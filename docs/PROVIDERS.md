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

**Does not supply:** star ratings or review counts. Local Score stays `unavailable` in live mode unless a future enrichment source is added. Candidate discovery ≠ Kakao rating availability.

**Pagination:** up to **3 pages × 15** results per `SearchArea` (≤ 45). Stops early when `meta.is_end` is true.

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
  → normalize_and_dedupe              # by kakao_place_id (before Google)
  → PlaceMatcher per unique Kakao place
       → Places Text Search (New)    # ≤ 1 per unique place (request-cached)
       → Places Details (New)         # only if rating/count missing after search
  → ScoringEngine
```

`SearchMeta.api_calls` (live) reports:

```json
{
  "kakao_keyword": 1,
  "google_search_text": 12,
  "google_details": 0,
  "total": 13
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
- Name transliteration differences can still produce false positives; confidence gate mitigates but does not eliminate them.
- Kakao Local still provides no ratings → live Local Score usually `unavailable`.
- Legacy Places endpoints (Find Place / Place Details Legacy) are intentionally unused.

## Testing

Automated tests mock HTTP with `httpx.MockTransport` and **must not** call real APIs or need credentials. See `backend/tests/test_live_providers.py`.
