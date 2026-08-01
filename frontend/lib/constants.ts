/** Shared search UI constants. */

export const SEARCH_RADIUS_OPTIONS_M = [500, 1000, 1500, 2000] as const;
/** @deprecated Use SEARCH_RADIUS_OPTIONS_M */
export const STATION_RADIUS_OPTIONS_M = SEARCH_RADIUS_OPTIONS_M;
export type StationRadiusM = (typeof SEARCH_RADIUS_OPTIONS_M)[number];
export const DEFAULT_RADIUS_M: StationRadiusM = 1000;

export const CITIES = [
  { value: "seoul" as const, label: "서울/수도권" },
  { value: "busan" as const, label: "부산" },
  { value: "incheon" as const, label: "인천" },
  { value: "daegu" as const, label: "대구" },
  { value: "daejeon" as const, label: "대전" },
  { value: "gwangju" as const, label: "광주" },
  { value: "ulsan" as const, label: "울산" },
  { value: "jeonju" as const, label: "전주" },
];

export const LOCATION_MODES = [
  { value: "station" as const, label: "지하철역" },
  { value: "bus_stop" as const, label: "버스정류장" },
  { value: "neighborhood" as const, label: "동 / 동네" },
];

export function formatRadiusLabel(meters: number): string {
  if (meters >= 1000) {
    const km = meters / 1000;
    return Number.isInteger(km) ? `${km} km` : `${km} km`;
  }
  return `${meters} m`;
}
