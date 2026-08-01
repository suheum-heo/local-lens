"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type MouseEvent,
} from "react";
import { fetchLocations, searchRestaurants, toLocationPayload } from "@/lib/api";
import {
  CITIES,
  DEFAULT_FOOD_QUERY,
  DEFAULT_RADIUS_M,
  LOCATION_MODES,
  SEARCH_RADIUS_OPTIONS_M,
  formatRadiusLabel,
  locationSearchPlaceholder,
  type StationRadiusM,
} from "@/lib/constants";

import type {
  City,
  LocationCatalogItem,
  LocationMode,
  RatingCoverage,
  Restaurant,
  SearchResponse,
} from "@/lib/types";
import { nearestDistanceMeters } from "@/lib/geo";
import { RestaurantCard } from "./RestaurantCard";
import { ResultsMapClient } from "./ResultsMapClient";
import { areasFromSelection } from "@/lib/mapAreas";

const CHIP =
  "rounded-chip px-3.5 py-2 text-sm font-medium transition duration-200 ease-soft touch-manipulation";
const CHIP_ON = "bg-leaf text-white shadow-soft";
const CHIP_OFF =
  "bg-white text-ink/65 ring-1 ring-ink/[0.08] hover:bg-mist/80 hover:text-ink";
const FIELD =
  "w-full rounded-2xl border-0 bg-mist/60 px-4 py-3 text-ink outline-none ring-1 ring-ink/[0.06] transition placeholder:text-ink/35 focus:bg-white focus:ring-2 focus:ring-leaf/25";

const CITY_LABEL: Record<string, string> = Object.fromEntries(
  CITIES.map((c) => [c.value, c.label]),
);

const PAGE_SIZE = 10;

/** Run action on mousedown so a focused text field/IME cannot eat the first tap. */
function pressProps(action: () => void) {
  return {
    onMouseDown: (e: MouseEvent) => {
      if (e.button !== 0) return;
      e.preventDefault();
      action();
    },
    onKeyDown: (e: KeyboardEvent) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        action();
      }
    },
  };
}

type CoverageFilter = "all" | RatingCoverage;

