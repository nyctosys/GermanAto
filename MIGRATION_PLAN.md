# GermanATO → Next.js + FastAPI migration plan

## 1. What exists today

| Layer | Current | Size |
|---|---|---|
| Backend | Flask 2.2 + Flask-SQLAlchemy (SQLAlchemy 2.0), Flask-JWT-Extended, gunicorn behind nginx | ~15k lines Python, 13 blueprints, ~140 API endpoints |
| DB | MySQL (`germanato_db`) via PyMySQL; schema from `db.create_all()` + ~20 hand-rolled `migrate_*.py` / `fix_*.sh` scripts (alembic folder exists but holds one stale revision) | 26 models in `backend/models.py` |
| Frontend | 32 static HTML pages in `backend/frontend/`, served by one Flask route each; vanilla JS per page (`backend/static/js/`, ~16k lines), per-page CSS, vendored Chart.js / jsPDF / html2canvas / SheetJS | largest: `repairOrder.js` 2.1k, `inventory.js` 2.1k, `invoiceShared.js` 1.3k, `invoice-template.html` 1.5k |
| Auth | JWT access+refresh in `localStorage`, `Authorization` header; RBAC = role + `role_permissions` table, mapped by URL prefix in `jwt_auth.PATH_PERMISSIONS` | |
| Integrations | Twilio/WhatsApp notifications; ZKTeco biometric devices PUSH to `/iclock/getrequest` and `/iclock/cdata` (plain-text protocol, must answer `OK`) | |

Domains: invoices/quotes, repair orders, inventory (+ transactions/history, barcodes, low-stock print), customers/cars, expenses (daily/major), cash received, vendors (ledger, POs, consignments), HR (workers, attendance, advances, payroll), reports/monthly ledger, financial period lock, settings, admin logs, WhatsApp.

### Things worth knowing before porting
- **Pure business logic is already Flask-free** and moves as-is: `invoice_math.py`, `payroll.py`, `petty_cash.py`, `inventory_utils.py`, `inventory_transaction_utils.py`, `repair_order_inventory_utils.py`, `document_links.py`, `search_suggestions.py`, `whatsapp_notifications.py`. Only `period_lock.py` and `log_utils.py` touch `flask.request`.
- **Stock updates have no row locking** (no `with_for_update` anywhere). Two simultaneous invoices for the same part can oversell. Fix during the port, not after.
- `WhatsAppNotification` is defined twice (`models.py:371` and `whatsapp_notification_model.py:10`). Keep one.
- Debug endpoints (`/api/workers/debug`, `/api/workers/test-auth`) should not be carried over.
- Weak defaults: `SECRET_KEY`/`JWT_SECRET_KEY` fall back to hard-coded strings; CORS is `*` with credentials. Fail fast on missing secrets in the new app.
- Routes are mounted inconsistently (`vendor_bp`, `hr_bp` at `''`, rest at `/api`). Normalize everything under `/api` except `/iclock/*`.

## 2. Target architecture

```
germanato/
  api/                    FastAPI (Python 3.12)
    app/main.py           app factory, CORS, routers
    app/db.py             SQLAlchemy 2.0 engine + session dependency
    app/models.py         ported from backend/models.py (plain SQLAlchemy, no Flask-SQLAlchemy)
    app/auth.py           JWT + RBAC dependency (port of jwt_auth.py)
    app/routers/          one file per current blueprint
    app/services/         the Flask-free modules listed above, moved verbatim
    alembic/              migrations, starting from the 0001 baseline
  web/                    Next.js (App Router, TypeScript)
    app/(auth)/login
    app/(shell)/…         one route per current HTML page, sharing the sidebar layout
    lib/api.ts            typed fetch client (generated from FastAPI OpenAPI)
```

