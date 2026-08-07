import type { LocationCatalogItem } from "./types";

function isExactNameMatch(item: LocationCatalogItem, q: string): boolean {
  return (
    item.name === q ||
    item.name === `${q}역` ||
    item.name.toLowerCase() === q.toLowerCase()
  );
}

/**
 * Resolve an auto-select candidate from the typed filter.
 *
 * Exact / 「역」-suffix matches are accepted only when the query uniquely
 * finishes that name. Prefixes like 「잠실」 must not steal 「잠실새내」.
 * Duplicate names across cities (e.g. 종합운동장역) never auto-select.
 */
export function resolveLocationPick(
  query: string,
  items: LocationCatalogItem[],
): LocationCatalogItem | null {
  const q = query.trim();
  if (!q || items.length === 0) return null;

  const exactMatches = items.filter((i) => isExactNameMatch(i, q));
  if (exactMatches.length > 1) {
    // Same station name in multiple cities — user must pick explicitly.
    return null;
  }

  const exact = exactMatches[0];
  if (exact) {
    // Fully typed official name (e.g. 「잠실역」).
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
