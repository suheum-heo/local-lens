import type { Restaurant } from "@/lib/types";

/** Kakao Map place page (falls back to id-based URL). */
export function kakaoMapUrl(restaurant: Restaurant): string {
  const fromApi = restaurant.kakao.place_url?.trim();
  if (fromApi) return fromApi;
  return `https://place.map.kakao.com/${restaurant.kakao.kakao_place_id}`;
}

/**
 * Google Maps place link when matched; otherwise name+address search.
 * Always returns a usable URL so both map actions can be shown.
 */
export function googleMapUrl(restaurant: Restaurant): string {
  const placeId = restaurant.google?.google_place_id?.trim();
  if (placeId) {
    return `https://www.google.com/maps/place/?q=place_id:${encodeURIComponent(placeId)}`;
  }
  const address = restaurant.road_address || restaurant.address || "";
  const query = [restaurant.name, address].filter(Boolean).join(" ");
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
}
