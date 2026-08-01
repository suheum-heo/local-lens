import { googleMapUrl, kakaoMapUrl } from "@/lib/mapLinks";
import { formatDistanceMeters } from "@/lib/geo";
import type { Restaurant, RestaurantLabel } from "@/lib/types";

const LABEL_KO: Record<RestaurantLabel, string> = {
  consensus_pick: "Consensus Pick",
  local_favorite: "Local Favorite",
  global_favorite: "Global Favorite",
  limited_data: "Limited Data",
};

const LABEL_STYLE: Record<RestaurantLabel, string> = {
  consensus_pick: "bg-leaf text-white",
  local_favorite: "bg-leaf/10 text-leaf",
  global_favorite: "bg-ink/90 text-white",
  limited_data: "bg-mist text-ink/60",
};

function RatingPill({
  label,
  rating,
  count,
  empty,
}: {
  label: string;
  rating: number | null;
  count: number | null;
  empty: string;
}) {
  if (rating == null) {
    return (
      <div className="min-w-0 rounded-xl bg-mist/70 px-3 py-2.5">
        <div className="text-[11px] font-medium uppercase tracking-wide text-ink/40">
          {label}
        </div>
        <div className="mt-0.5 text-sm text-ink/45">{empty}</div>
      </div>
    );
  }
  return (
    <div className="min-w-0 rounded-xl bg-mist/70 px-3 py-2.5">
      <div className="text-[11px] font-medium uppercase tracking-wide text-ink/40">
        {label}
      </div>
      <div className="mt-0.5 flex items-baseline gap-1.5">
        <span className="text-lg font-semibold tabular-nums tracking-tight text-ink">
          {rating.toFixed(1)}
        </span>
        <span className="text-xs text-ink/40">★</span>
        {count != null ? (
          <span className="text-xs tabular-nums text-ink/40">
            {count.toLocaleString()}
          </span>
        ) : null}
      </div>
    </div>
  );
}

export function RestaurantCard({
  restaurant,
  selected = false,
  onSelect,
  distanceM = null,
}: {
  restaurant: Restaurant;
  selected?: boolean;
  onSelect?: (restaurantId: string) => void;
  distanceM?: number | null;
}) {
  const { scores, kakao, google, label, match } = restaurant;
  const googleRating = scores.global.rating ?? google?.rating ?? null;
  const googleCount =
    scores.global.review_count ?? google?.user_rating_count ?? null;
  const kakaoRating = scores.local.rating ?? kakao.rating;
  const kakaoCount = scores.local.review_count ?? kakao.review_count;
  const recommendation = scores.consensus.score ?? scores.local.score ?? scores.global.score;

  const unmatched = !match.matched;
  const statusBadge = label
    ? { text: LABEL_KO[label], className: LABEL_STYLE[label] }
    : unmatched
      ? { text: "Google Unmatched", className: "bg-mist text-ink/55" }
      : null;

  const categoryShort = restaurant.category?.split(">").pop()?.trim() ?? null;

  return (
    <article
      id={`restaurant-${restaurant.restaurant_id}`}
      role={onSelect ? "button" : undefined}
      tabIndex={onSelect ? 0 : undefined}
      onClick={() => onSelect?.(restaurant.restaurant_id)}
      onKeyDown={(e) => {
        if (!onSelect) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(restaurant.restaurant_id);
        }
      }}
      className={`group rounded-card border bg-card p-4 shadow-soft outline-none transition duration-200 ease-soft sm:p-5 ${
        selected
          ? "border-leaf/30 ring-2 ring-leaf/20 shadow-lift"
          : "border-ink/[0.06] hover:-translate-y-0.5 hover:border-ink/10 hover:shadow-lift"
      } ${onSelect ? "cursor-pointer" : ""}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-lg font-semibold tracking-tight text-ink sm:text-xl">
            {restaurant.name}
          </h3>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-ink/45">
            {distanceM != null ? (
              <span className="font-medium tabular-nums text-ink/55">
                {formatDistanceMeters(distanceM)}
              </span>
            ) : null}
            {distanceM != null && categoryShort ? (
              <span className="text-ink/20">·</span>
            ) : null}
            {categoryShort ? <span>{categoryShort}</span> : null}
          </div>
        </div>
        {statusBadge ? (
          <span
            className={`shrink-0 rounded-chip px-2.5 py-1 text-[11px] font-semibold tracking-wide ${statusBadge.className}`}
          >
            {statusBadge.text}
          </span>
        ) : null}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2">
        <RatingPill
          label="Kakao"
          rating={kakaoRating}
          count={kakaoCount}
          empty={
            scores.local.availability === "insufficient_data"
              ? "리뷰 부족"
              : "보강 불가"
          }
        />
        <RatingPill
          label="Google"
          rating={googleRating}
          count={googleCount}
          empty={
            scores.global.availability === "unmatched"
              ? "매칭 없음"
              : "데이터 없음"
          }
        />
      </div>

      <div className="mt-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-[11px] font-medium uppercase tracking-wide text-ink/35">
            Recommendation
          </div>
          <div className="mt-0.5 text-2xl font-semibold tabular-nums tracking-tight text-ink">
            {recommendation != null ? recommendation.toFixed(1) : "—"}
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <a
            href={kakaoMapUrl(restaurant)}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="rounded-chip border border-ink/10 bg-white px-3 py-1.5 text-xs font-medium text-ink/70 transition hover:border-ink/20 hover:bg-mist/60 hover:text-ink"
          >
            Kakao
          </a>
          <a
            href={googleMapUrl(restaurant)}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="rounded-chip border border-ink/10 bg-white px-3 py-1.5 text-xs font-medium text-ink/70 transition hover:border-ink/20 hover:bg-mist/60 hover:text-ink"
          >
            Google
          </a>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onSelect?.(restaurant.restaurant_id);
            }}
            className="rounded-chip bg-leaf/10 px-3 py-1.5 text-xs font-semibold text-leaf transition hover:bg-leaf/15"
          >
            Map
          </button>
        </div>
      </div>
    </article>
  );
}
