import type { RatingCoverage, RestaurantLabel } from "./types";

/** Visual status tokens aligned with the LocalLens design guide. */
export const STATUS = {
  consensus: { hex: "#22C55E", soft: "#DCFCE7", text: "#15803D" },
  global: { hex: "#3B82F6", soft: "#DBEAFE", text: "#1D4ED8" },
  local: { hex: "#F97316", soft: "#FFEDD5", text: "#C2410C" },
  limited: { hex: "#6366F1", soft: "#E0E7FF", text: "#4338CA" },
  unmatched: { hex: "#94A3B8", soft: "#F1F5F9", text: "#475569" },
} as const;

export type StatusKey = keyof typeof STATUS;

export function statusFromLabel(
  label: RestaurantLabel | null | undefined,
): StatusKey {
  switch (label) {
    case "consensus_pick":
      return "consensus";
    case "global_favorite":
      return "global";
    case "local_favorite":
      return "local";
    case "limited_data":
      return "limited";
    default:
      return "limited";
  }
}

export function statusFromCoverage(coverage: RatingCoverage): StatusKey {
  switch (coverage) {
    case "both":
      return "consensus";
    case "google_only":
      return "global";
    case "kakao_only":
      return "local";
    case "none":
    default:
      return "limited";
  }
}

export const LABEL_TEXT: Record<RestaurantLabel, string> = {
  consensus_pick: "Consensus Pick",
  local_favorite: "Local Favorite",
  global_favorite: "Global Favorite",
  limited_data: "Limited Data",
};

export const LABEL_BADGE_CLASS: Record<RestaurantLabel, string> = {
  consensus_pick: "bg-brand text-white",
  local_favorite: "bg-local text-white",
  global_favorite: "bg-global text-white",
  limited_data: "bg-violet text-white",
};
