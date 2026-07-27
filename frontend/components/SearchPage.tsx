"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchLocations, searchRestaurants, toLocationPayload } from "@/lib/api";
import type {
  City,
  LocationCatalogItem,
  LocationMode,
  SearchResponse,
} from "@/lib/types";
import { RestaurantCard } from "./RestaurantCard";

const CITIES: { value: City; label: string }[] = [
  { value: "seoul", label: "서울" },
  { value: "ulsan", label: "울산" },
  { value: "jeonju", label: "전주" },
  { value: "busan", label: "부산" },
];

export function SearchPage() {
  const [city, setCity] = useState<City>("seoul");
  const [mode, setMode] = useState<LocationMode>("station");
  const [catalog, setCatalog] = useState<LocationCatalogItem[]>([]);
  const [selected, setSelected] = useState<LocationCatalogItem[]>([]);
  const [filter, setFilter] = useState("");
  const [query, setQuery] = useState("삼겹살");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SearchResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    setSelected([]);
    setResult(null);
    fetchLocations(city, mode)
      .then((items) => {
        if (!cancelled) setCatalog(items);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [city, mode]);

  // Prefer neighborhood mode for Ulsan / Jeonju in mock catalog
  useEffect(() => {
    if (city === "ulsan" || city === "jeonju") {
      setMode("neighborhood");
    } else if (city === "seoul") {
      setMode("station");
    }
  }, [city]);

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return catalog;
    return catalog.filter(
      (item) =>
        item.name.toLowerCase().includes(q) ||
        (item.name_en?.toLowerCase().includes(q) ?? false),
    );
  }, [catalog, filter]);

  function toggleLocation(item: LocationCatalogItem) {
    setSelected((prev) => {
      if (prev.some((s) => s.id === item.id)) {
        return prev.filter((s) => s.id !== item.id);
      }
      return [...prev, item];
    });
  }

  function removeLocation(id: string) {
    setSelected((prev) => prev.filter((s) => s.id !== id));
  }

  async function onSearch() {
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
    try {
      const data = await searchRestaurants({
        city,
        mode,
        locations: selected.map(toLocationPayload),
        query: query.trim(),
      });
      setResult(data);
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 sm:py-12">
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

        <div>
          <label className="block text-sm text-ink/60">위치 검색</label>
          <input
            className="mt-1 w-full border border-ink/15 bg-white px-3 py-2 text-ink outline-none focus:border-leaf"
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
                      {item.name_en ? (
                        <span className="text-xs text-ink/40">{item.name_en}</span>
                      ) : null}
                    </button>
                  </li>
                );
              })
            )}
          </ul>
        </div>

        {selected.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {selected.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => removeLocation(item.id)}
                className="inline-flex items-center gap-1.5 border border-ink/15 bg-mist/50 px-2.5 py-1 text-sm text-ink"
              >
                {item.name}
                <span className="text-ink/40" aria-hidden>
                  ×
                </span>
              </button>
            ))}
          </div>
        ) : null}

        <label className="block text-sm">
          <span className="text-ink/60">검색어 (카테고리 / 음식)</span>
          <input
            className="mt-1 w-full border border-ink/15 bg-white px-3 py-2 text-ink outline-none focus:border-leaf"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="예: 삼겹살"
            onKeyDown={(e) => {
              if (e.key === "Enter") void onSearch();
            }}
          />
        </label>

        <button
          type="button"
          onClick={() => void onSearch()}
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
            </p>
          </div>

          {result.notices.length > 0 ? (
            <ul className="mb-4 space-y-1 rounded-sm bg-mist/70 px-3 py-2 text-sm text-ink/65">
              {result.notices.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          ) : null}

          {result.results.length === 0 ? (
            <p className="text-sm text-ink/55">
              선택한 영역에서 식당을 찾지 못했습니다. 위치나 검색어를 바꿔 보세요.
            </p>
          ) : (
            <div>
              {result.results.map((r) => (
                <RestaurantCard key={r.restaurant_id} restaurant={r} />
              ))}
            </div>
          )}
        </section>
      ) : null}
    </div>
  );
}
