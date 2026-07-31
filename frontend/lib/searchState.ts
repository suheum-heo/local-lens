import type { City, LocationMode } from "./types";
import {
  DEFAULT_RADIUS_M,
  STATION_RADIUS_OPTIONS_M,
  type StationRadiusM,
} from "./constants";

/**
 * URL search-param helpers (optional / tests).
 * The live SearchPage no longer hydrates or auto-runs from the URL on refresh.
 */
export interface SearchStateParams {
  city: City;
  mode: LocationMode;
  locationIds: string[];
  radiusM: StationRadiusM;
  query: string;
  /** Legacy flag; SearchPage ignores this on load. */
  run: boolean;
}

const CITY_SET = new Set<string>([
  "seoul",
  "busan",
  "daegu",
  "incheon",
  "gwangju",
  "daejeon",
  "ulsan",
  "jeonju",
  "other",
]);

export function parseSearchParams(
  params: URLSearchParams,
): Partial<SearchStateParams> {
  const out: Partial<SearchStateParams> = {};

  const city = params.get("city");
  if (city && CITY_SET.has(city)) {
    out.city = city as City;
  }

  const mode = params.get("mode");
  if (mode === "station" || mode === "neighborhood") {
    out.mode = mode;
  }

  const locs = params.get("locs");
  if (locs) {
    out.locationIds = locs
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }

  const radius = Number(params.get("radius"));
  if (
    STATION_RADIUS_OPTIONS_M.includes(radius as StationRadiusM)
  ) {
    out.radiusM = radius as StationRadiusM;
  }

  const q = params.get("q");
  if (q != null && q !== "") {
    out.query = q;
  }

  out.run = params.get("run") === "1";

  return out;
}

export function buildSearchParams(state: {
  city: City;
  mode: LocationMode;
  locationIds: string[];
  radiusM: number;
  query: string;
  run?: boolean;
}): URLSearchParams {
  const params = new URLSearchParams();
  params.set("city", state.city);
  params.set("mode", state.mode);
  if (state.locationIds.length > 0) {
    params.set("locs", state.locationIds.join(","));
  }
  if (state.mode === "station") {
    params.set("radius", String(state.radiusM || DEFAULT_RADIUS_M));
  }
  if (state.query.trim()) {
    params.set("q", state.query.trim());
  }
  if (state.run) {
    params.set("run", "1");
  }
  return params;
}

export function writeSearchParamsToUrl(
  state: Parameters<typeof buildSearchParams>[0],
  replace = true,
): void {
  if (typeof window === "undefined") return;
  const params = buildSearchParams(state);
  const next = `${window.location.pathname}?${params.toString()}`;
  if (replace) {
    window.history.replaceState(null, "", next);
  } else {
    window.history.pushState(null, "", next);
  }
}
