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
  SearchResponse,
} from "@/lib/types";
import { RestaurantCard } from "./RestaurantCard";
import { ResultsMapClient } from "./ResultsMapClient";
import { areasFromSelection } from "@/lib/mapAreas";

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
  const [hydrated, setHydrated] = useState(false);
  const pendingLocationIds = useRef<string[] | null>(null);
  const shouldAutoSearch = useRef(false);
  const skipNextCatalogClear = useRef(false);
  const listRef = useRef<HTMLDivElement | null>(null);

  // Restore search config from URL once on mount.
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

  // Prefer neighborhood mode for cities without subway catalog — but not when
  // restoring a shared URL that already set mode.
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

  // Keep URL in sync as the form changes (without forcing a search).
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

  // Auto-run when landing on a shareable URL with run=1.
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

          {mapAreas.length > 0 ? (
            <div className="mb-6">
              <ResultsMapClient
                areas={mapAreas}
                restaurants={result.results}
                selectedRestaurantId={selectedRestaurantId}
                onSelectRestaurant={selectRestaurant}
              />
              <p className="mt-2 text-xs text-ink/45">
                지도를 탭하면 해당 식당 카드가 강조되고, 카드를 누르면 마커로
                이동합니다.
              </p>
            </div>
          ) : null}

          {result.results.length === 0 ? (
            <p className="text-sm text-ink/55">
              선택한 영역에서 식당을 찾지 못했습니다. 반경·위치·검색어를 바꿔
              보세요.
            </p>
          ) : (
            <div ref={listRef}>
              {result.results.map((r) => (
                <RestaurantCard
                  key={r.restaurant_id}
                  restaurant={r}
                  selected={r.restaurant_id === selectedRestaurantId}
                  onSelect={selectRestaurant}
                />
              ))}
            </div>
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
