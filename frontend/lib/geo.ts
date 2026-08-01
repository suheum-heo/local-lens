/** Client-side geo helpers (no backend dependency). */

export function haversineMeters(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number,
): number {
  const r = 6_371_000;
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dp = ((lat2 - lat1) * Math.PI) / 180;
  const dl = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dp / 2) ** 2 +
    Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * r * Math.asin(Math.min(1, Math.sqrt(a)));
}

export function formatDistanceMeters(meters: number): string {
  if (meters < 1000) return `${Math.round(meters)} m`;
  const km = meters / 1000;
  return km < 10 ? `${km.toFixed(1)} km` : `${Math.round(km)} km`;
}

export function nearestDistanceMeters(
  latitude: number,
  longitude: number,
  origins: { latitude: number; longitude: number }[],
): number | null {
  if (origins.length === 0) return null;
  let best = Infinity;
  for (const o of origins) {
    const d = haversineMeters(latitude, longitude, o.latitude, o.longitude);
    if (d < best) best = d;
  }
  return Number.isFinite(best) ? best : null;
}
