# GermanATO — Gap report

Status key: **Done** / **Partial** / **Missing**

Last updated: merged **design** (shell, pipeline, Money In/Out) with **mk** (customers/vehicles, stock ledger, live dashboard).

---

## Target product features

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 1 | Entry-to-exit printables | **Partial** | Shared A4 CSS + packet; more stage polish open |
| 2 | Car history | **Done** | |
| 3 | Inventory via PO | **Done** | GRN via `stock.po_receive` + receipt; shortages → draft POs |
| 4 | Job card → quote → RO → invoice chain | **Done** | + next-action banner |
| 5 | Barcode inventory | **Done** | Field + scan + label UX |
| 6 | Car transfer | **Done** | |
| 6b | Visit / check-in | **Done** | |
| 7 | Error prevention | **Done** | Foundation + wired overrides |
| 7b | Shared data foundation | **Done** | Document codes, EntitySelect, entities API |
| 8 | Branch hex id | **Done** | |
| 9 | Offline sync | **Missing** | Deferred |
| 10 | Finance evidence | **Partial** | Transfers + PO GRN receipt; expenses optional next |
| 11 | Money In | **Done** | `/money-in` facade |
| 12 | Money Out | **Done** | `/money-out` facade (payroll separate) |
| 13 | WhatsApp | **Done** | |
| 14 | Monthly / yearly close | **Partial** | Monthly exists; yearly open |
| 15 | Full reports | **Partial** | Live dashboard + invoices CSV; more exports open |
| 15b | Live home dashboard | **Done** | Role views + charts + `workshop_kpis` |
| 16 | Customer & vehicle management | **Done** | Phone search, multi-vehicle, CustomerDetail |
| Design system | Shell + tokens | **Done** | Orange/black/off-white, Montserrat / Source Code Pro |

---

## Foundation

All foundation checklist items remain **Done** (branch, audit, soft delete, version, idempotency, settings, granular perms, validation CHECKs). Money-as-paisa still **Partial** (helpers only).

## Pipeline

Labour codes, job cards, WhatsApp line approval, deposits, reserve/issue/return, variations, QC, invoice lock, payment gate, gate pass, legacy visit backfill — **Done**. Next-action API — **Done**.

## Inventory / stock ledger

| Item | Status | Notes |
|------|--------|-------|
| StockMovement via `inventory_transactions` | **Done** | `po_receive`, reserve/release/issue/return, adjustment |
| on_hand / reserved / available | **Done** | `Inventory.quantity` = on_hand; `reserved`; available computed |
| avg_cost on GRN only | **Done** | `stock.compute_avg_cost` / `po_receive` |
| Adjustments | **Done** | reason + `adjust_stock` override |
| Reorder → draft POs | **Done** | |
| Part ownership + old-parts-returned | **Done** | |
| Migration | **Done** | `migrate_inventory.py` + `migrate_pipeline.py` |

## Docs

- Root `design.md`, `architecture.md`
- This gap report
- `docs/SHARED_DATA_FOUNDATION.md`

## Tests / CI

| Item | Status |
|------|--------|
| pytest | foundation + pipeline + stock + customer/vehicle + dashboard/PO/money/next_action |
| Lint | `oxlint` |
| Build | `tsc -b && vite build` |
