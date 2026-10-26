# GermanATO — Gap report (16 target features + foundation)

Status key: **Done** / **Partial** / **Missing**

Last updated: customer & vehicle management (phone search, multi-vehicle, job-card reuse).

---

## Target product features

| # | Feature | Status | Files involved | What's needed |
|---|---------|--------|----------------|---------------|
| 1 | Car entry-to-exit printable docs | **Partial** | check-in sheet on `CarDetailPage`, RO/invoice prints still separate | Check-in printable sheet Done; full entry→exit packet across stages still open |
| 2 | Car history | **Done** | `car_ownership.build_car_history`, `GET /cars/{id}/history`, `CarDetailPage.tsx`, search via plate/VIN/customer | Timeline includes visits/comebacks, quotes, ROs, invoices, payments, parts, ownership; filters + document links |
| 3 | Inventory via PO | **Done** | `models.PurchaseOrder`, `stock.py`, `POST /api/purchase-orders/{id}/receive`, `VendorDetailPage` | Draft→Ordered→partial/Received→Closed; GRN updates qty + avg_cost only; receipt required; vendor payable on receive |
| 4 | Job card → quotation (advance) → RO → invoice | **Partial** | `QuoteCreatePage`, `PendingQuotesPage`, `RepairOrder*`, `Invoice*`, `invoices.py`, `repair_orders.py` | Quotes (`type_of=quote`), advance on invoice, ROs, invoices exist as parallel docs; no enforced job-card entity or strict pipeline state machine |
| 5 | Barcode inventory | **Done** | `Inventory.barcode`, lookup + `create_prefill`, label print, `InventoryPage` scan UX | Unknown code prefills create form; USB scanner Enter; label print payload + window print |
| 6 | Car transfer | **Done** | `models.CarOwnership`, `car_ownership.transfer_car_ownership`, `POST /cars/{id}/transfer`, `CarDetailPage` transfer tab | Evidence required; audit logged; invoices stay with original customer; rejects same/deleted owners |
| 6b | Visit / check-in inspection | **Done** | `models.Visit` / `VisitInspectionItem` / `InspectionTemplate`, `visits.py`, `POST /cars/{id}/visits`, `CarDetailPage` check-in tab, printable sheet | Configurable multi-point checklist, photos, canvas signature, camera capture; signature+inspection required before job card when `car_id` set |
| 7 | Error prevention | **Partial** → improved | `period_lock.py`, `foundation/*`, validation, idempotency, soft-delete, version, stock guards, `entities` duplicate check | Month lock + uniqueness + foundation guards + duplicate warnings API; remaining: wider Zod form wiring on every page |
| 7b | Shared data foundation | **Done** | `document_numbers.py`, `routers/entities.py`, `EntitySelect`, `migrate_shared_foundation.py`, gate_pass | Permanent codes (CN/VH/VN/INV/QT/RO/EXP/CR/PO/GP); searchable selectors; customer→vehicles bundle; actor stamps; gate pass |
| 8 | Branch hex id | **Done** | `foundation/branch.py`, `foundation/scope.py`, `foundation/hooks.py`, `main.py` middleware, `migrate_foundation.py` | 8-char hex branch, default seed `a1b2c3d4`, auto-assign on create, ORM list scoping via session hooks + `X-Branch-Id` |
| 9 | Offline / cloud sync | **Missing** | — | No sync queue, conflict resolution, or offline client store (ZKTeco `last_sync` is device attendance only) |
| 10 | Finance transparency with evidence | **Partial** | `VendorLedger.attachment_path`, `foundation/attachments.py`, PO GRN receipt | Vendor ledger + PO receive evidence; expenses/cash/invoices still next |
| 11 | Money In page | **Partial** | `CashReceivedPage.tsx`, `routers/cash_received.py`, `FinanceHubPage.tsx` | Cash received page exists; not branded/unified as “Money In” covering all inflow types |
| 12 | Money Out page | **Partial** | `ExpensesPage.tsx` (daily/major), salaries via HR; vendor payable from GRN | Expenses exist; GRN feeds vendor ledger; no single “Money Out” facade yet |
| 13 | WhatsApp | **Done** | `whatsapp_notifications.py`, `routers/whatsapp.py`, `WhatsAppPage.tsx` | Notifications, history, resend, test connection; Twilio optional (logs if unset) |
| 14 | Monthly / yearly closing | **Partial** | `FinancialPeriod`, `period_lock.py`, `routers/periods.py`, `MonthlyLedgerPage.tsx` | Monthly open/close exists; no formal yearly close / retained-earnings workflow |
| 15 | Full reports | **Partial** | `routers/reports.py`, `ReportsPage.tsx` | Aggregations exist; branch-aware ORM lists apply via hooks, but raw SQL report paths may still need explicit `branch_id` filters |
| 15b | Live home dashboard | **Done** | `app/dashboard.py`, `GET /api/dashboard`, `DashboardPage.tsx` | Role views (reception/tech/store/accountant/manager); date filters; KPIs from DB (revenue ≠ cash ≠ receivables ≠ advances ≠ payables ≠ cash position); charts; alerts; searchable lists; quick actions; cards deep-link to filtered pages |
| 16 | Customer & vehicle management | **Done** | `models.Customer`/`Car`, `customer_vehicle.py`, `migrate_customers_vehicles.py`, `CarsPage`, `CustomerDetailPage`, job-card EntitySelect | Phone-first search + duplicate warn; alternate phone, type, notes, consent; year/engine/notes on vehicle; multi-vehicle; profile with balances/ROs/quotes/invoices; intake reuses plate/VIN; job card autofills + links existing FKs only |

