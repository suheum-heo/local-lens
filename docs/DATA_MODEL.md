# LocalLens Data Model

## Location inputs

### StationLocation

| Field | Type | Notes |
|-------|------|-------|
| `station_id` | string | Stable id |
| `station_name` | string | Display name (e.g. 합정역) |
| `city` | City enum | |
| `latitude` / `longitude` | float | WGS84 |
| `radius_m` | int | Default **1000** |

### NeighborhoodLocation

| Field | Type | Notes |
|-------|------|-------|
| `neighborhood_id` | string | Stable id |
| `neighborhood_name` | string | e.g. 삼산동 |
| `city` | City enum | |
| `latitude` / `longitude` | float | Centroid / anchor |
| `radius_m` | int | Default **1000** |

Stations and neighborhoods are **independent** types. Both convert to `SearchArea`.

### SearchArea (common abstraction)

Discovery code only sees:

- `area_id`, `label`, `city`
- `latitude`, `longitude`, `radius_m`
- `source_mode` (`station` \| `neighborhood`), `source_id`

Multiple areas per search are supported; overlapping results are deduplicated.

## Restaurant candidate (Kakao)

Normalized as `KakaoPlaceData`:

- `kakao_place_id`, `name`
- `address`, `road_address`
- `latitude`, `longitude`
- `category`, `place_url`
- optional `rating`, `review_count` (present in mocks; often absent from live keyword API)

Internal `restaurant_id` is a UUID assigned at normalization time.

**Dedup key:** `kakao_place_id` across all search areas in one request.

## Google match

`PlaceMatchResult`:

- `confidence` ∈ [0, 1]
- `confidence_level`: `high` \| `medium` \| `low` \| `none`
- `matched`: bool — `true` only if confidence ≥ accept threshold
- `google`: `GooglePlaceData` or `null`
- `reason`: explanation when not matched

`GooglePlaceData`:

- `google_place_id`, `name`, `address`
- `latitude`, `longitude`
- `rating`, `user_rating_count`
- `review_metadata` (list of lightweight review dicts from the official API when available)

## Scores & labels

`ScoreBundle`:

```json
{
  "local": { "availability": "...", "rating": null, "review_count": null, "score": null, "explanation": "..." },
  "global": { "...": "..." },
  "consensus": { "...": "..." }
}
```

`Restaurant.label`: `consensus_pick` \| `local_favorite` \| `global_favorite` \| `limited_data` \| `null`

## API contracts

### `POST /api/search`

Request:

```json
{
  "city": "seoul",
  "mode": "station",
  "locations": [
    {
      "type": "station",
      "station_id": "st_hapjeong",
      "station_name": "합정역",
      "city": "seoul",
      "latitude": 37.5496,
      "longitude": 126.9139,
      "radius_m": 1000
    }
  ],
  "query": "삼겹살"
}
```

Response: `{ "results": Restaurant[], "meta": {...}, "notices": string[] }`

### `GET /api/locations?city=seoul&mode=station`

Returns catalog items for the UI multi-select.

## Persistence (planned)

SQLAlchemy models / PostgreSQL are intended for caching Kakao/Google snapshots and match decisions. MVP search does not require a live database; `InMemoryRestaurantRepository` is a stub.
