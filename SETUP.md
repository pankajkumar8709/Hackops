# Pulse — Local Development Setup

## Services (no Docker)

| Service | How to run |
|---|---|
| **Database** | Supabase or Neon (managed Postgres + pgvector) |
| **Backend** | `uvicorn app.main:app --reload` (from `backend/`) |
| **Frontend** | `npm run dev` (from `frontend/`) |
| **Discord bot** | `python bot/main.py` (from project root, Phase 12+) |

## First-time setup

### 1. Database — Supabase or Neon

1. Create a free project at [supabase.com](https://supabase.com) or [neon.tech](https://neon.tech).
2. Open the **SQL Editor** and run:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
3. Copy the **connection string** from the dashboard (Settings → Database).

### 2. Environment

```bash
cp .env.example .env
```

Edit `.env` and fill in:
- `DATABASE_URL` — asyncpg connection string (for FastAPI runtime)
- `DATABASE_SYNC_URL` — psycopg2 connection string (for Alembic CLI)
- `GROQ_API_KEY` — from [console.groq.com](https://console.groq.com)
- `JWT_SECRET` — any long random string

Both URLs point to the **same database**, just different driver prefixes:
```
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db?sslmode=require
DATABASE_SYNC_URL=postgresql+psycopg2://user:pass@host:5432/db?sslmode=require
```

### 3. Backend

```bash
cd backend
pip install -r requirements.txt
# Run migrations (after Phase 1 models are created)
alembic upgrade head
# Start dev server
uvicorn app.main:app --reload --port 8000
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
# Vite starts on http://localhost:5173
```

### 5. Verify Phase 0

- Backend → `http://localhost:8000/health` → `{ "status": "ok" }`
- Frontend → `http://localhost:5173` → displays "ok" from the backend