Decisions (with reasons):
- **PostgreSQL, starting from an empty database.** The app is being built new, so no existing MySQL data is carried over. The Flask app already runs on Postgres (Phase 0b), so the FastAPI port starts there.
- **Sync SQLAlchemy in FastAPI** (`def` endpoints, threadpool). Existing queries port line-for-line; async buys nothing for a single-shop ERP.
- **Pydantic schemas** for request/response — replaces manual `request.get_json()` parsing and `to_dict()` methods; gives OpenAPI → generated TS client (`openapi-typescript`).
- **Auth: move tokens from `localStorage` to httpOnly cookies** set by FastAPI; Next.js `proxy.ts` only checks cookie presence and redirects to `/login`. Permissions still enforced server-side by a FastAPI dependency `require_permission("inventory")` replacing the URL-prefix table.
- **Next.js as a client-heavy app**: pages are data-entry screens; use Server Components for the shell/layout and `'use client'` for forms. TanStack Query for fetching/caching, a light component lib (shadcn/ui) for tables, dialogs, forms.
- **Printing/PDF**: keep browser print with print CSS for invoice/repair-order/low-stock templates (`window.print()`); drop html2canvas+jsPDF unless a downloadable PDF is required. Excel export: keep SheetJS (npm `xlsx`) or move to server-side `openpyxl` endpoints.
- **Same origin in prod**: nginx routes `/api/*` and `/iclock/*` → FastAPI (uvicorn/gunicorn), everything else → Next.js (`next start`). No CORS needed. ZKTeco devices keep the same URL.

## 3. Phases (strangler pattern — old app keeps running until each page is replaced)

### Phase 0 — Groundwork (≈1 week)

**Status (2026-10-28): done.**
- `backend/alembic/versions/0001_baseline_baseline_schema.py`: 27 tables, autogenerated from `models.py`; `alembic check` reports no drift. Replaces the old unused `20230829_01` revision.
- `backend/tests/`: 11 pytest tests covering ~60 GET endpoints plus write flows (customer → car → inventory → invoice/quote → repair order, expenses, cash, vendors/ledger/POs, workers/attendance/advances/payroll, period lock, ZKTeco `/iclock`). JSON response shapes are frozen in `tests/contracts/*.json`.
- Run: `cd backend && pip install -r requirements-dev.txt && pytest tests` (SQLite in memory; set `DATABASE_URL` to a throwaway Postgres or MySQL DB to run there; all 11 pass on SQLite, MySQL 5.7 and Postgres 15).

New database:
```bash
cd backend
DATABASE_URL=postgresql://USER:PASS@HOST/germanato_db alembic upgrade head
python create_admin_user.py
```
Schema changes from now on are `alembic revision --autogenerate` + `alembic upgrade head`, not new `migrate_*.py` scripts.

### Phase 0b — MySQL → PostgreSQL (done locally, 2026-10-28)
- Driver is psycopg 3. `config.database_url()` rewrites `postgres://` / `postgresql://` URLs to `postgresql+psycopg://`; alembic uses the same helper.
- Fixed for Postgres:
  - `reports_routes.py`: `HAVING` used a SELECT alias (Postgres rejects it); low-stock ordering used integer division (floors on Postgres).
  - Login/registration: username and email lookups are case-insensitive, as MySQL's collation made them.
  - Lists that relied on MySQL's implicit id order (users, customers, cars, low stock, devices, and invoice/repair-order line items) now `ORDER BY id`. Postgres moves updated rows to the end.
- Not covered: other string `==` lookups that used to be case-insensitive (vendor/customer duplicate checks, exact-match filters). Searches already use `ilike`. The shell deploy/backup scripts (`deploy.sh`, `safe_db_migration*.sh`, `database_optimization.sh`, …) are still MySQL-only.
- No data is migrated. The root-level `migrate_*.py`, `fix_*`, `backfill_*` and `import_cleaned_inventory.py` scripts only repaired old MySQL data and can be deleted.

Original steps:
1. Snapshot prod schema (`mysqldump --no-data`) and create an **Alembic baseline** that matches it exactly; retire `migrate_*.py`/`fix_*.sh` into `scripts/legacy/`.
2. Add a smoke test suite against the *current* Flask API (pytest + a test MySQL DB): one happy-path test per endpoint group, plus the existing `test_permissions_matrix.py` and report verification scripts. These become the contract the FastAPI port must pass.
3. Pick a frozen JSON contract: the new API returns the **same response shapes** as Flask so the old pages can be pointed at it unchanged.