export function SearchPage() {
  const [city, setCity] = useState<City>("seoul");
  const [mode, setMode] = useState<LocationMode>("station");
  const [catalog, setCatalog] = useState<LocationCatalogItem[]>([]);
  const [selected, setSelected] = useState<LocationCatalogItem[]>([]);
  const [radiusM, setRadiusM] = useState<StationRadiusM>(DEFAULT_RADIUS_M);
  const [filter, setFilter] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [selectedRestaurantId, setSelectedRestaurantId] = useState<
    string | null
  >(null);
  const [coverageFilter, setCoverageFilter] = useState<CoverageFilter>("all");
  const [page, setPage] = useState(1);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [mobilePane, setMobilePane] = useState<"list" | "map">("list");
  const listRef = useRef<HTMLDivElement | null>(null);
  const filterInputRef = useRef<HTMLInputElement | null>(null);
  const queryInputRef = useRef<HTMLInputElement | null>(null);
  const suggestionListRef = useRef<HTMLUListElement | null>(null);
  const filterDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);
  const selectedRef = useRef<LocationCatalogItem[]>([]);
  const searchingRef = useRef(false);
  const filteredRef = useRef<LocationCatalogItem[]>([]);
  const filterValueRef = useRef("");
  const addLocationRef = useRef<(item: LocationCatalogItem) => void>(() => {});
  const composingRef = useRef(false);
  const lastPointerRef = useRef({ x: 0, y: 0 });
  const pickLockRef = useRef(false);
  const ignoreBlurPickUntilRef = useRef(0);
  const imePointerDownRef = useRef(false);

  useEffect(() => {
    // Refresh / shared links must not restore a previous search session.
    if (typeof window !== "undefined" && window.location.search) {
      window.history.replaceState(null, "", window.location.pathname);
    }
  }, []);

  // Reset selection when city/mode changes; load base catalog.
  // Selection keeps its own city — never sync city from a chip click (that used
  // to clear selection under React Strict Mode's double effect invoke).
  useEffect(() => {
    let cancelled = false;
    setSelected([]);
    setResult(null);
    setSelectedRestaurantId(null);
    setFilter("");
    setError(null);
    setCatalogLoading(true);

    fetchLocations(city, mode, {
      nationwide: mode === "station",
    })
      .then((items) => {
        if (!cancelled) setCatalog(items);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setCatalogLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [city, mode]);

  // Bus / dong: live lookup as the user types (debounced).
  useEffect(() => {
    if (mode === "station") return;
    const q = filter.trim();
    let cancelled = false;
    if (filterDebounce.current) clearTimeout(filterDebounce.current);

    filterDebounce.current = setTimeout(() => {
      setCatalogLoading(true);
      fetchLocations(city, mode, { q: q || undefined })
        .then((items) => {
          if (!cancelled) setCatalog(items);
        })
        .catch((err: Error) => {
          if (!cancelled) setError(err.message);
        })
        .finally(() => {
          if (!cancelled) setCatalogLoading(false);
        });
    }, 350);

    return () => {
      cancelled = true;
      if (filterDebounce.current) clearTimeout(filterDebounce.current);
    };
  }, [filter, city, mode]);

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    let items = catalog;
    if (mode === "station") {
      if (!q) {
        items = catalog.filter((item) => item.city === city);
      } else {
        items = catalog.filter(
          (item) =>
            item.name.toLowerCase().includes(q) ||
            (item.name_en?.toLowerCase().includes(q) ?? false),
        );
      }
    }
    // bus_stop / neighborhood: catalog already comes from live/seed query
    return items.slice(0, 80);
  }, [catalog, filter, mode, city]);

  const modeLabel =
    LOCATION_MODES.find((m) => m.value === mode)?.label ?? "위치";

  const mapAreas = useMemo(
    () => areasFromSelection(selected, radiusM, mode),
    [selected, radiusM, mode],
  );

  const coverageCounts = useMemo(() => {
    const counts: Record<CoverageFilter, number> = {
      all: 0,
      both: 0,
      kakao_only: 0,
      google_only: 0,
      none: 0,
    };
    if (!result) return counts;
    counts.all = result.results.length;
    for (const r of result.results) {
      counts[r.rating_coverage] += 1;
    }
    return counts;
  }, [result]);

  const filteredResults = useMemo(() => {
    if (!result) return [] as Restaurant[];
    if (coverageFilter === "all") return result.results;
    return result.results.filter((r) => r.rating_coverage === coverageFilter);
  }, [result, coverageFilter]);

  const totalPages = Math.max(1, Math.ceil(filteredResults.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageResults = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return filteredResults.slice(start, start + PAGE_SIZE);
  }, [filteredResults, currentPage]);

  useEffect(() => {
    setPage(1);
  }, [coverageFilter, result]);

  useEffect(() => {
    selectedRef.current = selected;
  }, [selected]);

  useEffect(() => {
    filteredRef.current = filtered;
  }, [filtered]);

  useEffect(() => {
    filterValueRef.current = filter;
  }, [filter]);

  /** Add from the suggestion list (idempotent). Deselect only via chip ×. */
  const addLocation = useCallback((item: LocationCatalogItem) => {
    if (pickLockRef.current) return;
    pickLockRef.current = true;
    ignoreBlurPickUntilRef.current = Date.now() + 500;

    setSelected((prev) => {
      if (prev.some((s) => s.id === item.id)) return prev;
      return [...prev, item];
    });

    // Defer clearing the filter so the list does not reshuffle under the
    // still-active pointer/IME gesture (that was making search-picks need 2 taps).
    window.setTimeout(() => {
      setFilter("");
      filterInputRef.current?.blur();
      pickLockRef.current = false;
    }, 100);
  }, []);

  useEffect(() => {
    addLocationRef.current = addLocation;
  }, [addLocation]);

  function locationAtClientPoint(
    x: number,
    y: number,
  ): LocationCatalogItem | null {
    const ul = suggestionListRef.current;
    if (!ul) return null;
    const el = document.elementFromPoint(x, y) as HTMLElement | null;
    const row = el?.closest?.(
      "[data-location-id]",
    ) as HTMLElement | null;
    if (!row || !ul.contains(row)) return null;
    const id = row.getAttribute("data-location-id");
    if (!id) return null;
    return filteredRef.current.find((item) => item.id === id) ?? null;
  }

  function resolveBlurSelection(): LocationCatalogItem | null {
    const items = filteredRef.current;
    const q = filterValueRef.current.trim();
    if (!q || items.length === 0) return null;
    const exact = items.find(
      (i) =>
        i.name === q ||
        i.name === `${q}역` ||
        i.name.toLowerCase() === q.toLowerCase(),
    );
    if (exact) return exact;
    if (items.length === 1) return items[0];
    return null;
  }

  /** Recover selection when IME swallows the click and only compositionend fires. */
  function recoverImeSuggestionPick() {
    if (pickLockRef.current) return;
    const { x, y } = lastPointerRef.current;
    const under = locationAtClientPoint(x, y);
    if (under) {
      addLocationRef.current(under);
      return;
    }
    const ul = suggestionListRef.current;
    if (!ul) return;
    const rect = ul.getBoundingClientRect();
    if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) {
      return;
    }
    const choice = resolveBlurSelection() ?? filteredRef.current[0] ?? null;
    if (choice) addLocationRef.current(choice);
  }

  // Capture-phase listener: select by click coordinates, not event.target.
  // During Korean IME composition the browser may drop/retarget the click so
  // target is wrong — clientX/Y still point at the hovered suggestion.
  useEffect(() => {
    let handledByPointerDown = false;

    const trackPointer = (e: PointerEvent) => {
      lastPointerRef.current = { x: e.clientX, y: e.clientY };
    };

    const pickFromCoords = (e: Event) => {
      const ul = suggestionListRef.current;
      if (!ul || pickLockRef.current) return;
      const pe = e as PointerEvent | MouseEvent;
      if (!("clientX" in pe)) return;
      lastPointerRef.current = { x: pe.clientX, y: pe.clientY };
      if (composingRef.current) imePointerDownRef.current = true;

      const under = locationAtClientPoint(pe.clientX, pe.clientY);
      const fromTarget = (() => {
        const el = (e.target as HTMLElement | null)?.closest?.(
          "[data-location-id]",
        ) as HTMLElement | null;
        if (!el || !ul.contains(el)) return null;
        const id = el.getAttribute("data-location-id");
        return filteredRef.current.find((x) => x.id === id) ?? null;
      })();
      const item = under || fromTarget;
      if (!item) return;

      e.preventDefault();
      e.stopPropagation();
      addLocationRef.current(item);
    };

    const onPointerDown = (e: Event) => {
      handledByPointerDown = true;
      pickFromCoords(e);
    };
    const onMouseDown = (e: Event) => {
      // Safari / IME paths may skip PointerEvent; avoid double-handling.
      if (handledByPointerDown) {
        handledByPointerDown = false;
        return;
      }
      pickFromCoords(e);
    };

    document.addEventListener("pointermove", trackPointer, true);
    document.addEventListener("pointerdown", onPointerDown, true);
    document.addEventListener("mousedown", onMouseDown, true);
    return () => {
      document.removeEventListener("pointermove", trackPointer, true);
      document.removeEventListener("pointerdown", onPointerDown, true);
      document.removeEventListener("mousedown", onMouseDown, true);
    };
  }, []);

  function removeLocation(id: string) {
    setSelected((prev) => prev.filter((s) => s.id !== id));
  }

  const runSearch = useCallback(async () => {
    if (searchingRef.current) return;
    setError(null);

    // If the user typed a unique station (e.g. 지행) but IME ate the list
    // click, adopt that match so Search still works on the first press.
    let currentSelected = selectedRef.current;
    if (currentSelected.length === 0) {
      const inferred = resolveBlurSelection();
      if (inferred) {
        currentSelected = [inferred];
        selectedRef.current = currentSelected;
        setSelected(currentSelected);
        setFilter("");
      }
    }

    if (currentSelected.length === 0) {
      setError("검색할 위치를 하나 이상 선택하세요.");
      return;
    }
    searchingRef.current = true;
    setLoading(true);
    setSelectedRestaurantId(null);
    setCoverageFilter("all");
    setPage(1);
    queryInputRef.current?.blur();
    filterInputRef.current?.blur();
    try {
      // Use the selected place's city for the API only — do not setCity here.
      // setCity would re-run the city/mode effect and wipe selection + results.
      const requestCity = currentSelected[0]?.city ?? city;
      const foodQuery = query.trim() || DEFAULT_FOOD_QUERY;
      const data = await searchRestaurants({
        city: requestCity,
        mode,
        locations: currentSelected.map((item) =>
          toLocationPayload(item, radiusM),
        ),
        query: foodQuery,
      });
      setResult(data);
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "검색에 실패했습니다.");
    } finally {
      searchingRef.current = false;
      setLoading(false);
    }
  }, [city, mode, radiusM, query]);

  function selectRestaurant(restaurantId: string) {
    setSelectedRestaurantId(restaurantId);
    const el = document.getElementById(`restaurant-${restaurantId}`);
    el?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function goToPage(next: number) {
    const clamped = Math.min(Math.max(1, next), totalPages);
    setPage(clamped);
    listRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const summaryCards = [
    { id: "all" as const, label: "전체", value: coverageCounts.all },
    { id: "both" as const, label: "양쪽 검증", value: coverageCounts.both },
    {
      id: "google_only" as const,
      label: "Google 리뷰",
      value: coverageCounts.google_only,
    },
    {
      id: "kakao_only" as const,
      label: "Kakao만",
      value: coverageCounts.kakao_only,
    },
    { id: "none" as const, label: "데이터 없음", value: coverageCounts.none },
  ];

  return (
    <div className="mx-auto max-w-6xl px-4 pb-16 pt-10 sm:px-6 sm:pt-14 lg:px-8">
      <header className="mb-10 max-w-2xl sm:mb-14">
        <p className="font-display text-sm font-semibold tracking-[0.18em] text-leaf">
          LOCALLENS
        </p>
        <h1 className="mt-4 font-display text-[2.5rem] font-semibold leading-[1.15] tracking-tight text-ink text-balance sm:text-5xl sm:leading-[1.12]">
          한국인도,
          <br />
          외국인도
          <br />
          좋아하는 맛집.
        </h1>
        <p className="mt-4 max-w-lg text-base leading-relaxed text-ink/50 sm:text-lg">
          Kakao와 Google 데이터를 함께 비교해 더 신뢰할 수 있는 맛집을 찾습니다.
        </p>
      </header>

      <section className="rounded-card bg-card p-5 shadow-soft ring-1 ring-ink/[0.04] sm:p-7">
        <form
          className="space-y-7"
          onSubmit={(e) => {
            e.preventDefault();
            void runSearch();
          }}
        >
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-ink/35">
              City
            </div>
            <div
              className="mt-2.5 flex flex-wrap gap-2"
              role="radiogroup"
              aria-label="지역"
            >
              {CITIES.map((c) => {
                const active = city === c.value;
                return (
                  <button
                    key={c.value}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    {...pressProps(() => setCity(c.value))}
                    className={`${CHIP} ${active ? CHIP_ON : CHIP_OFF}`}
                  >
                    {c.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label className="text-xs font-medium uppercase tracking-wide text-ink/35">
              Food / Keyword
            </label>
            <input
              ref={queryInputRef}
              className={`mt-2.5 ${FIELD}`}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={`비우면 모든 음식 · 예: 삼겹살, 카페, 국밥`}
              autoComplete="off"
              autoCorrect="off"
              spellCheck={false}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  void runSearch();
                }
              }}
            />
          </div>

          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-ink/35">
              Location type
            </div>
            <div
              className="mt-2.5 grid grid-cols-3 gap-1 rounded-2xl bg-mist/70 p-1"
              role="radiogroup"
              aria-label="위치 유형"
            >
              {LOCATION_MODES.map((m) => {
                const active = mode === m.value;
                return (
                  <button
                    key={m.value}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    {...pressProps(() => setMode(m.value))}
                    className={`rounded-xl px-2 py-2.5 text-sm font-semibold transition duration-200 ease-soft sm:px-3 ${
                      active
                        ? "bg-white text-ink shadow-soft"
                        : "text-ink/50 hover:text-ink"
                    }`}
                  >
                    {m.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <div className="flex items-baseline justify-between gap-2">
              <label className="text-xs font-medium uppercase tracking-wide text-ink/35">
                {modeLabel}
              </label>
              {catalogLoading ? (
                <span className="text-xs text-ink/35">불러오는 중…</span>
              ) : null}
            </div>

            {selected.length > 0 ? (
              <div className="mt-2.5 flex flex-wrap gap-2" aria-label="선택된 위치">
                {selected.map((item) => (
                  <span
                    key={item.id}
                    className="inline-flex items-center gap-1 rounded-chip bg-leaf/10 py-1 pl-3 text-sm font-medium text-leaf"
                  >
                    {item.name}
                    <button
                      type="button"
                      {...pressProps(() => removeLocation(item.id))}
                      className="rounded-full px-2 py-0.5 text-leaf/70 transition hover:bg-leaf/10 hover:text-leaf"
                      aria-label={`${item.name} 제거`}
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            ) : null}

            <input
              ref={filterInputRef}
              className={`mt-2.5 ${FIELD}`}
              placeholder={locationSearchPlaceholder(city, mode)}
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              autoComplete="off"
              autoCorrect="off"
              spellCheck={false}
              onCompositionStart={() => {
                composingRef.current = true;
                imePointerDownRef.current = false;
              }}
              onCompositionEnd={() => {
                composingRef.current = false;
                const hadPointer = imePointerDownRef.current;
                imePointerDownRef.current = false;
                requestAnimationFrame(() => {
                  if (hadPointer) {
                    recoverImeSuggestionPick();
                    return;
                  }
                  const { x, y } = lastPointerRef.current;
                  const under = locationAtClientPoint(x, y);
                  if (under) {
                    const unique = resolveBlurSelection();
                    if (
                      unique?.id === under.id ||
                      filteredRef.current.length === 1
                    ) {
                      addLocationRef.current(under);
                      return;
                    }
                  }
                  if (
                    filteredRef.current.length === 1 &&
                    filterValueRef.current.trim().length >= 2
                  ) {
                    addLocationRef.current(filteredRef.current[0]);
                  }
                });
              }}
              onKeyDown={(e) => {
                if (e.key !== "Enter" || e.nativeEvent.isComposing) return;
                e.preventDefault();
                const first = filtered[0];
                if (first) addLocation(first);
              }}
              onBlur={(e) => {
                if (Date.now() < ignoreBlurPickUntilRef.current) return;
                const related = e.relatedTarget as HTMLElement | null;
                const viaOption = related?.closest?.(
                  "[data-location-id]",
                ) as HTMLElement | null;
                if (viaOption) {
                  const id = viaOption.getAttribute("data-location-id");
                  const item = filteredRef.current.find((x) => x.id === id);
                  if (item) addLocation(item);
                  return;
                }
                window.setTimeout(() => {
                  if (Date.now() < ignoreBlurPickUntilRef.current) return;
                  if (document.activeElement === filterInputRef.current) return;
                  const { x, y } = lastPointerRef.current;
                  const under = locationAtClientPoint(x, y);
                  if (under) {
                    addLocationRef.current(under);
                    return;
                  }
                  const choice = resolveBlurSelection();
                  if (choice) addLocationRef.current(choice);
                }, 0);
              }}
            />
            <ul
              ref={suggestionListRef}
              className="mt-2 max-h-44 overflow-auto rounded-2xl bg-mist/40 ring-1 ring-ink/[0.05]"
              role="listbox"
              aria-label={`${modeLabel} 검색 결과`}
            >
              {filtered.length === 0 ? (
                <li className="px-4 py-3 text-sm text-ink/40">
                  {catalogLoading
                    ? "위치를 불러오는 중이에요…"
                    : mode === "bus_stop" && filter.trim().length < 2
                      ? "정류장 이름을 두 글자 이상 입력해 주세요."
                      : "검색된 위치가 없어요. 다른 이름을 입력해 보세요."}
                </li>
              ) : (
                filtered.map((item) => {
                  const active = selected.some((s) => s.id === item.id);
                  return (
                    <li
                      key={item.id}
                      role="option"
                      aria-selected={active}
                      data-location-id={item.id}
                      className={`flex w-full cursor-pointer touch-manipulation items-center justify-between px-4 py-2.5 text-left text-sm transition ${
                        active
                          ? "bg-leaf/10 font-medium text-leaf"
                          : "text-ink hover:bg-white/80"
                      }`}
                    >
                      <span>{item.name}</span>
                      <span className="text-xs text-ink/35">
                        {active
                          ? "선택됨"
                          : CITY_LABEL[item.city] || item.name_en || item.city}
                      </span>
                    </li>
                  );
                })
              )}
            </ul>
          </div>

          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-ink/35">
              Radius
            </div>
            <div className="mt-2.5 flex flex-wrap gap-2">
              {SEARCH_RADIUS_OPTIONS_M.map((r) => {
                const active = radiusM === r;
                return (
                  <button
                    key={r}
                    type="button"
                    {...pressProps(() => setRadiusM(r))}
                    className={`${CHIP} ${active ? CHIP_ON : CHIP_OFF}`}
                  >
                    {formatRadiusLabel(r)}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex flex-col gap-3 pt-1 sm:flex-row sm:items-center">
            <button
              type="submit"
              disabled={loading}
              {...pressProps(() => {
                if (!loading) void runSearch();
              })}
              className="inline-flex w-full items-center justify-center rounded-chip bg-leaf px-6 py-3 text-sm font-semibold text-white shadow-soft transition duration-200 ease-soft hover:bg-leaf/90 hover:shadow-lift disabled:opacity-55 sm:w-auto"
            >
              {loading ? "검색 중…" : "맛집 찾기"}
            </button>
            {error ? (
              <p className="text-sm text-clay" role="alert">
                {error}
              </p>
            ) : null}
          </div>
        </form>
      </section>

      {!result && selected.length > 0 ? (
        <section className="mt-8">
          <div className="mb-3 text-xs font-medium uppercase tracking-wide text-ink/35">
            Area preview
          </div>
          <div className="h-56 sm:h-72">
            <ResultsMapClient
              areas={mapAreas}
              restaurants={[]}
              selectedRestaurantId={null}
              onSelectRestaurant={() => undefined}
            />
          </div>
        </section>
      ) : null}

      {result ? (
        <section className="mt-12 sm:mt-16">
          <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
                Results
              </h2>
              <p className="mt-1 text-sm text-ink/40">
                {result.meta.query} · {formatRadiusLabel(radiusM)} ·{" "}
                {result.meta.area_count}곳 기준
              </p>
            </div>
          </div>

          <div className="mb-6 grid grid-cols-2 gap-2 sm:grid-cols-5">
            {summaryCards.map((card) => {
              const active = coverageFilter === card.id;
              return (
                <button
                  key={card.id}
                  type="button"
                  onClick={() =>
                    setCoverageFilter(card.id === "all" ? "all" : card.id)
                  }
                  className={`rounded-card px-3 py-3 text-left transition duration-200 ease-soft sm:px-4 sm:py-4 ${
                    active
                      ? "bg-leaf text-white shadow-soft"
                      : "bg-card text-ink shadow-soft ring-1 ring-ink/[0.04] hover:shadow-lift"
                  }`}
                >
                  <div
                    className={`text-[11px] font-medium tracking-wide ${
                      active ? "text-white/70" : "text-ink/40"
                    }`}
                  >
                    {card.label}
                  </div>
                  <div className="mt-1 text-2xl font-semibold tabular-nums tracking-tight">
                    {card.value}
                  </div>
                </button>
              );
            })}
          </div>

          {result.notices.length > 0 ? (
            <div className="mb-6 rounded-2xl bg-mist/60 px-4 py-3 text-sm text-ink/50">
              {result.notices[0]}
            </div>
          ) : null}

          <div
            className="mb-4 flex rounded-2xl bg-mist/70 p-1 lg:hidden"
            role="tablist"
            aria-label="결과 보기"
          >
            {(
              [
                { id: "list" as const, label: "List" },
                { id: "map" as const, label: "Map" },
              ] as const
            ).map((tab) => {
              const active = mobilePane === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  onClick={() => setMobilePane(tab.id)}
                  className={`flex-1 rounded-xl py-2.5 text-sm font-semibold transition ${
                    active
                      ? "bg-white text-ink shadow-soft"
                      : "text-ink/45"
                  }`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>

          <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
            <div
              ref={listRef}
              className={mobilePane === "list" ? "block" : "hidden lg:block"}
            >
              {filteredResults.length === 0 ? (
                <div className="rounded-card bg-card px-6 py-16 text-center shadow-soft ring-1 ring-ink/[0.04]">
                  <p className="text-lg font-semibold text-ink">
                    조건에 맞는 식당이 없어요
                  </p>
                  <p className="mt-2 text-sm text-ink/45">
                    다른 분류를 고르거나 반경·키워드를 바꿔 보세요.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {pageResults.map((r) => (
                    <RestaurantCard
                      key={r.restaurant_id}
                      restaurant={r}
                      selected={r.restaurant_id === selectedRestaurantId}
                      onSelect={selectRestaurant}
                      distanceM={nearestDistanceMeters(
                        r.latitude,
                        r.longitude,
                        mapAreas,
                      )}
                    />
                  ))}
                  {totalPages > 1 ? (
                    <div className="flex flex-wrap items-center justify-center gap-2 pt-4">
                      <button
                        type="button"
                        disabled={currentPage <= 1}
                        onClick={() => goToPage(currentPage - 1)}
                        className={`${CHIP} ${CHIP_OFF} disabled:opacity-40`}
                      >
                        이전
                      </button>
                      <span className="px-2 text-sm tabular-nums text-ink/40">
                        {currentPage} / {totalPages}
                      </span>
                      <button
                        type="button"
                        disabled={currentPage >= totalPages}
                        onClick={() => goToPage(currentPage + 1)}
                        className={`${CHIP} ${CHIP_OFF} disabled:opacity-40`}
                      >
                        다음
                      </button>
                    </div>
                  ) : null}
                </div>
              )}
            </div>

            <div
              className={`lg:sticky lg:top-6 ${
                mobilePane === "map" ? "block" : "hidden lg:block"
              }`}
            >
              <div className="h-[22rem] sm:h-[28rem] lg:h-[min(70vh,40rem)]">
                {mapAreas.length > 0 ? (
                  <ResultsMapClient
                    areas={mapAreas}
                    restaurants={filteredResults}
                    selectedRestaurantId={selectedRestaurantId}
                    onSelectRestaurant={(id) => {
                      setMobilePane("list");
                      selectRestaurant(id);
                    }}
                  />
                ) : (
                  <div className="flex h-full items-center justify-center rounded-card bg-card text-sm text-ink/40 shadow-soft">
                    위치를 선택하면 지도가 표시됩니다
                  </div>
                )}
              </div>
            </div>
          </div>
        </section>
      ) : null}
    </div>
  );
}
