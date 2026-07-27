import type { LocationCatalogItem } from "./types";

export interface SearchAreaView {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  radius_m: number;
}

export function areasFromSelection(
  selected: LocationCatalogItem[],
  radiusM: number,
  mode: "station" | "neighborhood",
): SearchAreaView[] {
  return selected.map((item) => ({
    id: item.id,
    name: item.name,
    latitude: item.latitude,
    longitude: item.longitude,
    radius_m: mode === "station" ? radiusM : item.default_radius_m,
  }));
}
