# GermanATO — Gap report (16 target features + foundation)

Status key: **Done** / **Partial** / **Missing**

Last updated: car transfer + unified car history API/UI.

---

## Target product features

| # | Feature | Status | Files involved | What's needed |
|---|---------|--------|----------------|---------------|
| 1 | Car entry-to-exit printable docs | **Partial** | `web/src/pages/CarsPage.tsx`, `RepairOrdersPage.tsx`, `Invoice*`, `api/app/routers/cars.py`, `repair_orders.py`, `invoices.py` | CRUD + RO status timeline exist; no dedicated entry/exit printable packet or unified print templates across stages |
| 2 | Car history | **Done** | `car_ownership.build_car_history`, `GET /cars/{id}/history`, `CarDetailPage.tsx`, search via plate/VIN/customer | Unified timeline (quotes, ROs, invoices, payments, parts, odometer/tech, ownership); filters + document links |
| 3 | Inventory via PO | **Partial** | `models.PurchaseOrder`, `routers/vendors.py`, `VendorsPage` / `VendorDetailPage` | Vendor PO/consignment records exist; not a full PO → receive → stock-update workflow tied to `Inventory` qty |
| 4 | Job card → quotation (advance) → RO → invoice | **Partial** | `QuoteCreatePage`, `PendingQuotesPage`, `RepairOrder*`, `Invoice*`, `invoices.py`, `repair_orders.py` | Quotes (`type_of=quote`), advance on invoice, ROs, invoices exist as parallel docs; no enforced job-card entity or strict pipeline state machine |
| 5 | Barcode inventory | **Partial** | `models.Inventory.barcode`, `routers/inventory.py` (lookup/receive by barcode), `InventoryPage.tsx` | Barcode field + scan/receive endpoints exist; no dedicated barcode label print / gun UX polish |
| 6 | Car transfer | **Done** | `models.CarOwnership`, `car_ownership.transfer_car_ownership`, `POST /cars/{id}/transfer`, `CarDetailPage` transfer tab | Evidence required; audit logged; invoices stay with original customer; rejects same/deleted owners |
| 7 | Error prevention | **Partial** → improved | `period_lock.py`, `foundation/*`, validation, idempotency, soft-delete, version | Month lock + uniqueness + foundation guards; remaining: wider Zod form wiring on every page |
| 8 | Branch hex id | **Done** | `foundation/branch.py`, `foundation/scope.py`, `foundation/hooks.py`, `main.py` middleware, `migrate_foundation.py` | 8-char hex branch, default seed `a1b2c3d4`, auto-assign on create, ORM list scoping via session hooks + `X-Branch-Id` |
| 9 | Offline / cloud sync | **Missing** | — | No sync queue, conflict resolution, or offline client store (ZKTeco `last_sync` is device attendance only) |
| 10 | Finance transparency with evidence | **Partial** | `VendorLedger.attachment_path`, `foundation/attachments.py` | Vendor ledger attachments + Attachment service; expenses/cash/invoices not fully wired to evidence yet |
| 11 | Money In page | **Partial** | `CashReceivedPage.tsx`, `routers/cash_received.py`, `FinanceHubPage.tsx` | Cash received page exists; not branded/unified as “Money In” covering all inflow types |
| 12 | Money Out page | **Partial** | `ExpensesPage.tsx` (daily/major), salaries via HR | Expenses exist; no single “Money Out” facade covering expenses + payroll + vendor payments |
| 13 | WhatsApp | **Done** | `whatsapp_notifications.py`, `routers/whatsapp.py`, `WhatsAppPage.tsx` | Notifications, history, resend, test connection; Twilio optional (logs if unset) |
| 14 | Monthly / yearly closing | **Partial** | `FinancialPeriod`, `period_lock.py`, `routers/periods.py`, `MonthlyLedgerPage.tsx` | Monthly open/close exists; no formal yearly close / retained-earnings workflow |
| 15 | Full reports | **Partial** | `routers/reports.py`, `ReportsPage.tsx` | Aggregations exist; branch-aware ORM lists apply via hooks, but raw SQL report paths may still need explicit `branch_id` filters |

---

## Foundation checklist (blocking later modules)

| Foundation item | Status | Files | Notes |
|-----------------|--------|-------|-------|
| `branch_id` (8-char hex) + default seed | **Done** | `models.Branch`, `foundation/branch.py`, `foundation/scope.py`, `foundation/hooks.py`, `deps.get_branch_id`, middleware | Auto-assign on insert; list queries scoped via `do_orm_execute` + `scoped_query` helper |
| Base columns: id, created_at/by, updated_at/by, version, deleted_at | **Done** (additive) | `FoundationMixin`, migration | Integer ids kept; `version` + `deleted_at` on business tables |
| Audit log (who/what/old/new/reason) | **Done** | `foundation/audit.py`, `foundation/hooks.py` (`before_flush`) | Automatic on create/update/delete; `X-Audit-Reason` required for price/stock/deletes |
| Money as integer paisa | **Partial** | `foundation/money.py`, `shared/src/money.ts` | Helpers ready; legacy Float/Numeric columns unchanged (data-safe) |
| Shared validation + DB constraints | **Done** | `foundation/validation.py`, `schemas_foundation.py`, `shared/src/validation.ts`, CHECK migration | PK phone E.164, reg no, CNIC, non-negative qty/price; DB CHECKs on key tables |
| Reusable attachment / evidence service | **Partial** | `foundation/attachments.py`, `models.Attachment`, car transfer evidence | Wired for car ownership transfers; expenses/cash/invoices still next |
| Role / permission map | **Done** | `foundation/roles.py`, `routers/auth.py`, `AdminPage.tsx` | Owner/Manager/Accountant/Service Advisor/Technician/Store Keeper (+ legacy names) |
| Soft delete everywhere | **Done** | `foundation/hooks.py` (`Session.delete`), `soft_delete.py` | Hard `db.delete` → soft when `deleted_at` exists; lists exclude deleted |
| Optimistic locking (`version`) | **Done** | `foundation/versioning.py`, update routes (cars/expenses/invoices/inventory), `web/src/api/client.ts` 409 | 409 + `VersionConflictError` on client |
| Idempotency-Key on creates | **Done** | `foundation/idempotent.py`, invoices/expenses/cash-received/POs | Header honored; client auto-sends UUID on `api.post` |

---

## Tests / CI

| Item | Status |
|------|--------|
| Automated test suite | **Partial** → expanded — `api/tests/` covers money, validation, scope/soft-delete/version, idempotency/audit, car transfer rules + history ordering |
| Lint | `web`: `oxlint` (warnings only on pre-existing purity patterns) |
| Build | `web`: `tsc -b && vite build` |
