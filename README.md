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
  docs/         ARCHITECTURE.md, SCORING.md, DATA_MODEL.md
```

## Prerequisites

- Python 3.11+
- Node.js 20+
- (Optional) Kakao REST API key + Google Places API key for live mode

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
cp ../.env.example .env.local      # uses NEXT_PUBLIC_API_BASE_URL
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### Try these searches (mock data)

| City | Mode | Locations | Query |
|------|------|-----------|-------|
| Seoul | Station | 합정역 | 삼겹살 |
| Seoul | Station | 강남역 (+ 신논현역) | 삼겹살 |
| Ulsan | Neighborhood | 삼산동 | 고기 or 분식 |

Mock fixtures include: strong dual-platform data, missing Google match, insufficient Google reviews, and uncertain matching.

## Live providers

1. Copy `.env.example` → `backend/.env`
2. Set:

```env
PROVIDER_MODE=live
KAKAO_REST_API_KEY=your_kakao_rest_key
GOOGLE_PLACES_API_KEY=your_google_places_key
```

3. Restart the backend. Interfaces stay the same; only the factory swaps implementations.

**Note:** Kakao Local keyword search does not return star ratings. Local Score may be `unavailable` in live mode until a richer enrichment source is added. See `docs/SCORING.md`.

## Tests

```bash
cd backend
source .venv/bin/activate
pytest
```

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/SCORING.md](docs/SCORING.md)
- [docs/DATA_MODEL.md](docs/DATA_MODEL.md)

## API

`POST /api/search` — multi-location restaurant search  
`GET /api/locations?city=seoul&mode=station` — location catalog for the UI