---

## Foundation checklist (blocking later modules)

| Foundation item | Status | Files | Notes |
|-----------------|--------|-------|-------|
| `branch_id` (8-char hex) + default seed | **Done** | `models.Branch`, `foundation/branch.py`, `foundation/scope.py`, `foundation/hooks.py`, `deps.get_branch_id`, middleware | Shared hooks auto-assign on insert + filter lists (`do_orm_execute` / `scoped_query`); no per-router copy-paste |
| Base columns: id, created_at/by, updated_at/by, version, deleted_at | **Done** (additive) | `FoundationMixin`, migration | Integer ids kept; `version` + `deleted_at` on business tables |
| Audit log (who/what/old/new/reason) | **Done** | `foundation/audit.py`, `foundation/hooks.py`, `foundation/overrides.py` | Auto audit on flush; reason required for price/discount-above-threshold/stock/deletes/payment-gate/evidence/period-reopen |
| Money as integer paisa | **Partial** | `foundation/money.py`, `shared/src/money.ts` | Helpers ready; legacy Float/Numeric columns unchanged (data-safe) |
| Shared validation + DB constraints | **Done** | `foundation/validation.py`, `schemas_foundation.py`, `shared/src/validation.ts`, CHECK migration | PK phone E.164, reg no, CNIC, non-negative qty/price; DB CHECKs on key tables |
| Reusable attachment / evidence service | **Partial** | `foundation/attachments.py`, `models.Attachment`, car transfer + PO GRN receipt | Wired for transfers + PO receive; expenses/cash/invoices still next |
| Role / permission map | **Done** | `foundation/roles.py`, `deps.require_permissions`, `AdminPage.tsx` | Includes granular: `approve_discount`, `override_payment_gate`, `qc_signoff`, `adjust_stock`, `reopen_period`, `approve_evidence_exception` |
| Soft delete everywhere | **Done** | `foundation/hooks.py` (`Session.delete`), `soft_delete.py` | Hard `db.delete` → soft when `deleted_at` exists; lists exclude deleted |
| Optimistic locking (`version`) | **Done** | `foundation/versioning.py`, update routes (cars/expenses/invoices/inventory), `web/src/api/client.ts` 409 | 409 + `VersionConflictError` on client |
| Idempotency-Key on creates | **Done** | `foundation/idempotent.py` (sync+async), invoices/expenses/cash-received/POs/receive + invoice payment PUT | Header honored; client auto-sends on `api.post` / `api.putIdempotent` |
| Workshop settings thresholds | **Done** | `models.AppSetting`, `foundation/settings.py`, `GET/PUT /api/settings/workshop`, `SettingsPage` | Defaults: discount approval 10%, receipt Rs 500, comeback 14d, payment gate on, expense heads list |

---

## Inventory / stock ledger

| Item | Status | Notes |
|------|--------|-------|
| StockMovement via `inventory_transactions` | **Done** | Types: `po_receive`, `reserve`, `release`, `issue_to_ro`, `return_from_ro`, `adjustment` (+ legacy) |
| on_hand / reserved / available | **Done** | `Inventory.quantity` = on_hand; `reserved`; available computed |
| avg_cost on GRN only | **Done** | `stock.compute_avg_cost` / `po_receive`; PUT blocks direct qty/avg_cost |
| Adjustments | **Done** | `POST /api/inventory/adjust` — reason + evidence + `adjust_stock` |
| Parts min/max, supersession, alternates | **Done** | `min_level`/`max_level`, `superseded_by_id`, `alternate_codes` |
| Reorder → draft POs | **Done** | `GET .../reorder-suggestions`, `POST .../draft-pos` |
| Part ownership + old-parts-returned | **Done** | `RepairOrderPart.ownership_type`, `old_parts_returned`; customer_supplied skips stock |
| Pending purchase inline item | **Done** | `POST /api/inventory/pending-item` |
| Migration | **Done** | `api/migrate_inventory.py` (additive, re-runnable) |

---

## Tests / CI

| Item | Status |
|------|--------|
| Automated test suite | **Partial** → expanded — foundation + car transfer/history + visits + **stock** (`test_stock.py`: avg cost, partial receive, reserve/issue/return, negatives) |
| Lint | `web`: `oxlint` |
| Build | `web`: `tsc -b && vite build` |
