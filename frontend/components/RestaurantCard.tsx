"use client";

import { useState } from "react";
import { googleMapUrl, kakaoMapUrl } from "@/lib/mapLinks";
import { formatDistanceMeters } from "@/lib/geo";
import { restaurantPhotoSrc } from "@/lib/photoUrl";
import {
  LABEL_BADGE_CLASS,
  LABEL_TEXT,
  STATUS,
  statusFromLabel,
} from "@/lib/statusStyles";
import type { Restaurant } from "@/lib/types";

function ScoreRing({
  score,
  tone,
}: {
  score: number | null;
  tone: keyof typeof STATUS;
}) {
  const color = STATUS[tone].hex;
  const display = score != null ? Math.round(score) : "—";
  return (
    <div
      className="relative flex h-[4.25rem] w-[4.25rem] shrink-0 items-center justify-center rounded-full bg-white shadow-soft"
      style={{
        background: `conic-gradient(${color} ${
          score != null ? Math.min(100, Math.max(0, score)) : 0
        }%, #E5E7EB 0)`,
      }}
      aria-label={
        score != null ? `추천 점수 ${score.toFixed(1)}` : "추천 점수 없음"
      }
    >
      <div className="flex h-[3.35rem] w-[3.35rem] flex-col items-center justify-center rounded-full bg-white">
        <span className="text-lg font-bold tabular-nums leading-none text-ink">
          {display}
        </span>
        <span className="mt-0.5 text-[9px] font-medium uppercase tracking-wide text-mute">
          Score
        </span>
      </div>
    </div>
  );
}

function PhotoThumb({
  restaurant,
}: {
  restaurant: Restaurant;
}) {
  const src = restaurantPhotoSrc(restaurant.photo_url);
  const [failed, setFailed] = useState(false);
  const showPhoto = Boolean(src) && !failed;
  const attribution = restaurant.photo_attributions?.[0] ?? null;
  const initial = restaurant.name.trim().charAt(0) || "";

  return (
    <div className="relative h-[4.5rem] w-[4.5rem] shrink-0 overflow-hidden rounded-2xl bg-mist shadow-soft sm:h-[5.25rem] sm:w-[5.25rem]">
      {showPhoto ? (
        <img
          src={src!}
          alt=""
          width={84}
          height={84}
          loading="lazy"
          decoding="async"
          className="h-full w-full object-cover"
          onError={() => setFailed(true)}
        />
      ) : (
        <div
          className="flex h-full w-full flex-col items-center justify-center gap-1 text-white"
          style={{
            background:
              "linear-gradient(145deg, rgba(34,197,94,0.92), rgba(99,102,241,0.88))",
          }}
          aria-hidden
        >
          <svg
            viewBox="0 0 24 24"
            className="h-6 w-6 opacity-95 sm:h-7 sm:w-7"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
          >
            <path d="M8 3v10a2 2 0 0 0 4 0V3" />
            <path d="M10 3v18" />
            <path d="M16 8v13" />
            <path d="M14 8h4" />
          </svg>
          {initial ? (
            <span className="text-[10px] font-semibold tracking-wide text-white/80">
              {initial}
            </span>
          ) : null}
        </div>
      )}
      {showPhoto && attribution ? (
        <span
          className="pointer-events-none absolute inset-x-0 bottom-0 truncate bg-black/45 px-1 py-0.5 text-[8px] font-medium text-white"
          title={attribution}
        >
          {attribution}
        </span>
      ) : null}
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
  const recommendation =
    scores.consensus.score ?? scores.local.score ?? scores.global.score;

  const unmatched = !match.matched;
  const tone = unmatched && !label ? "unmatched" : statusFromLabel(label);
  const statusBadge = label
    ? { text: LABEL_TEXT[label], className: LABEL_BADGE_CLASS[label] }
    : unmatched
      ? {
          text: "Google Unmatched",
          className: "bg-slate-400 text-white",
        }
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
      className={`group rounded-card border bg-card p-3.5 shadow-soft outline-none transition duration-200 ease-soft sm:p-4 ${
        selected
          ? "border-brand/40 ring-2 ring-brand/20 shadow-lift"
          : "border-line hover:-translate-y-0.5 hover:border-brand/20 hover:shadow-lift"
      } ${onSelect ? "cursor-pointer" : ""}`}
    >
      <div className="flex gap-3 sm:gap-4">
        <PhotoThumb restaurant={restaurant} />

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              {statusBadge ? (
                <span
                  className={`inline-flex rounded-chip px-2 py-0.5 text-[10px] font-semibold tracking-wide ${statusBadge.className}`}
                >
                  {statusBadge.text}
                </span>
              ) : null}
              <h3 className="mt-1 truncate text-base font-semibold tracking-tight text-ink sm:text-lg">
                {restaurant.name}
              </h3>
              <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-mute sm:text-sm">
                {categoryShort ? <span>{categoryShort}</span> : null}
                {categoryShort && distanceM != null ? (
                  <span className="text-line">·</span>
                ) : null}
                {distanceM != null ? (
                  <span className="font-medium tabular-nums text-ink/60">
                    {formatDistanceMeters(distanceM)}
                  </span>
                ) : null}
              </div>
            </div>
            <ScoreRing score={recommendation} tone={tone} />
          </div>

          <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            <span className="inline-flex items-center gap-1.5 text-ink/80">
              <span className="rounded-md bg-local/10 px-1.5 py-0.5 text-[11px] font-bold text-local">
                K
              </span>
              {kakaoRating != null ? (
                <>
                  <span className="font-semibold tabular-nums">
                    {kakaoRating.toFixed(1)}
                  </span>
                  {kakaoCount != null ? (
                    <span className="text-mute">
                      ({kakaoCount.toLocaleString()})
                    </span>
                  ) : null}
                </>
              ) : (
                <span className="text-mute">
                  {scores.local.availability === "insufficient_data"
                    ? "리뷰 부족"
                    : "데이터 없음"}
                </span>
              )}
            </span>
            <span className="inline-flex items-center gap-1.5 text-ink/80">
              <span className="rounded-md bg-global/10 px-1.5 py-0.5 text-[11px] font-bold text-global">
                G
              </span>
              {googleRating != null ? (
                <>
                  <span className="font-semibold tabular-nums">
                    {googleRating.toFixed(1)}
                  </span>
                  {googleCount != null ? (
                    <span className="text-mute">
                      ({googleCount.toLocaleString()})
                    </span>
                  ) : null}
                </>
              ) : (
                <span className="text-mute">
                  {scores.global.availability === "unmatched"
                    ? "매칭 없음"
                    : "데이터 없음"}
                </span>
              )}
            </span>
          </div>

          <div className="mt-3 flex flex-wrap gap-1.5">
            <a
              href={kakaoMapUrl(restaurant)}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="rounded-chip border border-line bg-white px-3 py-1.5 text-xs font-medium text-ink/70 transition hover:border-local/30 hover:bg-local/5 hover:text-ink"
            >
              Kakao
            </a>
            <a
              href={googleMapUrl(restaurant)}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="rounded-chip border border-line bg-white px-3 py-1.5 text-xs font-medium text-ink/70 transition hover:border-global/30 hover:bg-global/5 hover:text-ink"
            >
              Google
            </a>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onSelect?.(restaurant.restaurant_id);
              }}
              className="rounded-chip bg-brand/10 px-3 py-1.5 text-xs font-semibold text-brand-dark transition hover:bg-brand/15"
            >
              Map
            </button>
          </div>
        </div>
      </div>
    </article>
  );
}
