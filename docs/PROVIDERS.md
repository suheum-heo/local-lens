# Live Kakao & Google Providers

## Modes

| `PROVIDER_MODE` | Behavior |
|-----------------|----------|
| `mock` (default) | In-memory fixtures; **no API keys required** |
| `live` | Official Kakao Local + **Places API (New)** |

Live mode **does not** silently fall back to mock. Missing keys raise a configuration error (`503` from the API).

## Credentials

Copy `.env.example` → `backend/.env` (never commit real keys):

```env
PROVIDER_MODE=live
KAKAO_REST_API_KEY=
GOOGLE_PLACES_API_KEY=
```

### Kakao REST API key

1. Create an app in [Kakao Developers](https://developers.kakao.com/)
2. Enable **Kakao Map / Local** tools for the app
3. Copy the **REST API key** into `KAKAO_REST_API_KEY`

### Google Places API key (New)

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable **Places API (New)** (not only legacy Places API)
3. Create an API key; restrict it by IP / application in production
4. Copy into `GOOGLE_PLACES_API_KEY`

Billing uses Places API (New) SKUs (Text Search / Place Details). Legacy Find Place is **not** used.

## Endpoints used

### Kakao Local

- `GET https://dapi.kakao.com/v2/local/search/keyword.json`
- Auth header: `Authorization: KakaoAK <REST_KEY>`
- Params: `query`, `x`/`y` (WGS84 lon/lat), `radius` (m, capped at 20 000), `category_group_code=FD6` (food), `size≤15`, `page`, `sort=distance`

**Supplies:** Kakao place id, name, address / road address, coordinates, category, place URL.

**Does not supply:** star ratings or review counts. Discovery ≠ Kakao rating availability. Ratings come from a separate unofficial enrichment step (below).

**Pagination:** up to **3 pages × 15** results per origin (≤ 45). Stops early when `meta.is_end` is true.

**Broad food queries** (`맛집` / empty → default): Kakao’s ~45 pageable ceiling hides restaurants that are inside the radius but not among the nearest pack. LocalLens fans out the same keyword search across a tight cardinal grid (~200–280 m steps; a second ring for ≥1.2 km), merges by Kakao place id, and keeps only places within the original radius. Specific cuisine/name queries still use a single origin.

**Cuisine intent expansion:** Umbrella food terms (e.g. `양식`) also search related Kakao keywords (`패밀리레스토랑`, `파스타`, `피자`, …) because Kakao’s category tree often tags Western-style places outside `음식점 > 양식`. Results are merged by place id. Place-name queries are not expanded.

### Kakao Map place-detail enrichment (unofficial)

Official Local APIs do not expose map reviews. After keyword discovery + dedupe, live mode calls a **public but unofficial** Kakao Map review-tab endpoint to fill `rating` / `review_count` when present:

- `GET https://place-api.map.kakao.com/places/tab/reviews/kakaomap/{kakao_place_id}`
- Browser-like headers including `appVersion` and `pf=PC` (required by the host)
- Parsed fields: `score_set.average_score`, `score_set.review_count`

**Behavior:**

- Soft-fail per place (timeout / 404 / parse miss) → leave rating missing; never invent zeros
- Request-scoped cache by place id; concurrency ≤ 12; enrich at most **40** unique places per search
- Runs **in parallel** with Google matching (ratings are not required for matching)
- Skipped entirely when `PROVIDER_MODE=mock` (fixtures already include ratings)
- Counted as `api_calls.kakao_place_detail`

**Risk:** Not a Kakao Developers product. Kakao has stated map reviews are not for third-party API use. The endpoint may break or block clients without notice. LocalLens documents this trade-off explicitly so Local vs Global scoring can work.

**Neighborhoods:** searched as a radius around the catalog centroid. The official keyword API does not filter by administrative polygon; LocalLens does not claim a place is “inside” a dong beyond that radius evidence.

### Google Places API (New)

#### Text Search (primary)

- `POST https://places.googleapis.com/v1/places:searchText`
- Headers:
  - `X-Goog-Api-Key: <GOOGLE_PLACES_API_KEY>`
  - `X-Goog-FieldMask:` (required; no `*` wildcards)

**Field mask (matching + scoring):**

```text
places.id,places.displayName,places.formattedAddress,places.location,places.rating,places.userRatingCount
```

**Request body (focused):**

- `textQuery` — Kakao name + address
- `languageCode=ko`, `regionCode=KR`
- `includedType=restaurant`
- `pageSize=5`
- `locationBias.circle` — Kakao coordinates, radius **500 m**

**Supplies:** place id, display name, formatted address, coordinates, rating, user rating count.

**Does not request:** `places.reviews` (scoring only needs rating + count).

#### Place Details (New) — conditional fallback only

- `GET https://places.googleapis.com/v1/places/{place_id}`
- Field mask: `id,displayName,formattedAddress,location,rating,userRatingCount`

Invoked **only** when Text Search accepted a match but `rating` or `userRatingCount` is missing. In the usual case Text Search already returns both and Details is skipped.

## Kakao → Google matching

1. Text Search returns up to 5 candidates (not auto-accepted).
2. `DefaultPlaceMatcher` scores each candidate with name similarity, distance, and address overlap.
3. The highest-confidence candidate is kept only if confidence ≥ **0.55**; otherwise Global = `unmatched`.

Index 0 is never assumed to be correct.

## Where API calls happen

```
POST /api/search
  → create_search_orchestrator()      # fresh providers + ApiCallCounter
  → Kakao keyword search              # once per SearchArea page
  → normalize_and_dedupe              # by kakao_place_id
  → KakaoPlaceEnricher ∥ PlaceMatcher # parallel (live enrich + Google match)
       → review-tab ratings           # unofficial; ≤ 40 places, concurrency 12
       → Places Text Search (New)    # ≤ 1 per unique place (cached; concurrency 8)
       → Places Details (New)         # only if rating/count missing after search
  → ScoringEngine
```

`SearchMeta.api_calls` (live) reports:

```json
{
  "kakao_keyword": 1,
  "kakao_place_detail": 12,
  "google_search_text": 12,
  "google_details": 0,
  "total": 25
}
```

## Billing considerations (Google Places API New)

| Field / call | Role | Typical LocalLens usage |
|--------------|------|-------------------------|
| `places.id`, `displayName`, `formattedAddress`, `location` | Matching | Always in Text Search mask |
| `places.rating`, `places.userRatingCount` | Global Score | Always in Text Search mask (Enterprise/Pro SKUs apply per Google’s field pricing) |
| `places.reviews` | Optional metadata | **Not requested** |
| Place Details (New) | Fallback | Only when search omitted rating/count |

Also:

- Deduplicate Kakao candidates **before** Google enrichment.
- Request-scoped Text Search / Details caches avoid repeat calls in one search.
- Keep validation queries small (single station, modest radius).

## Error handling

| Condition | Result |
|-----------|--------|
| Missing live credentials | `ProviderConfigError` → HTTP 503 |
| Kakao 401/403 | Safe message; HTTP 502 |
| Google 401/403 | Auth failure message; HTTP 502 |
| Kakao/Google rate limit (429) | HTTP 429, retryable |
| Timeout / transport failure | HTTP 504/502, retryable |
| Empty Text Search / no confident match | Restaurant kept; Global = `unmatched` |
| Few Google reviews | Global = `insufficient_data` (score `null`, not 0) |

API keys and raw upstream exception bodies are never returned to the client.

## Limitations

- Text Search location bias is soft (results can fall outside the 500 m circle).
- Name transliteration: matcher romanizes Hangul and allows a tight geo+address fallback for Hangul↔Latin pairs; residual false negatives/positives are still possible.
- Kakao Local discovery still has no ratings; Local Score depends on unofficial place-detail enrichment succeeding.
- Legacy Places endpoints (Find Place / Place Details Legacy) are intentionally unused.

## Testing

Automated tests mock HTTP with `httpx.MockTransport` and **must not** call real APIs or need credentials. See `backend/tests/test_live_providers.py`.
