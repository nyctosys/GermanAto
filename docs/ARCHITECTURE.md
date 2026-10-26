# GermanATO — Architecture (as implemented)

This document describes **what exists in the repo today**, plus conventions for new code. It is not a greenfield redesign.

**Assumptions:** FastAPI + React remain the stack (do not replace with Express). Integer primary keys remain; ULID is a future convention for *new* tables only. Money remains Float/Numeric in existing columns; new money fields should use integer paisa via foundation helpers. Currency display is PKR.

---

## Stack

| Layer | Technology | Location |
|-------|------------|----------|
| Frontend | React 19, TypeScript, Vite 8, React Router 7, TanStack Query 5 | `web/` |
| Backend | FastAPI, SQLAlchemy 2, Pydantic Settings, python-jose JWT, passlib/bcrypt | `api/` |
| Database | PostgreSQL (Docker `germanato-db` or local) | `DATABASE_URL` in `api/.env` |
| Shared client schemas | Zod package `@germanato/shared` | `shared/` |
| Schema creation | `Base.metadata.create_all` on API startup | `api/app/main.py` lifespan |
| Additive migrations | `migrate_foundation.py`, `migrate_inventory.py`, `migrate_shared_foundation.py` | `api/migrate_*.py` |

There is **no Alembic**. There is **no Express/Node API**. There is **no monorepo workspace tooling** beyond `file:` dependency from `web` → `shared`.

---

## Folder map

```
Germanato/
  api/
    app/
      main.py              # FastAPI app, CORS, routers, error handlers
      config.py            # Settings from .env
      db.py                # engine, SessionLocal, Base, get_db
      models.py            # All SQLAlchemy models
      schemas.py           # Pydantic auth DTOs (partial coverage)
      deps.py              # JWT current user, require_roles
      security.py          # hash/verify password, JWT encode/decode
      log_utils.py         # AppLog writer + upload helper
      document_links.py    # Resolve customer/car for invoices & ROs
      period_lock.py       # Month close guards for finance writes
      invoice_math.py      # Invoice totals helpers
    inventory_*.py       # Stock / RO parts helpers
    repair_execution.py  # Technician time / parts / faults / job cost
    payroll.py, petty_cash.py
      whatsapp_notifications.py
      foundation/          # Branch, money (paisa), audit, attachments, roles, soft delete
      routers/             # HTTP endpoints by domain
    create_admin.py
    migrate_foundation.py
    tests/
    .env.example
  web/
    src/
      api/client.ts        # fetch wrapper, JWT refresh
      auth/                # AuthContext, ProtectedRoute
      components/ui.tsx    # Shared form/layout primitives
      layout/              # AppShell, nav (permission-gated)
      pages/               # One page module per route
      App.tsx, main.tsx, index.css, types.ts
  shared/                  # Zod schemas shared with web
  docs/
```

---

## Runtime shape

- API: `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
- Web: `npm run dev` → `http://localhost:5173`, Vite proxies `/api` and `/iclock` → `:8000`
- Default admin seed: `python create_admin.py` → `admin` / `admin123`
- Health: `GET /api/health`

---

## Data model overview (ERD sketch)

```
User ──< RolePermission (role, permission strings)
User ──< AppLog
Branch (8-char hex id) ── referenced by branch_id on business tables (foundation)

Customer ──< Car
Customer / Car ── linked from Invoice, RepairOrder (nullable FKs, SET NULL)

Invoice ──< InvoiceItem, InvoiceLabour
RepairOrder ──< RepairOrderPart, RepairOrderLabour
RepairOrderPart >── Inventory (optional)
Inventory ──< InventoryTransaction (stock movements: po_receive/reserve/release/issue_to_ro/return_from_ro/adjustment)
PurchaseOrder ── GoodsReceipt (GRN) → Inventory qty + avg_cost
SupplierInvoice → VendorLedger debit (payable); SupplierPayment → credit
SupplierCreditNote → return_to_vendor + ledger credit

Vendor ──< VendorLedger, PurchaseOrder, GoodsReceipt, SupplierInvoice
Worker ──< AttendanceRecord, SalaryAdvance, PayrollRun
ZKTecoDevice ──< AttendanceRecord
Expense, CashReceived, FinancialPeriod
WhatsAppNotification
Attachment (foundation evidence), IdempotencyKey (foundation)
```

**IDs:** Integer autoincrement PKs everywhere today.

**Timestamps:** Most tables have `created_at`; many have `updated_at`. Some documents store `created_by_user` / `updated_by_user` as username strings.

