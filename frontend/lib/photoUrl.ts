/** Build browser-safe photo URLs that hit the LocalLens backend proxy only. */

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export function restaurantPhotoSrc(
  photoUrl: string | null | undefined,
): string | null {
  if (!photoUrl) return null;
  // Reject accidental absolute Google / credentialed URLs from the client.
  if (/^https?:\/\//i.test(photoUrl)) {
    try {
      const u = new URL(photoUrl);
      const api = new URL(API_BASE);
      if (u.origin !== api.origin) return null;
    } catch {
      return null;
    }
    return photoUrl;
  }
  if (!photoUrl.startsWith("/api/restaurants/photo")) return null;
  return `${API_BASE}${photoUrl}`;
}

export function photoSrcLooksSafe(src: string | null): boolean {
  if (!src) return true;
  if (src.includes("key=")) return false;
  if (/googleapis\.com/i.test(src)) return false;
  return src.includes("/api/restaurants/photo");
}
