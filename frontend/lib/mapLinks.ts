import type { Restaurant } from "@/lib/types";

/** Kakao Map place page (falls back to id-based URL). */
export function kakaoMapUrl(restaurant: Restaurant): string {
  const fromApi = restaurant.kakao.place_url?.trim();
  if (fromApi) return fromApi;
  return `https://place.map.kakao.com/${restaurant.kakao.kakao_place_id}`;
}

/**
 * Google Maps link that works on desktop and iOS (Google Maps app).
 *
 * Avoid `maps/place/?q=place_id:` — iOS Maps opens that and shows
 * "No results found". Use the official Search URL with query_place_id.
 * @see https://developers.google.com/maps/documentation/urls/get-started#search-action
 */
export function googleMapUrl(restaurant: Restaurant): string {
  const placeId = restaurant.google?.google_place_id?.trim();
  const address = restaurant.road_address || restaurant.address || "";
  const nameQuery = [restaurant.name, address].filter(Boolean).join(" ");
  const coordQuery =
    Number.isFinite(restaurant.latitude) && Number.isFinite(restaurant.longitude)
      ? `${restaurant.latitude},${restaurant.longitude}`
      : "";

  if (placeId) {
    const params = new URLSearchParams({ api: "1" });
    // Prefer name+address; coords are a solid iOS fallback for place details.
    params.set("query", nameQuery || coordQuery || placeId);
    params.set("query_place_id", placeId);
    return `https://www.google.com/maps/search/?${params.toString()}`;
  }

  const query = nameQuery || coordQuery || restaurant.name;
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
}