**Soft delete:** Not used historically (hard `db.delete`). Foundation adds optional `deleted_at` + helpers; existing delete routes still hard-delete until migrated per module.

**Optimistic lock:** Not used historically. Foundation adds optional `version` column.

**Money:** Invoice/expense/cash use `Float`; vendor ledger / PO / payroll use `Numeric(10,2)`. Values are treated as **PKR rupees with fractions**, not paisa. Foundation `money` helpers convert for *new* code.

**Branch:** Not present historically. Foundation adds `branch` table + `branch_id` (8-char hex) on business tables, default seed branch.

---

## Auth & permissions (actual)

- JWT access + refresh (`api/app/security.py`, `deps.py`).
- Roles historically: `admin`, `accountant`, `inventory_manager` (`VALID_ROLES` in `routers/auth.py`).
- Foundation extends roles: `owner`, `manager`, `service_advisor`, `technician`, `store_keeper` (see `foundation/roles.py`). `admin` remains Owner-equivalent; `inventory_manager` remains alias of Store Keeper.
- Permissions are string keys (`invoice`, `inventory`, `hr`, …) stored in `role_permissions` or defaults in `DEFAULT_ROLE_PERMISSIONS`.
- Route guards mostly use `require_roles([...])` (role allow-list), not permission keys. Nav uses permission keys via `AuthContext.canAccess`.
- Admin UI: `/admin` (`AdminPage.tsx`) manages users and role permission matrices.

---

## Validation (actual)

- **Server:** Mix of Pydantic models (`schemas.py` for auth) and ad-hoc `dict`/`Body` validation inside routers (cars, invoices, inventory, …).
- **Client:** Manual form state; little shared schema validation. `@germanato/shared` Zod schemas are the convention for new forms.
- **DB:** Some `UniqueConstraint` / unique columns (`part_number`, `barcode`, payroll month, etc.). Not comprehensive CHECKs for money ≥ 0.
- **Idempotency:** Not on create endpoints historically; foundation table + helper available for new creates.
- **Period lock:** `period_lock.py` blocks non-admin writes into closed months for guarded finance routes.

---

## Audit & uploads (actual)

- **Audit:** `AppLog` + `log_action()` / `document_log_entries()` in `log_utils.py`. Action/module/details/IP; **not** structured old/new/reason historically. Foundation extends columns + `audit_write`.
- **Uploads:** `save_uploaded_file()` → `api/app/static/uploads/`. Vendor ledger supports `attachment_path`. Inventory has `image_path`. Foundation `Attachment` model + `attachments` service for reusable evidence.

---

## Frontend conventions (actual)

- Pages own their React Query keys and call `api` directly (no separate `services/` layer yet).
- Shared UI: `components/ui.tsx` (`PageHeader`, `Panel`, `Field`, …).
- Auth gate: `ProtectedRoute` + shell filters nav by permission.
- Styling: global `index.css` (not Tailwind).

---

## Conventions for new code

1. **Do not rewrite working modules.** Prefer additive columns, helpers, and opt-in use.
2. **Branch:** Set `branch_id` on create (default branch if header absent). Filter list queries with `not_deleted` + `for_branch` helpers from `foundation`.
3. **Money:** Store new amounts as **integer paisa** (`money.to_paisa` / `from_paisa`). Display PKR with two decimals. Do not silently change existing Float columns without a data migration.
4. **Validation:** Add Zod in `shared/`; mirror critical rules in Pydantic or router checks. Disable submit until client schema succeeds.
5. **Writes:** Call `audit_write(...)` with old/new/reason on mutating endpoints. Prefer soft delete (`soft_delete`) over hard delete for new entities.
6. **Attachments:** Use `foundation.attachments` — do not invent new upload folders.
7. **Roles:** Use names from `foundation.roles`; keep `admin` working. Prefer expanding `require_roles` via role hierarchy helpers rather than duplicating permission logic.
8. **API style:** Prefer `/api/...` JSON `{ error: string }` on failure (existing handlers). Keep Vite proxy paths stable.
9. **Migrations:** Add SQL steps to `migrate_foundation.py` (or a new numbered script); do not rely on `create_all` alone for existing DBs.
10. **Tests:** Put unit tests under `api/tests/` for foundation helpers; keep them free of a live DB when possible.

---

## Known non-goals of the current foundation pass

- Replacing FastAPI with Express.
- Converting all existing money columns to paisa in place.
- Changing integer PKs to ULID.
- Offline/cloud sync.
- Rewriting every router to enforce branch scoping overnight (helpers + columns first).
