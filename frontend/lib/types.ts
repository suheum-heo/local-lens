export type City =
  | "seoul"
  | "busan"
  | "daegu"
  | "incheon"
  | "gwangju"
  | "daejeon"
  | "ulsan"
  | "jeonju"
  | "other";

export type LocationMode = "station" | "neighborhood";

export type DataAvailability =
  | "available"
  | "insufficient_data"
  | "unavailable"
  | "unmatched";

export type RestaurantLabel =
  | "consensus_pick"
  | "local_favorite"
  | "global_favorite"
  | "limited_data";

export type RatingCoverage =
  | "both"
  | "kakao_only"
  | "google_only"
  | "none";

export interface LocationCatalogItem {
  id: string;
  name: string;
  name_en: string | null;
  city: City;
  latitude: number;
  longitude: number;
  mode: LocationMode;
  default_radius_m: number;
}

export interface PlatformSignal {
  availability: DataAvailability;
  rating: number | null;
  review_count: number | null;
  score: number | null;
  explanation: string | null;
}

export interface ScoreBundle {
  local: PlatformSignal;
  global: PlatformSignal;
  consensus: PlatformSignal;
}

export interface Restaurant {
  restaurant_id: string;
  name: string;
  address: string | null;
  road_address: string | null;
  latitude: number;
  longitude: number;
  category: string | null;
  kakao: {
    kakao_place_id: string;
    name: string;
    rating: number | null;
    review_count: number | null;
    place_url: string | null;
  };
  google: {
    google_place_id: string;
    name: string;
    rating: number | null;
    user_rating_count: number | null;
  } | null;
  match: {
    confidence: number;
    confidence_level: string;
    matched: boolean;
    reason: string | null;
  };
  scores: ScoreBundle;
  label: RestaurantLabel | null;
  rating_coverage: RatingCoverage;
  source_area_ids?: string[];
}

export interface SearchResponse {
  results: Restaurant[];
  meta: {
    provider_mode: string;
    area_count: number;
    candidate_count: number;
    result_count: number;
    query: string;
    city: City;
    mode: LocationMode;
    api_calls?: {
      kakao_keyword: number;
      google_search_text: number;
      google_details: number;
      total: number;
    } | null;
  };
  notices: string[];
}

export interface StationLocationPayload {
  type: "station";
  station_id: string;
  station_name: string;
  city: City;
  latitude: number;
  longitude: number;
  radius_m: number;
}

export interface NeighborhoodLocationPayload {
  type: "neighborhood";
  neighborhood_id: string;
  neighborhood_name: string;
  city: City;
  latitude: number;
  longitude: number;
  radius_m: number;
}

export type LocationPayload =
  | StationLocationPayload
  | NeighborhoodLocationPayload;
