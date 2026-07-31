# LocalLens Architecture

## Overview

LocalLens discovers restaurants in South Korea by combining:

- **Kakao Local** — candidate discovery and local (Korean-user) signals
- **Google Places** — global rating / review signals after place matching

The MVP runs with **mock providers** by default so development does not require API keys.

## Directory layout

```
local-lens/
  frontend/          Next.js (App Router) UI
  backend/           FastAPI application
  docs/              Architecture & domain docs
  .env.example       Placeholder env vars only
```

### Backend layers

| Layer | Path | Responsibility |
|-------|------|----------------|
| API routes | `app/api/routes/` | HTTP adapters only — validate input, call services |
| Services | `app/services/` | Search orchestration |
| Providers | `app/providers/` | Kakao / Google clients behind interfaces |
| Matching | `app/matching/` | Kakao → Google place matching + confidence |
| Normalization | `app/normalization/` | Candidate merge / dedupe |
| Scoring | `app/scoring/` | Local / Global / Consensus scores |
| Domain | `app/domain/` | Enums, locations, models, API contracts |
| Repositories | `app/repositories/` | Persistence interface (in-memory for MVP) |

Route handlers do **not** call external APIs directly.

## Search flow

```
SearchRequest
  → SearchArea[]          (stations or neighborhoods → common abstraction)
  → KakaoLocalProvider    (per area, keyword + radius)
  → normalize_and_dedupe  (by Kakao place id)
  → KakaoPlaceEnricher ∥ PlaceMatcher  (ratings + Google match in parallel)
  → ScoringEngine         (availability-aware scores + labels)
  → SearchResponse
```

## Location abstraction

Users select **subway stations** or **neighborhoods**. Both normalize to `SearchArea`:

- `latitude`, `longitude`, `radius_m`
  - Stations: UI options **500 / 1000 / 1500 / 2000 m** (default 1000)
  - Neighborhoods: default **1000 m** in the MVP UI
- `source_mode`, `source_id`, `label`, `city`

Restaurant discovery only receives `SearchArea`. Multi-select is first-class: one search may include several stations or several neighborhoods. Overlaps are deduplicated by Kakao place id.

The frontend keeps search configuration in the URL (`city`, `mode`, `locs`, `radius`, `q`, `run`) so refresh/share preserves the selection. Result cards and the map share selection state.


## Provider switching

`PROVIDER_MODE=mock` (default) → `MockKakaoLocalProvider` / `MockGooglePlacesProvider`  
`PROVIDER_MODE=live` → `LiveKakaoLocalProvider` / `LiveGooglePlacesProvider` (**Places API New**)

Factory: `app/providers/factory.py`. Live mode requires both API keys and **never** falls back to mock silently.

Each `POST /api/search` builds a request-scoped orchestrator (fresh Google caches + `ApiCallCounter`). See [PROVIDERS.md](PROVIDERS.md) for endpoints, field masks, and cost controls.

## Matching policy

Matching uses name similarity, distance, and address overlap across **all** Text Search candidates (not just the first). Results below the accept threshold (`0.55`) are **not** attached to the restaurant. Uncertain matches stay `unmatched` — never silently linked.

Google Place Details (New) is called only when Text Search did not already return rating + user rating count.

## Missing data

Missing or weak Google data is a first-class `DataAvailability` state:

- `available`
- `insufficient_data`
- `unavailable`
- `unmatched`

Scores are `null` when data is insufficient. We never coerce missing Google data to a zero rating.

Kakao Local keyword search does **not** provide ratings. Live Local Score depends on unofficial Kakao Map place-detail enrichment (soft-fail → missing).

## Extending to real APIs

1. Set `KAKAO_REST_API_KEY` and `GOOGLE_PLACES_API_KEY` in `backend/.env`.
2. Enable **Places API (New)** in Google Cloud (Text Search).
3. Set `PROVIDER_MODE=live`.
4. Restart the backend. Orchestration, matching, and scoring stay unchanged.

PostgreSQL + SQLAlchemy are listed for persistence; the MVP search path is request-scoped (in-memory repository stub only).
