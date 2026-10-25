# GermanATO

Workshop management app: **FastAPI** API (`api/`), **React + TypeScript + Vite** frontend (`web/`), **PostgreSQL**, **JWT** auth.

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

## API (FastAPI)

```bash
cd api
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
python create_admin.py
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Health: `http://127.0.0.1:8000/api/health`
- Docs: `http://127.0.0.1:8000/docs`
- Auth: `POST /api/auth/login` → JWT access + refresh tokens

## Web (React + Vite)

```bash
cd web
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` → `http://127.0.0.1:8000`.

Production build:

```bash
cd web
npm run build
npm run preview
```

## Stack

| Layer    | Tech                                      |
|----------|-------------------------------------------|
| Frontend | React, TypeScript, Vite, React Router, TanStack Query |
| Backend  | FastAPI, SQLAlchemy, JWT                  |
| Database | PostgreSQL                                |

## Layout

- `api/` — FastAPI application
- `web/` — React SPA

Default admin (from `create_admin.py`): `admin` / `admin123`
