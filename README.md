# LocalLens

Discover restaurants in South Korea by combining **Kakao** (local) and **Google** (global) signals.

- **Local popularity** — Kakao-oriented signals used heavily by Korean users  
- **Global popularity** — Google Maps ratings / reviews (travelers + international users)  
- **Consensus picks** — places that perform well on both sides  

Missing data stays missing. Weak Google coverage is never turned into a fake zero rating.

## Project structure

```
local-lens/
  frontend/     Next.js (App Router) + TypeScript + Tailwind
  backend/      FastAPI + Pydantic + provider interfaces
  docs/         ARCHITECTURE.md, SCORING.md, DATA_MODEL.md, PROVIDERS.md
```

## Prerequisites

- Python 3.11+
- Node.js 20+
- (Optional for live mode) Kakao REST API key + Google Places API key

## Quick start (mock mode — no API keys)

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt

# Optional: copy env from repo root
cp ../.env.example .env            # PROVIDER_MODE=mock by default

uvicorn app.main:app --reload --port 8000
```

Health check: [http://localhost:8000/health](http://localhost:8000/health)  
API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### 2. Frontend

```bash
cd frontend
npm install
# Ensure NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 in .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### Try these searches (mock data)

| City | Mode | Locations | Query |
|------|------|-----------|-------|
| Seoul | Station | 합정역 | 삼겹살 |
| Seoul | Station | 강남역 (+ 신논현역) | 삼겹살 |
| Ulsan | Neighborhood | 삼산동 | 고기 or 분식 |

Station searches support radius chips: **500 m / 1 km / 1.5 km / 2 km** (default 1 km).  
The UI keeps `city`, `mode`, `locs`, `radius`, `q`, and `run` in the URL so refresh/share preserves the configuration. Result cards and the map share selection.

Mock fixtures include: strong dual-platform data, missing Google match, insufficient Google reviews, and uncertain matching.

## Live mode (real Kakao + Google)

1. Obtain credentials (see [docs/PROVIDERS.md](docs/PROVIDERS.md)):
   - Kakao Developers → REST API key (Local/Map)
   - Google Cloud → enable **Places API (New)** → API key
2. Copy `.env.example` → `backend/.env` and set:

```env
PROVIDER_MODE=live
KAKAO_REST_API_KEY=your_kakao_rest_key
GOOGLE_PLACES_API_KEY=your_google_places_key
```

3. Restart the backend. **Do not** put keys in the frontend, docs, or Git.

Google enrichment uses Places API (New) **Text Search** (`places:searchText`), not legacy Find Place. Place Details (New) is only a fallback when rating/count are missing from search.

Suggested first live validation (keeps Google usage small):

- Seoul · 합정역 · radius **1 km** · query **맛집**

**Important:** Kakao Local keyword search discovers candidates but does **not** return star ratings. Live mode then enriches ratings via an **unofficial** Kakao Map place-detail endpoint (ToS / breakage risk). Failures leave Kakao ratings missing — never fabricated. Global Score still uses Google when a confident match exists.

Live mode fails with a clear configuration error if keys are missing — it will not silently use mock data.

## Tests

```bash
cd backend
source .venv/bin/activate
pytest
```

Live-provider tests mock HTTP and never call billable APIs.

```bash
cd frontend
npm run lint    # tsc --noEmit
npm run build
```

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/SCORING.md](docs/SCORING.md)
- [docs/DATA_MODEL.md](docs/DATA_MODEL.md)
- [docs/PROVIDERS.md](docs/PROVIDERS.md) — endpoints, credentials, API cost notes

## API

`POST /api/search` — multi-location restaurant search  
`GET /api/locations?city=seoul&mode=station` — location catalog for the UI  
`GET /api/restaurants/photo?photo_name=...` — Google Place photo proxy (API key stays server-side)

## Deploy (Vercel + Render, Live)

Production layout:

- **Frontend** — [Vercel](https://vercel.com), project root directory `frontend/`
- **Backend** — [Render](https://render.com), Docker service from [`render.yaml`](render.yaml) + [`backend/Dockerfile`](backend/Dockerfile)

### 1. Backend on Render

1. In the Render Dashboard: **New → Blueprint** → connect `suheum-heo/local-lens` (uses root `render.yaml`).
2. Set secret env vars when prompted (never commit these):

```env
PROVIDER_MODE=live
KAKAO_REST_API_KEY=...
GOOGLE_PLACES_API_KEY=...
CORS_ORIGINS=https://YOUR_VERCEL_DOMAIN
```

`PROVIDER_MODE` is already set to `live` in `render.yaml`.

3. Deploy and note the public URL (e.g. `https://local-lens-api.onrender.com`).
4. Confirm `GET /health` returns `"provider_mode": "live"`.

Free web services on Render spin down after idle; the first request after sleep can take ~30–60s.

### 2. Frontend on Vercel

1. Import the GitHub repo (or `npx vercel` from `frontend/`).
2. Set **Root Directory** to `frontend`.
3. Set:

```env
NEXT_PUBLIC_API_BASE_URL=https://YOUR_RENDER_BACKEND_URL
```

4. Deploy production. Then update Render `CORS_ORIGINS` to the Vercel URL and redeploy the API if needed.

CLI sketch:

```bash
cd frontend
npx vercel login
npx vercel link
npx vercel env add NEXT_PUBLIC_API_BASE_URL production
npx vercel --prod
```

### 3. Smoke check

- Backend: `curl https://YOUR_RENDER_URL/health`
- Frontend: open the Vercel URL → Seoul · 합정역 · 맛집 → results load with Kakao/Google signals
