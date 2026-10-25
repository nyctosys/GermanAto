# GermanATO

Workshop management app: **FastAPI** API (`api/`), **React + TypeScript + Vite** frontend (`web/`), **PostgreSQL**, **JWT** auth.

See **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** for what exists today and **[docs/GAP_REPORT.md](docs/GAP_REPORT.md)** for feature gaps.

## Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL

## Database

Create a database and user, then copy API env:

```bash
cd api
cp .env.example .env
# edit DATABASE_URL / JWT_SECRET_KEY as needed
```

Default example URL:

`postgresql+psycopg://germanato:germanato@localhost:5432/germanato`

After first boot (or when upgrading), run the additive foundation migration:

```bash
cd api
.venv\Scripts\python.exe migrate_foundation.py
```

This seeds default branch `a1b2c3d4` and adds `branch_id` / `version` / `deleted_at` columns without rewriting money fields.

## API (FastAPI)

```bash
cd api
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
pip install pytest
python create_admin.py
python migrate_foundation.py
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Health: `http://127.0.0.1:8000/api/health`
- Docs: `http://127.0.0.1:8000/docs`
- Auth: `POST /api/auth/login` → JWT access + refresh tokens

Tests:

```bash
cd api
.venv\Scripts\python.exe -m pytest tests -q
```

## Web (React + Vite)

```bash
cd web
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` → `http://127.0.0.1:8000`.

Shared Zod schemas live in `shared/` (`@germanato/shared`).

Production build:

```bash
cd web
npm run build
npm run preview
```

## Stack

| Layer    | Tech                                      |
|----------|-------------------------------------------|
| Frontend | React, TypeScript, Vite, React Router, TanStack Query, Zod |
| Backend  | FastAPI, SQLAlchemy, JWT                  |
| Shared   | `@germanato/shared` (Zod: money, branch, roles) |
| Database | PostgreSQL                                |

## Layout

- `api/` — FastAPI application + `foundation/` helpers
- `web/` — React SPA
- `shared/` — client validation schemas
- `docs/` — architecture + gap report

Default admin (from `create_admin.py`): `admin` / `admin123`
