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
const CHIP_ON = "bg-brand text-white shadow-soft";
const CHIP_OFF =
  "bg-white text-ink/65 ring-1 ring-line hover:bg-mist hover:text-ink";
const FIELD =
  "w-full rounded-2xl border-0 bg-mist/80 px-4 py-3 text-ink outline-none ring-1 ring-line transition placeholder:text-mute/70 focus:bg-white focus:ring-2 focus:ring-brand/25";
const LABEL =
  "text-xs font-semibold uppercase tracking-wide text-mute";

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
  const filterDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);
  const selectedRef = useRef<LocationCatalogItem[]>([]);
  const searchingRef = useRef(false);
  const filteredRef = useRef<LocationCatalogItem[]>([]);
  const catalogByIdRef = useRef<Map<string, LocationCatalogItem>>(new Map());
  const filterValueRef = useRef("");
  const addLocationRef = useRef<(item: LocationCatalogItem) => void>(() => {});
  /** Same-id debounce only — must not block picking a different station next. */
  const lastPickedIdRef = useRef<{ id: string; at: number } | null>(null);
  const ignoreBlurPickUntilRef = useRef(0);
  /** Hangul IME: 1-char queries stay composing; first click only commits IME. */
  const composingRef = useRef(false);
  const lastPointerRef = useRef({ x: 0, y: 0, downAt: 0 });
  const suggestionListRef = useRef<HTMLUListElement | null>(null);

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
    if (mode === "station") {
      if (!q) {
        // Full city catalog (Seoul ~465). Truncating hid 합정/홍대 등 so users
        // had to type + fight IME for those stations.
        return catalog.filter((item) => item.city === city);
      }
      const matched = catalog.filter(
        (item) =>
          item.name.toLowerCase().includes(q) ||
          (item.name_en?.toLowerCase().includes(q) ?? false),
      );
      // Prefer exact / prefix matches so "압구정" surfaces 압구정역 before
      // 압구정로데오역, and short typed queries feel one-click reliable.
      const rank = (item: LocationCatalogItem) => {
        const name = item.name.toLowerCase();
        const bare = name.replace(/역$/, "");
        if (name === q || name === `${q}역` || bare === q) return 0;
        if (name.startsWith(q) || bare.startsWith(q)) return 1;
        if (item.name_en?.toLowerCase().startsWith(q)) return 2;
        return 3;
      };
      return matched
        .sort((a, b) => {
          const d = rank(a) - rank(b);
          if (d !== 0) return d;
          return a.name.length - b.name.length || a.name.localeCompare(b.name, "ko");
        })
        .slice(0, 120);
    }
    // bus_stop / neighborhood: catalog already comes from live/seed query
    return catalog.slice(0, 120);
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
    const map = new Map<string, LocationCatalogItem>();
    for (const item of catalog) map.set(item.id, item);
    catalogByIdRef.current = map;
  }, [catalog]);

  useEffect(() => {
    filterValueRef.current = filter;
  }, [filter]);

  function locationById(id: string | null | undefined): LocationCatalogItem | null {
    if (!id) return null;
    return catalogByIdRef.current.get(id) ?? null;
  }

  /** Add from the suggestion list (idempotent). Deselect only via chip ×. */
  const addLocation = useCallback((item: LocationCatalogItem) => {
    if (selectedRef.current.some((s) => s.id === item.id)) return;

    const now = Date.now();
    const last = lastPickedIdRef.current;
    if (last && last.id === item.id && now - last.at < 400) return;
    lastPickedIdRef.current = { id: item.id, at: now };
    ignoreBlurPickUntilRef.current = now + 600;

    setSelected((prev) => {
      if (prev.some((s) => s.id === item.id)) return prev;
      return [...prev, item];
    });
    setFilter("");
  }, []);

  useEffect(() => {
    addLocationRef.current = addLocation;
  }, [addLocation]);

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

  /** Pick a row from the closed-over item — never re-resolve via a reshuffled list. */
  function pickSuggestion(
    item: LocationCatalogItem,
    e?: { preventDefault(): void; stopPropagation(): void },
  ) {
    e?.preventDefault();
    e?.stopPropagation();
    addLocation(item);
  }

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
    return locationById(row.getAttribute("data-location-id"));
  }

  // While Hangul IME is composing (common after typing just 1 syllable), the
  // browser spends the first click committing composition — often retargeted
  // to the input — so the suggestion button never sees pointerdown.
  // Capture the click coordinates and select the row under the cursor instead.
  useEffect(() => {
    const onPointerDown = (e: PointerEvent) => {
      lastPointerRef.current = {
        x: e.clientX,
        y: e.clientY,
        downAt: Date.now(),
      };
      if (!composingRef.current) return;
      const item = locationAtClientPoint(e.clientX, e.clientY);
      if (!item) return;
      e.preventDefault();
      e.stopPropagation();
      addLocationRef.current(item);
    };
    document.addEventListener("pointerdown", onPointerDown, true);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown, true);
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
    {
      id: "both" as const,
      label: "양쪽 검증",
      hint: "Consensus Pick",
      value: coverageCounts.both,
      accent: "text-brand-dark",
      iconBg: "bg-brand/15 text-brand-dark",
      activeClass: "ring-brand/40 bg-brand/5",
      dot: "bg-brand",
    },
    {
      id: "google_only" as const,
      label: "Google 리뷰",
      hint: "Global Favorite",
      value: coverageCounts.google_only,
      accent: "text-global",
      iconBg: "bg-global/15 text-global",
      activeClass: "ring-global/40 bg-global/5",
      dot: "bg-global",
    },
    {
      id: "kakao_only" as const,
      label: "Kakao만",
      hint: "Local Favorite",
      value: coverageCounts.kakao_only,
      accent: "text-local",
      iconBg: "bg-local/15 text-local",
      activeClass: "ring-local/40 bg-local/5",
      dot: "bg-local",
    },
    {
      id: "none" as const,
      label: "데이터 부족",
      hint: "Limited Data",
      value: coverageCounts.none,
      accent: "text-violet",
      iconBg: "bg-violet/15 text-violet",
      activeClass: "ring-violet/40 bg-violet/5",
      dot: "bg-violet",
    },
  ];

  const selectedSummary =
    selected.length === 0
      ? null
      : selected.length === 1
        ? selected[0].name
        : `${selected[0].name} 외 ${selected.length - 1}곳`;

  const searchForm = (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        void runSearch();
      }}
    >
      <div>
        <label className={LABEL} htmlFor="ll-city">
          지역
        </label>
        <select
          id="ll-city"
          className={`mt-2 ${FIELD} appearance-none`}
          value={city}
          onChange={(e) => setCity(e.target.value as City)}
        >
          {CITIES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <div className={LABEL}>위치 유형</div>
        <div
          className="mt-2 flex flex-wrap gap-2"
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
                className={`${CHIP} ${active ? CHIP_ON : CHIP_OFF}`}
              >
                {m.label}
              </button>
            );
          })}
        </div>
      </div>

      <div>
        <div className="flex items-baseline justify-between gap-2">
          <label className={LABEL} htmlFor="ll-location">
            {modeLabel}
          </label>
          {catalogLoading ? (
            <span className="text-xs text-mute">불러오는 중…</span>
          ) : null}
        </div>

        {selected.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-2" aria-label="선택된 위치">
            {selected.map((item) => (
              <span
                key={item.id}
                className="inline-flex items-center gap-1 rounded-chip bg-brand/10 py-1 pl-3 text-sm font-medium text-brand-dark"
              >
                {item.name}
                <button
                  type="button"
                  {...pressProps(() => removeLocation(item.id))}
                  className="rounded-full px-2 py-0.5 text-brand-dark/70 transition hover:bg-brand/10"
                  aria-label={`${item.name} 제거`}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        ) : null}

        <input
          id="ll-location"
          ref={filterInputRef}
          className={`mt-2 ${FIELD}`}
          placeholder={locationSearchPlaceholder(city, mode)}
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
          onCompositionStart={() => {
            composingRef.current = true;
          }}
          onCompositionEnd={() => {
            composingRef.current = false;
            // Click-to-confirm IME: pointerdown may have been retargeted to the
            // input, so recover the row under the recent click coordinates.
            // Keyboard-only commits (no recent pointerdown) must not auto-pick
            // a hovered row when many matches exist (1-char queries).
            window.requestAnimationFrame(() => {
              if (Date.now() < ignoreBlurPickUntilRef.current) return;
              const { x, y, downAt } = lastPointerRef.current;
              if (Date.now() - downAt < 500) {
                const under = locationAtClientPoint(x, y);
                if (under) {
                  addLocationRef.current(under);
                  return;
                }
              }
              // Fully typed unique name (e.g. 지행) → select without a click.
              const choice = resolveBlurSelection();
              if (
                choice &&
                filterValueRef.current.trim().length >= 2 &&
                (filteredRef.current.length === 1 ||
                  choice.name === filterValueRef.current.trim() ||
                  choice.name === `${filterValueRef.current.trim()}역`)
              ) {
                addLocationRef.current(choice);
              }
            });
          }}
          onPointerDown={(e) => {
            // IME often retargets the first tap onto this input while still
            // composing (1-char case). Select the suggestion under the cursor.
            lastPointerRef.current = {
              x: e.clientX,
              y: e.clientY,
              downAt: Date.now(),
            };
            if (!composingRef.current) return;
            const under = locationAtClientPoint(e.clientX, e.clientY);
            if (!under) return;
            e.preventDefault();
            addLocation(under);
          }}
          onMouseDown={(e) => {
            lastPointerRef.current = {
              x: e.clientX,
              y: e.clientY,
              downAt: Date.now(),
            };
            if (!composingRef.current) return;
            const under = locationAtClientPoint(e.clientX, e.clientY);
            if (!under) return;
            e.preventDefault();
            addLocation(under);
          }}
          onKeyDown={(e) => {
            if (e.key !== "Enter" || e.nativeEvent.isComposing) return;
            e.preventDefault();
            const choice = resolveBlurSelection() ?? filtered[0];
            if (choice) addLocation(choice);
          }}
          onBlur={(e) => {
            if (Date.now() < ignoreBlurPickUntilRef.current) return;
            const related = e.relatedTarget as HTMLElement | null;
            const viaOption = related?.closest?.(
              "[data-location-id]",
            ) as HTMLElement | null;
            if (viaOption) {
              const item = locationById(
                viaOption.getAttribute("data-location-id"),
              );
              if (item) addLocation(item);
              return;
            }
            window.setTimeout(() => {
              if (Date.now() < ignoreBlurPickUntilRef.current) return;
              if (document.activeElement === filterInputRef.current) return;
              // Prefer the row under the pointer (1-char + click-away path).
              const { x, y, downAt } = lastPointerRef.current;
              if (Date.now() - downAt < 500) {
                const under = locationAtClientPoint(x, y);
                if (under) {
                  addLocationRef.current(under);
                  return;
                }
              }
              const choice = resolveBlurSelection();
              if (choice) addLocationRef.current(choice);
            }, 0);
          }}
        />
        <ul
          ref={suggestionListRef}
          className="mt-2 max-h-56 overflow-auto rounded-2xl bg-white ring-1 ring-line"
          role="listbox"
          aria-label={`${modeLabel} 검색 결과`}
        >
          {filtered.length === 0 ? (
            <li className="px-4 py-3 text-sm text-mute">
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
                <li key={item.id} role="presentation">
                  <button
                    type="button"
                    role="option"
                    aria-selected={active}
                    data-location-id={item.id}
                    disabled={active}
                    onPointerDown={(e) => {
                      // Combobox pattern: pick on pointerdown + preventDefault so
                      // Hangul IME / input blur cannot swallow the first tap.
                      // Skip click handlers — clearing the filter unmounts this
                      // row and a late click can land on a different station.
                      if (e.button !== 0 || active) return;
                      pickSuggestion(item, e);
                    }}
                    onMouseDown={(e) => {
                      // Safari / some IME paths skip PointerEvent.
                      if (e.button !== 0 || active) return;
                      pickSuggestion(item, e);
                    }}
                    onKeyDown={(e) => {
                      if (active) return;
                      if (e.key !== "Enter" && e.key !== " ") return;
                      e.preventDefault();
                      pickSuggestion(item);
                    }}
                    className={`flex w-full touch-manipulation items-center justify-between px-4 py-2.5 text-left text-sm transition ${
                      active
                        ? "cursor-default bg-brand/10 font-medium text-brand-dark"
                        : "cursor-pointer text-ink hover:bg-mist/80"
                    }`}
                  >
                    <span>{item.name}</span>
                    <span className="text-xs text-mute">
                      {active
                        ? "선택됨"
                        : CITY_LABEL[item.city] || item.name_en || item.city}
                    </span>
                  </button>
                </li>
              );
            })
          )}
        </ul>
      </div>

      <div>
        <div className={LABEL}>반경</div>
        <div className="mt-2 flex flex-wrap gap-2">
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

      <div>
        <label className={LABEL} htmlFor="ll-query">
          음식 / 키워드
        </label>
        <input
          id="ll-query"
          ref={queryInputRef}
          className={`mt-2 ${FIELD}`}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="비우면 모든 음식 · 예: 삼겹살, 카페, 국밥"
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

      <div className="space-y-2 pt-1">
        <button
          type="submit"
          disabled={loading}
          {...pressProps(() => {
            if (!loading) void runSearch();
          })}
          className="inline-flex w-full items-center justify-center rounded-chip bg-brand-gradient px-6 py-3.5 text-sm font-semibold text-white shadow-glow transition duration-200 ease-soft hover:brightness-105 disabled:opacity-55"
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
  );

  return (
    <div className="min-h-screen lg:flex">
      <aside className="border-b border-line/80 bg-card/80 backdrop-blur-sm lg:sticky lg:top-0 lg:h-screen lg:w-[22rem] lg:shrink-0 lg:overflow-y-auto lg:border-b-0 lg:border-r xl:w-[24rem]">
        <div className="px-5 py-7 sm:px-6 sm:py-8">
          <div className="flex items-center gap-2.5">
            <span
              className="flex h-9 w-9 items-center justify-center rounded-2xl bg-brand-gradient text-sm font-bold text-white shadow-glow"
              aria-hidden
            >
              L
            </span>
            <div>
              <p className="font-display text-base font-bold tracking-tight text-ink">
                LocalLens
              </p>
              <p className="text-[11px] font-medium text-mute">
                Local × Global
              </p>
            </div>
          </div>

          <header className="mt-7">
            <h1 className="font-display text-[1.75rem] font-semibold leading-snug tracking-tight text-ink text-balance sm:text-[2rem]">
              두 시선이 만나는
              <br />
              진짜 맛집을 찾다.
            </h1>
            <p className="mt-3 text-sm leading-relaxed text-mute">
              Kakao와 Google 데이터를 함께 비교해 더 신뢰할 수 있는 맛집을
              찾습니다.
            </p>
          </header>

          <div className="mt-7">{searchForm}</div>
        </div>
      </aside>

      <main className="min-w-0 flex-1 px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-8">
        {!result ? (
          <section className="mx-auto flex max-w-3xl flex-col items-center justify-center px-4 py-16 text-center sm:py-24">
            <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-brand/10 text-2xl font-bold text-brand-dark">
              ◌
            </div>
            <h2 className="mt-5 text-xl font-semibold tracking-tight text-ink">
              {selected.length > 0
                ? "검색 영역을 확인했어요"
                : "위치를 고르고 맛집을 찾아보세요"}
            </h2>
            <p className="mt-2 max-w-md text-sm leading-relaxed text-mute">
              {selected.length > 0
                ? "왼쪽에서 키워드와 반경을 확인한 뒤 「맛집 찾기」를 눌러 주세요."
                : "지하철역·버스정류장·동을 선택한 뒤 Kakao와 Google 시선으로 비교합니다."}
            </p>
            {selected.length > 0 && mapAreas.length > 0 ? (
              <div className="mt-8 h-56 w-full max-w-xl sm:h-72">
                <ResultsMapClient
                  areas={mapAreas}
                  restaurants={[]}
                  selectedRestaurantId={null}
                  onSelectRestaurant={() => undefined}
                />
              </div>
            ) : null}
          </section>
        ) : (
          <section>
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 className="font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
                  {coverageCounts.all.toLocaleString()}곳
                </h2>
                <p className="mt-1 text-sm text-mute">
                  {[selectedSummary, formatRadiusLabel(radiusM), result.meta.query]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </div>
              <div
                className="flex rounded-2xl bg-mist p-1"
                role="tablist"
                aria-label="결과 보기"
              >
                {(
                  [
                    { id: "list" as const, label: "리스트" },
                    { id: "map" as const, label: "지도" },
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
                      className={`rounded-xl px-3.5 py-2 text-sm font-semibold transition lg:hidden ${
                        active
                          ? "bg-white text-ink shadow-soft"
                          : "text-mute"
                      }`}
                    >
                      {tab.label}
                    </button>
                  );
                })}
                <span className="hidden px-3 py-2 text-sm font-medium text-mute lg:inline">
                  리스트 + 지도
                </span>
              </div>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-2.5 xl:grid-cols-4">
              {summaryCards.map((card) => {
                const active = coverageFilter === card.id;
                return (
                  <button
                    key={card.id}
                    type="button"
                    onClick={() =>
                      setCoverageFilter(active ? "all" : card.id)
                    }
                    className={`rounded-card bg-card px-3.5 py-3.5 text-left shadow-soft ring-1 transition duration-200 ease-soft hover:shadow-lift ${
                      active
                        ? `${card.activeClass} ring-2`
                        : "ring-line hover:ring-brand/20"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${card.iconBg}`}
                      >
                        <span
                          className={`h-2 w-2 rounded-full ${card.dot}`}
                        />
                      </span>
                      <span className="text-xs font-medium text-mute">
                        {card.label}
                      </span>
                    </div>
                    <div
                      className={`mt-2 text-2xl font-bold tabular-nums tracking-tight ${card.accent}`}
                    >
                      {card.value}
                    </div>
                    <div className="mt-0.5 text-[11px] text-mute">
                      {card.hint}
                    </div>
                  </button>
                );
              })}
            </div>

            {result.notices.length > 0 ? (
              <div className="mt-4 rounded-2xl bg-mist/80 px-4 py-3 text-sm text-mute">
                {result.notices[0]}
              </div>
            ) : null}

            <div className="mt-6 grid gap-5 lg:grid-cols-2 lg:items-start">
              <div
                ref={listRef}
                className={mobilePane === "list" ? "block" : "hidden lg:block"}
              >
                {filteredResults.length === 0 ? (
                  <div className="rounded-card bg-card px-6 py-16 text-center shadow-soft ring-1 ring-line">
                    <p className="text-lg font-semibold text-ink">
                      조건에 맞는 식당이 없어요
                    </p>
                    <p className="mt-2 text-sm text-mute">
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
                        <span className="px-2 text-sm tabular-nums text-mute">
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
                <div className="h-[22rem] sm:h-[28rem] lg:h-[min(72vh,42rem)]">
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
                    <div className="flex h-full items-center justify-center rounded-card bg-card text-sm text-mute shadow-soft ring-1 ring-line">
                      위치를 선택하면 지도가 표시됩니다
                    </div>
                  )}
                </div>
              </div>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
