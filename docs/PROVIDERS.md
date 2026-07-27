# Live Kakao & Google Providers

## Modes

| `PROVIDER_MODE` | Behavior |
|-----------------|----------|
| `mock` (default) | In-memory fixtures; **no API keys required** |
| `live` | Official Kakao Local + Google Places HTTP APIs |

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

### Google Places API key

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable **Places API** (Find Place from Text + Place Details)
3. Create an API key; restrict it by IP/HTTP referrer in production
4. Copy into `GOOGLE_PLACES_API_KEY`

## Endpoints used

### Kakao Local

- `GET https://dapi.kakao.com/v2/local/search/keyword.json`
- Auth header: `Authorization: KakaoAK <REST_KEY>`
- Params: `query`, `x`/`y` (WGS84 lon/lat), `radius` (m, capped at 20 000), `category_group_code=FD6` (food), `size≤15`, `page`, `sort=distance`

**Supplies:** Kakao place id, name, address / road address, coordinates, category, place URL.

**Does not supply:** star ratings or review counts. Local Score stays `unavailable` in live mode unless a future enrichment source is added. Candidate discovery ≠ Kakao rating availability.

**Pagination:** up to **3 pages × 15** results per `SearchArea` (≤ 45). Stops early when `meta.is_end` is true.

**Neighborhoods:** searched as a radius around the catalog centroid. The official keyword API does not filter by administrative polygon; LocalLens does not claim a place is “inside” a dong beyond that radius evidence.

### Google Places

- `GET https://maps.googleapis.com/maps/api/place/findplacefromtext/json`
  - Fields: `place_id,name,formatted_address,geometry,rating,user_ratings_total`
  - `locationbias=circle:500@lat,lng`
- `GET https://maps.googleapis.com/maps/api/place/details/json` (only when Find Place lacks rating or review count)
  - Fields: above + `reviews`

**Supplies:** Google place id, name, address, coordinates, rating, user rating count, optional review snippets.

Matching still applies the confidence gate (`≥ 0.55`). A returned Google candidate is **not** auto-accepted.

## Where API calls happen

```
POST /api/search
  → create_search_orchestrator()   # fresh providers + ApiCallCounter
  → Kakao keyword search           # once per SearchArea page
  → normalize_and_dedupe           # by kakao_place_id (before Google)
  → PlaceMatcher per unique Kakao place
       → Google Find Place         # ≤ 1 per unique place (request-cached)
       → Google Place Details      # only if rating/count missing after Find
  → ScoringEngine
```

`SearchMeta.api_calls` (live) reports:

```json
{
  "kakao_keyword": 1,
  "google_find_place": 12,
  "google_details": 0,
  "total": 13
}
```

## Cost considerations (Google)

- Deduplicate Kakao candidates **before** enrichment.
- Request-scoped Find Place / Details caches avoid repeat calls in one search.
- Prefer Find Place fields that already include rating + `user_ratings_total` so Details is skipped.
- Keep validation queries small (single station, modest radius).
- Place Details + `reviews` is more expensive — avoided when scoring fields are already present.

## Error handling

| Condition | Result |
|-----------|--------|
| Missing live credentials | `ProviderConfigError` → HTTP 503 |
| Kakao 401/403 | Safe message; HTTP 502 |
| Kakao/Google rate limit | HTTP 429, retryable |
| Timeout / transport failure | HTTP 504/502, retryable |
| Google `ZERO_RESULTS` / no confident match | Restaurant kept; Global = `unmatched` |
| Few Google reviews | Global = `insufficient_data` (score `null`, not 0) |

API keys and raw upstream exception bodies are never returned to the client.

## Testing

Automated tests mock HTTP with `httpx.MockTransport` and **must not** call real APIs or need credentials. See `backend/tests/test_live_providers.py`.
