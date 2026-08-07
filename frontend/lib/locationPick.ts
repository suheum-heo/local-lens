import type { LocationCatalogItem } from "./types";

/**
 * Resolve an auto-select candidate from the typed filter.
 *
 * Exact / 「역」-suffix matches are accepted only when the query uniquely
 * finishes that name. Prefixes like 「잠실」 must not steal 「잠실새내」.
 */
export function resolveLocationPick(
  query: string,
  items: LocationCatalogItem[],
): LocationCatalogItem | null {
  const q = query.trim();
  if (!q || items.length === 0) return null;

  const exact = items.find(
    (i) =>
      i.name === q ||
      i.name === `${q}역` ||
      i.name.toLowerCase() === q.toLowerCase(),
  );

  if (exact) {
    // Fully typed official name (e.g. 「잠실역」) — always accept.
    if (
      q === exact.name ||
      q.toLowerCase() === exact.name.toLowerCase()
    ) {
      return exact;
    }

    // Typed stem that maps via +역 (e.g. 「잠실」 → 「잠실역」). Reject when
    // another suggestion continues past that stem (「잠실새내역」).
    const stem = q.replace(/역$/, "");
    const hasLongerContinuation = items.some((i) => {
      if (i.id === exact.id) return false;
      const bare = i.name.replace(/역$/, "");
      return bare.startsWith(stem) && bare.length > stem.length;
    });
    if (hasLongerContinuation) return null;
    return exact;
  }

  if (items.length === 1) return items[0];
  return null;
}
