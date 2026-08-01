/** Shared search UI constants. */

import type { City, LocationMode } from "./types";

export const SEARCH_RADIUS_OPTIONS_M = [500, 1000, 1500, 2000] as const;
/** @deprecated Use SEARCH_RADIUS_OPTIONS_M */
export const STATION_RADIUS_OPTIONS_M = SEARCH_RADIUS_OPTIONS_M;
export type StationRadiusM = (typeof SEARCH_RADIUS_OPTIONS_M)[number];
export const DEFAULT_RADIUS_M: StationRadiusM = 1000;

/** Sent to the API when the food keyword field is left empty. */
export const DEFAULT_FOOD_QUERY = "맛집";

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

const LOCATION_EXAMPLES: Record<
  City,
  Record<LocationMode, string>
> = {
  seoul: {
    station: "합정역, 강남역, 홍대입구역",
    bus_stop: "합정역, 홍대입구역, 신촌역",
    neighborhood: "합정동, 서교동, 역삼동",
  },
  busan: {
    station: "서면역, 해운대역, 남포역",
    bus_stop: "서면역, 해운대역, 남포동",
    neighborhood: "전포동, 우동, 남포동",
  },
  incheon: {
    station: "부평역, 주안역, 송도역",
    bus_stop: "부평역, 주안역, 인천터미널",
    neighborhood: "부평동, 구월동, 연수동",
  },
  daegu: {
    station: "동대구역, 반월당역, 중앙로역",
    bus_stop: "동대구역, 반월당, 중앙로",
    neighborhood: "삼덕동, 범어동, 두류동",
  },
  daejeon: {
    station: "중앙로역, 시청역, 유성온천역",
    bus_stop: "대전역, 시청, 유성온천",
    neighborhood: "둔산동, 궁동, 오류동",
  },
  gwangju: {
    station: "상무역, 금남로4가역, 남광주역",
    bus_stop: "상무역, 금남로, 남광주",
    neighborhood: "치평동, 충장로, 봉선동",
  },
  ulsan: {
    station: "울산역, 태화강역",
    bus_stop: "삼산동, 공업탑, 울산역",
    neighborhood: "삼산동, 달동, 성남동",
  },
  jeonju: {
    station: "전주역",
    bus_stop: "한옥마을, 전주역, 객사",
    neighborhood: "효자동, 서신동, 고사동",
  },
  other: {
    station: "역 이름",
    bus_stop: "정류장 이름",
    neighborhood: "동 이름",
  },
};

export function locationSearchPlaceholder(
  city: City,
  mode: LocationMode,
): string {
  const examples = LOCATION_EXAMPLES[city]?.[mode] ?? LOCATION_EXAMPLES.other[mode];
  if (mode === "station") {
    return `${CITY_LABEL_SHORT[city] ?? ""} 지하철역 검색 (예: ${examples})…`.trim();
  }
  if (mode === "bus_stop") {
    return `버스정류장 검색 (예: ${examples})…`;
  }
  return `동 이름 검색 (예: ${examples})…`;
}

const CITY_LABEL_SHORT: Record<string, string> = {
  seoul: "서울",
  busan: "부산",
  incheon: "인천",
  daegu: "대구",
  daejeon: "대전",
  gwangju: "광주",
  ulsan: "울산",
  jeonju: "전주",
  other: "",
};

export function formatRadiusLabel(meters: number): string {
  if (meters >= 1000) {
    const km = meters / 1000;
    return Number.isInteger(km) ? `${km} km` : `${km} km`;
  }
  return `${meters} m`;
}