### Phase 1 — FastAPI backend, drop-in replacement (≈3–4 weeks)
Port routers in dependency order; each one goes live behind nginx as soon as its tests pass (nginx routes that prefix to FastAPI, the rest stays on Flask):

| Order | Router | Source | Notes |
|---|---|---|---|
| 1 | auth, users, role permissions | `auth_routes_jwt.py`, `jwt_auth.py` | PyJWT or `fastapi-users`-free hand-rolled; keep token claims identical so both apps accept the same tokens during cut-over |
| 2 | settings, categories, departments, period lock, app logs | `settings_routes.py`, `period_lock.py`, `log_utils.py` | period lock becomes a dependency |
| 3 | customers & cars | `car_routes.py` | |
| 4 | inventory + transactions | `inventory_routes.py`, inventory utils | add `SELECT … FOR UPDATE` on stock rows |
| 5 | invoices & quotes | `routes.py`, `invoice_math.py` | |
| 6 | repair orders | `repair_order_routes.py`, `repair_order_inventory_utils.py` | |
| 7 | expenses, cash received | `expense_routes.py`, `cash_received_routes.py`, `petty_cash.py` | |
| 8 | vendors, ledger, POs | `vendor_routes.py` | |
| 9 | HR, attendance, payroll, ZKTeco `/iclock/*` | `hr_routes.py`, `payroll.py` | `/iclock` returns `PlainTextResponse("OK")` always |
| 10 | reports | `reports_routes.py` | run `verify_all_reports.py` against both and diff |
| 11 | WhatsApp | `whatsapp_routes.py`, `whatsapp_notifications.py` | send in `BackgroundTasks` |

Exit criteria: Flask serves only HTML/static; all `/api` traffic is FastAPI; smoke tests green.

### Phase 2 — Next.js frontend (≈5–7 weeks)
1. Scaffold `web/`: App Router, TS, Tailwind, shadcn/ui, TanStack Query, generated API client. Port `theme.css` tokens and `app-shell` sidebar into the root layout; read permissions once and hide nav items (server still enforces).
2. Switch auth to httpOnly cookies (FastAPI sets them on `/api/auth/login`; `proxy.ts` guards routes).
3. Port pages, simplest-first to establish patterns, heaviest last. nginx sends each migrated path to Next.js:
   - Wave A (lists/CRUD): login, home/dashboard, vendors, vendor detail, employees/HR, worker detail, attendance, device management, settings, admin, WhatsApp notifications, pending quotes
   - Wave B (finance): daily expenses, major expenses, finance management, monthly ledger, salaries, reports (Chart.js → `react-chartjs-2` or Recharts)
   - Wave C (heavy forms): inventory + history + low-stock print, car/customer, invoice & quote create/edit, invoice management, repair order + management
   - Wave D (print templates): invoice template, repair-order template → print-styled routes
4. Old URLs (`/inventory.html` etc.) → permanent redirects to new routes.

Exit criteria: Flask process removed; `backend/frontend` and `backend/static/js` deleted.

### Phase 3 — Deploy & cleanup (≈1 week)
- systemd units: `germanato-api` (gunicorn + `uvicorn.workers.UvicornWorker`) and `germanato-web` (`next start`, or `output: 'standalone'`); update `deploy.sh`/`release.sh` and nginx config.
- Remove one-off root scripts once confirmed unused; keep `.env.example` for both apps.
- CI: pytest for API, `tsc --noEmit` + lint + build for web.

## 4. Effort & risk summary

Rough total: **10–13 weeks for one developer**, delivered incrementally with production never fully cut over in one jump.

| Risk | Mitigation |
|---|---|
| Behaviour drift in money/stock math | Business modules moved verbatim; contract tests against Flask before switching each prefix; report diff script |
| Biggest pages (repair order, inventory, invoice) hide undocumented logic in 2k-line JS files | Port last, after patterns are settled; read each JS file end-to-end and list its API calls before rewriting |
| Auth cut-over logs everyone out | Keep JWT claims/secret identical in Phase 1; switch to cookies only in Phase 2 with a one-time re-login |
| ZKTeco devices break | `/iclock/*` path and plain-text `OK` responses unchanged; test with `zkteco_push_server.py` payloads |
