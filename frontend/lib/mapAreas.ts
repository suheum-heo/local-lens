import type { LocationCatalogItem, LocationMode } from "./types";

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
  _mode: LocationMode,
): SearchAreaView[] {
  return selected.map((item) => ({
    id: item.id,
    name: item.name,
    latitude: item.latitude,
    longitude: item.longitude,
    radius_m: radiusM,
  }));
}
