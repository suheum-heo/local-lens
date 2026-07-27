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
): Promise<LocationCatalogItem[]> {
  const url = `${API_BASE}/api/locations?city=${city}&mode=${mode}`;
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
  return {
    type: "neighborhood",
    neighborhood_id: item.id,
    neighborhood_name: item.name,
    city: item.city,
    latitude: item.latitude,
    longitude: item.longitude,
    radius_m: item.default_radius_m,
  };
}
