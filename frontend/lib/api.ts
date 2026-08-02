import type {
  City,
  LocationCatalogItem,
  LocationMode,
  LocationPayload,
  SearchResponse,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export async function fetchLocations(
  city: City,
  mode: LocationMode,
  options?: { nationwide?: boolean; q?: string },
): Promise<LocationCatalogItem[]> {
  const params = new URLSearchParams({ mode });
  if (
    (mode === "station" || mode === "street") &&
    options?.nationwide !== false
  ) {
    params.set("nationwide", "true");
  } else {
    params.set("city", city);
  }
  if (options?.q?.trim()) {
    params.set("q", options.q.trim());
  }
  const url = `${API_BASE}/api/locations?${params}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to load locations (${res.status})`);
  }
  return res.json();
}

export async function searchRestaurants(body: {
  city: City;
  mode: LocationMode;
  locations: LocationPayload[];
  query: string;
}): Promise<SearchResponse> {
  const res = await fetch(`${API_BASE}/api/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Search failed (${res.status})`);
  }
  return res.json();
}

export function toLocationPayload(
  item: LocationCatalogItem,
  radiusM: number = item.default_radius_m,
): LocationPayload {
  if (item.mode === "station") {
    return {
      type: "station",
      station_id: item.id,
      station_name: item.name,
      city: item.city,
      latitude: item.latitude,
      longitude: item.longitude,
      radius_m: radiusM,
    };
  }
  if (item.mode === "bus_stop") {
    return {
      type: "bus_stop",
      bus_stop_id: item.id,
      bus_stop_name: item.name,
      city: item.city,
      latitude: item.latitude,
      longitude: item.longitude,
      radius_m: radiusM,
    };
  }
  if (item.mode === "street") {
    return {
      type: "street",
      street_id: item.id,
      street_name: item.name,
      city: item.city,
      latitude: item.latitude,
      longitude: item.longitude,
      radius_m: radiusM,
    };
  }
  return {
    type: "neighborhood",
    neighborhood_id: item.id,
    neighborhood_name: item.name,
    city: item.city,
    latitude: item.latitude,
    longitude: item.longitude,
    radius_m: radiusM,
  };
}
