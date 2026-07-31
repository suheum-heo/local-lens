# LocalLens Scoring (v1)

This document describes the **initial transparent formula**. The scoring engine is behind a `ScoringEngine` interface so the formula can change without rewriting search orchestration.

## Goals

- **Local Score** — Korean / Kakao-side popularity signals
- **Global Score** — Google Places rating + review volume
- **Consensus Score** — only when **both** Local and Global are computable

Review **volume** influences confidence/weight; we do **not** simply average star ratings across platforms.

## Availability gates

Before any numeric score is produced:

| State | Meaning | Score |
|-------|---------|-------|
| `available` | Enough data to compute | number 0–100 |
| `insufficient_data` | Matched but too few reviews (or missing rating) | `null` |
| `unavailable` | Platform has no rating/review payload | `null` |
| `unmatched` | No accepted Google match | `null` |

**Google minimum reviews:** `MIN_GOOGLE_REVIEWS = 5`  
**Kakao minimum reviews (when rating fields exist):** `MIN_KAKAO_REVIEWS = 5`

Insufficient Google data surfaces user-facing copy such as:

> Google 리뷰 데이터가 충분하지 않아 Global Score를 계산하지 않았습니다.

**Never** convert missing Google data into a `0` rating or `0` score.

## Platform score formula (Local or Global)

When availability is `available`:

```
rating_norm = clamp(rating / 5.0, 0, 1)
volume_norm = clamp( log10(1 + review_count) / log10(1 + VOLUME_CAP), 0, 1 )

PlatformScore = 100 * (0.65 * rating_norm + 0.35 * volume_norm)
```

- `VOLUME_CAP = 2000` (soft saturation for review volume)
- Rating dominates (65%); volume still matters (35%) so a 5.0★ with 2 reviews cannot look like a consensus leader

## Consensus Score

Computed **only** when Local and Global are both `available`:

```
ConsensusScore = 0.5 * LocalScore + 0.5 * GlobalScore
```

Otherwise Consensus is `unavailable` with score `null`.

## Labels

Labels are assigned only when data supports them:

| Label | Condition (v1) |
|-------|----------------|
| `consensus_pick` | Both scores ≥ 75 and \|Local − Global\| ≤ 15 |
| `local_favorite` | Local ≥ 80 and (no Global, or Local − Global ≥ 10) |
| `global_favorite` | Global ≥ 80 and (no Local, or Global − Local ≥ 10) |
| `limited_data` | Global side insufficient / unavailable / unmatched and not otherwise labeled as a favorite |

No label is forced when evidence is weak.

## Live Kakao caveat

The Kakao Local **keyword search** API does not return star ratings or review counts.
In live mode, Local Score is typically `unavailable` and `rating_coverage` is usually
`google_only` or `none` — even when Kakao Map's consumer app shows reviews for the same place.
This is an official API limitation, not a matching bug. Mock data includes synthetic Kakao
ratings for UX development only.

### Rating coverage categories

| `rating_coverage` | Meaning |
|-------------------|---------|
| `both` | Kakao **and** Google numeric ratings present |
| `kakao_only` | Kakao rating only |
| `google_only` | Google rating only |
| `none` | Neither side has a numeric rating |

## Changing the formula later

Implement a new class satisfying `ScoringEngine.score(...)` and inject it into `SearchOrchestrator`. Keep availability semantics intact.
