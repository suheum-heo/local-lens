"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
import { RestaurantCard } from "./RestaurantCard";
import { ResultsMapClient } from "./ResultsMapClient";
import { areasFromSelection } from "@/lib/mapAreas";

const CITY_LABEL: Record<string, string> = Object.fromEntries(
  CITIES.map((c) => [c.value, c.label]),
);

const PAGE_SIZE = 10;

type CoverageFilter = "all" | RatingCoverage;

const COVERAGE_TABS: { id: CoverageFilter; label: string }[] = [
  { id: "all", label: "전체" },
  { id: "both", label: "양쪽 평점" },
  { id: "kakao_only", label: "카카오만" },
  { id: "google_only", label: "구글만" },
];

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
  const listRef = useRef<HTMLDivElement | null>(null);
  const filterInputRef = useRef<HTMLInputElement | null>(null);
  const queryInputRef = useRef<HTMLInputElement | null>(null);
  const filterDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);
  const selectedRef = useRef<LocationCatalogItem[]>([]);
  const pressLockRef = useRef(false);
  const searchingRef = useRef(false);

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

  function toggleLocation(item: LocationCatalogItem) {
    setSelected((prev) => {
      if (prev.some((s) => s.id === item.id)) {
        return prev.filter((s) => s.id !== item.id);
      }
      return [...prev, item];
    });
  }

  /** Select/deselect from the suggestion list in one gesture (no second tap). */
  function pressLocation(item: LocationCatalogItem) {
    if (pressLockRef.current) return;
    pressLockRef.current = true;

    toggleLocation(item);
    // Blur immediately so IME/keyboard dismiss is part of this same gesture.
    // Clear the filter only after the click sequence finishes — clearing too
    // early reshuffles the list under the cursor and can steal mouseup/click.
    filterInputRef.current?.blur();
    window.setTimeout(() => {
      setFilter("");
      pressLockRef.current = false;
    }, 400);
  }

  function removeLocation(id: string) {
    setSelected((prev) => prev.filter((s) => s.id !== id));
  }

  const runSearch = useCallback(async () => {
    if (searchingRef.current) return;
    setError(null);
    const currentSelected = selectedRef.current;
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

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:py-12">
      <header className="mb-8">
        <p className="text-sm font-medium tracking-wide text-leaf">LocalLens</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
          로컬과 글로벌 시선으로 맛집 찾기
        </h1>
        <p className="mt-2 max-w-xl text-sm leading-relaxed text-ink/60">
          Kakao의 로컬 신호와 Google의 글로벌 리뷰를 함께 봅니다. 데이터가
          없으면 비워 두고, 부족하면 점수를 만들지 않습니다.
        </p>
      </header>

      <section className="space-y-5 border-t border-ink/10 pt-6">
        <form
          className="space-y-5"
          onSubmit={(e) => {
            e.preventDefault();
            void runSearch();
          }}
        >
        <fieldset>
          <legend className="text-base font-semibold text-ink">지역</legend>
          <div className="mt-2 flex flex-wrap gap-2" role="radiogroup" aria-label="지역">
            {CITIES.map((c) => {
              const active = city === c.value;
              return (
                <button
                  key={c.value}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  onClick={() => setCity(c.value)}
                  className={`border px-3.5 py-2 text-sm font-medium transition ${
                    active
                      ? "border-leaf bg-leaf text-white shadow-sm"
                      : "border-ink/20 bg-white text-ink hover:border-leaf/50 hover:bg-leaf/5"
                  }`}
                >
                  {c.label}
                </button>
              );
            })}
          </div>
        </fieldset>

        <fieldset>
          <legend className="text-base font-semibold text-ink">위치 유형</legend>
          <div
            className="mt-2 grid grid-cols-3 gap-2"
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
                  onClick={() => setMode(m.value)}
                  className={`border px-3 py-3 text-sm font-semibold transition sm:py-3.5 ${
                    active
                      ? "border-leaf bg-leaf text-white shadow-sm"
                      : "border-ink/20 bg-white text-ink hover:border-leaf/50 hover:bg-leaf/5"
                  }`}
                >
                  {m.label}
                </button>
              );
            })}
          </div>
        </fieldset>

        <fieldset>
          <legend className="text-sm text-ink/60">검색 반경</legend>
          <div className="mt-2 flex flex-wrap gap-2">
            {SEARCH_RADIUS_OPTIONS_M.map((r) => {
              const active = radiusM === r;
              return (
                <button
                  key={r}
                  type="button"
                  onClick={() => setRadiusM(r)}
                  className={`border px-3 py-1.5 text-sm transition ${
                    active
                      ? "border-leaf bg-leaf text-white"
                      : "border-ink/15 bg-white text-ink hover:border-leaf/40"
                  }`}
                >
                  {formatRadiusLabel(r)}
                </button>
              );
            })}
          </div>
          <p className="mt-1.5 text-xs text-ink/45">
            선택한 모든 위치에 동일 반경이 적용됩니다. 기본값 1 km.
          </p>
        </fieldset>

        <div>
          <label className="block text-sm text-ink/60">{modeLabel} 선택</label>

          {selected.length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-2" aria-label="선택된 위치">
              {selected.map((item) => (
                <span
                  key={item.id}
                  className="inline-flex items-center gap-1 border border-leaf/25 bg-leaf/10 pl-2.5 text-sm text-leaf"
                >
                  {item.name}
                  <button
                    type="button"
                    onClick={() => removeLocation(item.id)}
                    className="px-2 py-1 text-leaf/70 hover:bg-leaf/15 hover:text-leaf"
                    aria-label={`${item.name} 제거`}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-xs text-ink/45">
              아래에서 위치를 골라 여러 곳을 함께 검색할 수 있습니다.
            </p>
          )}

          <input
            ref={filterInputRef}
            className="mt-2 w-full border border-ink/15 bg-white px-3 py-2 text-ink outline-none focus:border-leaf"
            placeholder={locationSearchPlaceholder(city, mode)}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
            onKeyDown={(e) => {
              if (e.key !== "Enter" || e.nativeEvent.isComposing) return;
              e.preventDefault();
              const first = filtered[0];
              if (first) pressLocation(first);
            }}
          />
          <p className="mt-1.5 text-xs text-ink/45">
            {mode === "station"
              ? "기본은 선택한 지역 역 목록입니다. 이름을 입력하면 전국 역도 검색됩니다."
              : mode === "bus_stop"
                ? "정류장 이름을 입력하면 선택한 지역 주변 버스정류장을 찾습니다."
                : "동 이름을 입력하면 행정동/법정동을 찾습니다."}
            {catalogLoading ? " · 불러오는 중…" : ""}
          </p>
          <ul className="mt-2 max-h-40 overflow-auto border border-ink/10 bg-white">
            {filtered.length === 0 ? (
              <li className="px-3 py-2 text-sm text-ink/45">
                {mode === "bus_stop" && filter.trim().length < 2
                  ? "정류장 이름을 두 글자 이상 입력해 주세요."
                  : "검색된 위치가 없습니다. 다른 이름을 입력해 보세요."}
              </li>
            ) : (
              filtered.map((item) => {
                const active = selected.some((s) => s.id === item.id);
                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      data-location-id={item.id}
                      // preventDefault on early pointer/mouse events keeps the
                      // filter input from stealing the first tap (IME / keyboard
                      // dismiss). pressLock prevents pointerdown+click double toggle.
                      onPointerDown={(e) => {
                        if (e.button !== 0) return;
                        e.preventDefault();
                        pressLocation(item);
                      }}
                      onMouseDown={(e) => {
                        if (e.button !== 0) return;
                        e.preventDefault();
                        pressLocation(item);
                      }}
                      onClick={(e) => {
                        e.preventDefault();
                        pressLocation(item);
                      }}
                      className={`flex w-full cursor-pointer touch-manipulation items-center justify-between px-3 py-2 text-left text-sm hover:bg-mist/80 ${
                        active ? "bg-leaf/10 text-leaf" : "text-ink"
                      }`}
                    >
                      <span>{item.name}</span>
                      <span className="text-xs text-ink/40">
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

        <div className="block text-sm">
          <span className="text-base font-semibold text-ink">음식 / 키워드</span>
          <input
            ref={queryInputRef}
            className="mt-2 w-full border border-ink/15 bg-white px-3 py-2 text-ink outline-none focus:border-leaf"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={`비우면 모든 음식 · 예: 삼겹살, 카페, 국밥`}
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
            onKeyDown={(e) => {
              // Ignore Enter while Korean IME composition is in progress.
              if (e.key === "Enter" && !e.nativeEvent.isComposing) {
                e.preventDefault();
                void runSearch();
              }
            }}
          />
          <p className="mt-1.5 text-xs text-ink/45">
            {query.trim()
              ? `「${query.trim()}」로 검색합니다.`
              : `비워 두면 모든 음식 종류(${DEFAULT_FOOD_QUERY})를 검색합니다.`}
          </p>
        </div>

        <button
          type="submit"
          disabled={loading}
          onPointerDown={(e) => {
            if (e.button !== 0 || loading) return;
            e.preventDefault();
            void runSearch();
          }}
          onMouseDown={(e) => {
            if (e.button !== 0 || loading) return;
            e.preventDefault();
            void runSearch();
          }}
          className="w-full cursor-pointer touch-manipulation bg-leaf px-4 py-2.5 text-sm font-medium text-white transition hover:bg-leaf/90 disabled:opacity-60 sm:w-auto"
        >
          {loading ? "검색 중…" : "검색"}
        </button>

        {error ? (
          <p className="text-sm text-clay" role="alert">
            {error}
          </p>
        ) : null}
        </form>
      </section>

      {result ? (
        <section className="mt-10 border-t border-ink/10 pt-6">
          <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-xl font-semibold text-ink">
              결과 {result.meta.result_count}곳
            </h2>
            <p className="text-xs text-ink/40">
              provider: {result.meta.provider_mode} · areas:{" "}
              {result.meta.area_count} · candidates: {result.meta.candidate_count}
              {` · radius: ${formatRadiusLabel(radiusM)}`}
            </p>
          </div>

          {result.notices.length > 0 ? (
            <ul className="mb-4 space-y-1 rounded-sm bg-mist/70 px-3 py-2 text-sm text-ink/65">
              {result.notices.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          ) : null}

          <div className="mb-4 flex flex-wrap gap-2" role="tablist" aria-label="평점 분류">
            {COVERAGE_TABS.map((tab) => {
              const active = coverageFilter === tab.id;
              const count = coverageCounts[tab.id];
              return (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  onClick={() => setCoverageFilter(tab.id)}
                  className={`border px-3 py-1.5 text-sm transition ${
                    active
                      ? "border-leaf bg-leaf text-white"
                      : "border-ink/15 bg-white text-ink hover:border-leaf/40"
                  }`}
                >
                  {tab.label}
                  <span className={`ml-1.5 tabular-nums ${active ? "text-white/80" : "text-ink/45"}`}>
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
          <p className="mb-4 text-xs text-ink/45">
            분류 기준: Kakao/Google에 숫자 평점이 있는지입니다.
          </p>

          {mapAreas.length > 0 ? (
            <div className="mb-6">
              <ResultsMapClient
                areas={mapAreas}
                restaurants={filteredResults}
                selectedRestaurantId={selectedRestaurantId}
                onSelectRestaurant={selectRestaurant}
              />
              <p className="mt-2 text-xs text-ink/45">
                지도는 현재 선택한 분류의 장소를 표시합니다. 카드 ↔ 마커 연동.
              </p>
            </div>
          ) : null}

          {filteredResults.length === 0 ? (
            <p className="text-sm text-ink/55">
              이 분류에 해당하는 식당이 없습니다. 다른 탭을 선택해 보세요.
            </p>
          ) : (
            <>
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-xs text-ink/50">
                <span>
                  {filteredResults.length}곳 중{" "}
                  {(currentPage - 1) * PAGE_SIZE + 1}–
                  {Math.min(currentPage * PAGE_SIZE, filteredResults.length)} 표시
                </span>
                <span>
                  {currentPage} / {totalPages} 페이지
                </span>
              </div>
              <div ref={listRef}>
                {pageResults.map((r) => (
                  <RestaurantCard
                    key={r.restaurant_id}
                    restaurant={r}
                    selected={r.restaurant_id === selectedRestaurantId}
                    onSelect={selectRestaurant}
                  />
                ))}
              </div>
              {totalPages > 1 ? (
                <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
                  <button
                    type="button"
                    disabled={currentPage <= 1}
                    onClick={() => goToPage(currentPage - 1)}
                    className="border border-ink/15 px-3 py-1.5 text-sm text-ink disabled:opacity-40"
                  >
                    이전
                  </button>
                  {Array.from({ length: totalPages }, (_, i) => i + 1)
                    .filter((p) => {
                      if (totalPages <= 7) return true;
                      return (
                        p === 1 ||
                        p === totalPages ||
                        Math.abs(p - currentPage) <= 1
                      );
                    })
                    .map((p, idx, arr) => {
                      const prev = arr[idx - 1];
                      const showEllipsis = prev != null && p - prev > 1;
                      return (
                        <span key={p} className="contents">
                          {showEllipsis ? (
                            <span className="px-1 text-ink/40">…</span>
                          ) : null}
                          <button
                            type="button"
                            onClick={() => goToPage(p)}
                            className={`min-w-9 border px-2 py-1.5 text-sm tabular-nums ${
                              p === currentPage
                                ? "border-leaf bg-leaf text-white"
                                : "border-ink/15 text-ink"
                            }`}
                          >
                            {p}
                          </button>
                        </span>
                      );
                    })}
                  <button
                    type="button"
                    disabled={currentPage >= totalPages}
                    onClick={() => goToPage(currentPage + 1)}
                    className="border border-ink/15 px-3 py-1.5 text-sm text-ink disabled:opacity-40"
                  >
                    다음
                  </button>
                </div>
              ) : null}
            </>
          )}
        </section>
      ) : selected.length > 0 ? (
        <section className="mt-8 border-t border-ink/10 pt-6">
          <p className="mb-2 text-sm text-ink/55">선택한 검색 영역 미리보기</p>
          <ResultsMapClient
            areas={mapAreas}
            restaurants={[]}
            selectedRestaurantId={null}
            onSelectRestaurant={() => undefined}
          />
        </section>
      ) : null}
    </div>
  );
}
