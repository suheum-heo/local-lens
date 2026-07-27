/** Shared search UI constants. */

export const STATION_RADIUS_OPTIONS_M = [500, 1000, 1500, 2000] as const;
export type StationRadiusM = (typeof STATION_RADIUS_OPTIONS_M)[number];
export const DEFAULT_RADIUS_M: StationRadiusM = 1000;

export const CITIES = [
  { value: "seoul" as const, label: "서울" },
  { value: "ulsan" as const, label: "울산" },
  { value: "jeonju" as const, label: "전주" },
  { value: "busan" as const, label: "부산" },
];

export function formatRadiusLabel(meters: number): string {
  if (meters >= 1000) {
    const km = meters / 1000;
    return Number.isInteger(km) ? `${km} km` : `${km} km`;
  }
  return `${meters} m`;
}
