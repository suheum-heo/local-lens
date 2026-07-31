"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchLocations, searchRestaurants, toLocationPayload } from "@/lib/api";
import {
  CITIES,
  DEFAULT_RADIUS_M,
  STATION_RADIUS_OPTIONS_M,
  formatRadiusLabel,
  type StationRadiusM,
} from "@/lib/constants";
import {
  parseSearchParams,
  writeSearchParamsToUrl,
} from "@/lib/searchState";
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
  const [query, setQuery] = useState("삼겹살");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [selectedRestaurantId, setSelectedRestaurantId] = useState<
    string | null
  >(null);
  const [coverageFilter, setCoverageFilter] = useState<CoverageFilter>("all");
  const [page, setPage] = useState(1);
  const [hydrated, setHydrated] = useState(false);
  const pendingLocationIds = useRef<string[] | null>(null);
  const shouldAutoSearch = useRef(false);
  const skipNextCatalogClear = useRef(false);
  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const parsed = parseSearchParams(new URLSearchParams(window.location.search));
    if (parsed.city) setCity(parsed.city);
    if (parsed.mode) {
      setMode(parsed.mode);
      skipNextCatalogClear.current = true;
    } else if (parsed.city === "ulsan" || parsed.city === "jeonju") {
      setMode("neighborhood");
      skipNextCatalogClear.current = true;
    }
    if (parsed.radiusM) setRadiusM(parsed.radiusM);
    if (parsed.query) setQuery(parsed.query);
    if (parsed.locationIds?.length) {
      pendingLocationIds.current = parsed.locationIds;
      skipNextCatalogClear.current = true;
    }
    shouldAutoSearch.current = Boolean(parsed.run && parsed.locationIds?.length);
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    if (skipNextCatalogClear.current) return;
    if (city === "ulsan" || city === "jeonju") {
      setMode("neighborhood");
    } else if (city === "seoul") {
      setMode("station");
    }
  }, [city, hydrated]);

  useEffect(() => {
    if (!hydrated) return;
    let cancelled = false;

    const preserveSelection = skipNextCatalogClear.current;
    if (!preserveSelection) {
      setSelected([]);
      setResult(null);
      setSelectedRestaurantId(null);
    }

    fetchLocations(city, mode)
      .then((items) => {
        if (cancelled) return;
        setCatalog(items);
        const pending = pendingLocationIds.current;
        if (pending?.length) {
          const restored = items.filter((item) => pending.includes(item.id));
          setSelected(restored);
          pendingLocationIds.current = null;
        }
        skipNextCatalogClear.current = false;
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });

    return () => {
      cancelled = true;
    };
  }, [city, mode, hydrated]);

  const syncUrl = useCallback(
    (run = false) => {
      writeSearchParamsToUrl({
        city,
        mode,
        locationIds: selected.map((s) => s.id),
        radiusM,
        query,
        run,
      });
    },
    [city, mode, selected, radiusM, query],
  );

  useEffect(() => {
    if (!hydrated) return;
    syncUrl(Boolean(result));
  }, [hydrated, syncUrl, result]);

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return catalog;
    return catalog.filter(
      (item) =>
        item.name.toLowerCase().includes(q) ||
        (item.name_en?.toLowerCase().includes(q) ?? false),
    );
  }, [catalog, filter]);

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

  function toggleLocation(item: LocationCatalogItem) {
    setSelected((prev) => {
      if (prev.some((s) => s.id === item.id)) {
        return prev.filter((s) => s.id !== item.id);
      }
      return [...prev, item];
    });
    setFilter("");
  }

  function removeLocation(id: string) {
    setSelected((prev) => prev.filter((s) => s.id !== id));
  }

  const runSearch = useCallback(async () => {
    setError(null);
    if (selected.length === 0) {
      setError("검색할 위치를 하나 이상 선택하세요.");
      return;
    }
    if (!query.trim()) {
      setError("검색어를 입력하세요.");
      return;
    }
    setLoading(true);
    setSelectedRestaurantId(null);
    setCoverageFilter("all");
    setPage(1);
    try {
      const data = await searchRestaurants({
        city,
        mode,
        locations: selected.map((item) =>
          toLocationPayload(item, mode === "station" ? radiusM : undefined),
        ),
        query: query.trim(),
      });
      setResult(data);
      writeSearchParamsToUrl({
        city,
        mode,
        locationIds: selected.map((s) => s.id),
        radiusM,
        query,
        run: true,
      });
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }, [city, mode, selected, radiusM, query]);

  useEffect(() => {
    if (!hydrated || !shouldAutoSearch.current) return;
    if (selected.length === 0) return;
    shouldAutoSearch.current = false;
    void runSearch();
  }, [hydrated, selected, runSearch]);

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

      <section className="space-y-4 border-t border-ink/10 pt-6">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="text-ink/60">도시</span>
            <select
              className="mt-1 w-full border border-ink/15 bg-white px-3 py-2 text-ink outline-none focus:border-leaf"
              value={city}
              onChange={(e) => setCity(e.target.value as City)}
            >
              {CITIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm">
            <span className="text-ink/60">위치 유형</span>
            <select
              className="mt-1 w-full border border-ink/15 bg-white px-3 py-2 text-ink outline-none focus:border-leaf"
              value={mode}
              onChange={(e) => setMode(e.target.value as LocationMode)}
            >
              <option value="station">지하철역</option>
              <option value="neighborhood">동네 / 행정동</option>
            </select>
          </label>
        </div>

        {mode === "station" ? (
          <fieldset>
            <legend className="text-sm text-ink/60">검색 반경</legend>
            <div className="mt-2 flex flex-wrap gap-2">
              {STATION_RADIUS_OPTIONS_M.map((r) => {
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
              선택한 모든 역에 동일 반경이 적용됩니다. 기본값 1 km.
            </p>
          </fieldset>
        ) : (
          <p className="text-xs text-ink/45">
            동네 검색은 기본 반경 1 km를 사용합니다.
          </p>
        )}

        <div>
          <label className="block text-sm text-ink/60">
            {mode === "station" ? "역 선택" : "동네 선택"}
          </label>

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
            className="mt-2 w-full border border-ink/15 bg-white px-3 py-2 text-ink outline-none focus:border-leaf"
            placeholder={
              mode === "station" ? "역 이름 검색…" : "동네 이름 검색…"
            }
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          <ul className="mt-2 max-h-40 overflow-auto border border-ink/10 bg-white">
            {filtered.length === 0 ? (
              <li className="px-3 py-2 text-sm text-ink/45">
                이 도시/유형에 대한 카탈로그가 없습니다.
              </li>
            ) : (
              filtered.map((item) => {
                const active = selected.some((s) => s.id === item.id);
                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      onClick={() => toggleLocation(item)}
                      className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-mist/80 ${
                        active ? "bg-leaf/10 text-leaf" : "text-ink"
                      }`}
                    >
                      <span>{item.name}</span>
                      <span className="text-xs text-ink/40">
                        {active ? "선택됨" : item.name_en}
                      </span>
                    </button>
                  </li>
                );
              })
            )}
          </ul>
        </div>

        <label className="block text-sm">
          <span className="text-ink/60">검색어 (카테고리 / 음식)</span>
          <input
            className="mt-1 w-full border border-ink/15 bg-white px-3 py-2 text-ink outline-none focus:border-leaf"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="예: 삼겹살"
            onKeyDown={(e) => {
              if (e.key === "Enter") void runSearch();
            }}
          />
        </label>

        <button
          type="button"
          onClick={() => void runSearch()}
          disabled={loading}
          className="w-full bg-leaf px-4 py-2.5 text-sm font-medium text-white transition hover:bg-leaf/90 disabled:opacity-60 sm:w-auto"
        >
          {loading ? "검색 중…" : "Search"}
        </button>

        {error ? (
          <p className="text-sm text-clay" role="alert">
            {error}
          </p>
        ) : null}
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
              {mode === "station" ? ` · radius: ${formatRadiusLabel(radiusM)}` : ""}
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
            분류 기준: Kakao/Google에 <em>숫자 평점</em>이 있는지. Kakao Local
            API는 평점을 주지 않아 live에서는 대부분 &quot;구글만&quot;으로
            보입니다.
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
