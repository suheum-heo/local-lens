import type { RatingCoverage, Restaurant, RestaurantLabel } from "@/lib/types";

const LABEL_KO: Record<RestaurantLabel, string> = {
  consensus_pick: "Consensus Pick",
  local_favorite: "Local Favorite",
  global_favorite: "Global Favorite",
  limited_data: "Limited Data",
};

const COVERAGE_KO: Record<RatingCoverage, string> = {
  both: "양쪽 평점",
  kakao_only: "카카오만",
  google_only: "구글만",
  none: "평점 없음",
};

function ScoreCell({
  title,
  score,
  explanation,
}: {
  title: string;
  score: number | null;
  explanation: string | null;
}) {
  return (
    <div className="min-w-0">
      <div className="text-xs uppercase tracking-wide text-ink/50">{title}</div>
      <div className="mt-0.5 font-semibold tabular-nums text-ink">
        {score != null ? score : "—"}
      </div>
      {score == null && explanation ? (
        <p className="mt-1 text-xs leading-snug text-ink/55">{explanation}</p>
      ) : null}
    </div>
  );
}

function PlatformBlock({
  title,
  rating,
  reviewCount,
  availability,
  explanation,
  emptyLabel,
}: {
  title: string;
  rating: number | null;
  reviewCount: number | null;
  availability: string;
  explanation: string | null;
  emptyLabel: string;
}) {
  // Show raw platform rating whenever present — even if score is insufficient.
  const showRating = rating != null;

  return (
    <div>
      <div className="text-xs font-medium text-ink/50">{title}</div>
      {showRating ? (
        <p className="mt-0.5 text-sm text-ink">
          <span className="font-semibold">{rating!.toFixed(1)}</span>
          <span className="text-ink/70"> ★</span>
          {reviewCount != null ? (
            <span className="text-ink/55">
              {" "}
              · {reviewCount.toLocaleString()} reviews
            </span>
          ) : null}
        </p>
      ) : (
        <p className="mt-0.5 text-sm text-ink/60">
          {availability === "insufficient_data"
            ? "데이터 부족"
            : availability === "unmatched"
              ? "매칭 없음"
              : emptyLabel}
        </p>
      )}
      {!showRating && explanation ? (
        <p className="mt-1 text-xs leading-snug text-ink/50">{explanation}</p>
      ) : null}
      {showRating &&
      availability !== "available" &&
      explanation ? (
        <p className="mt-1 text-xs leading-snug text-ink/50">{explanation}</p>
      ) : null}
    </div>
  );
}

export function RestaurantCard({
  restaurant,
  selected = false,
  onSelect,
}: {
  restaurant: Restaurant;
  selected?: boolean;
  onSelect?: (restaurantId: string) => void;
}) {
  const { scores, kakao, google, label, match, rating_coverage } = restaurant;

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
      className={`border-b border-ink/10 py-5 last:border-b-0 outline-none transition ${
        selected ? "bg-leaf/5 ring-1 ring-inset ring-leaf/30" : ""
      } ${onSelect ? "cursor-pointer hover:bg-mist/40" : ""}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-lg font-semibold tracking-tight text-ink">
            {restaurant.name}
          </h3>
          {restaurant.road_address || restaurant.address ? (
            <p className="mt-0.5 text-sm text-ink/55">
              {restaurant.road_address || restaurant.address}
            </p>
          ) : null}
          {restaurant.category ? (
            <p className="mt-0.5 text-xs text-ink/40">{restaurant.category}</p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="rounded-sm bg-mist px-2 py-1 text-xs font-medium text-ink/70">
            {COVERAGE_KO[rating_coverage]}
          </span>
          {label ? (
            <span className="rounded-sm bg-leaf/10 px-2 py-1 text-xs font-medium text-leaf">
              {LABEL_KO[label]}
            </span>
          ) : null}
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <PlatformBlock
          title="Kakao"
          rating={scores.local.rating ?? kakao.rating}
          reviewCount={scores.local.review_count ?? kakao.review_count}
          availability={scores.local.availability}
          explanation={scores.local.explanation}
          emptyLabel="보강 불가"
        />
        <PlatformBlock
          title="Google"
          rating={scores.global.rating ?? google?.rating ?? null}
          reviewCount={
            scores.global.review_count ?? google?.user_rating_count ?? null
          }
          availability={scores.global.availability}
          explanation={scores.global.explanation}
          emptyLabel="데이터 없음"
        />
      </div>

      <div className="mt-4 grid grid-cols-3 gap-3 rounded-sm bg-mist/60 p-3">
        <ScoreCell title="Local" score={scores.local.score} explanation={null} />
        <ScoreCell
          title="Global"
          score={scores.global.score}
          explanation={
            scores.global.score == null ? scores.global.explanation : null
          }
        />
        <ScoreCell
          title="Consensus"
          score={scores.consensus.score}
          explanation={
            scores.consensus.score == null ? scores.consensus.explanation : null
          }
        />
      </div>

      <p className="mt-3 text-xs text-ink/40">
        Match confidence:{" "}
        {match.matched
          ? `${match.confidence_level} (${match.confidence.toFixed(2)})`
          : `unmatched${match.reason ? ` — ${match.reason}` : ""}`}
      </p>
    </article>
  );
}
