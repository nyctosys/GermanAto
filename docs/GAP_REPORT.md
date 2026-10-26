# GermanATO — Gap report

Status key: **Done** / **Partial** / **Missing**

Last updated: merged **design** (shell, pipeline, Money In/Out) with **mk** (customers/vehicles, stock ledger, live dashboard).

---

## Target product features

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 1 | Entry-to-exit printables | **Partial** | Shared A4 CSS + packet; more stage polish open |
| 2 | Car history | **Done** | |
| 3 | Inventory via PO | **Done** | GRN via `GoodsReceipt` + `stock.po_receive`; shortages → draft POs; supplier invoice/payment/credit separate |
| 4 | Job card → quote → RO → invoice chain | **Done** | + next-action banner; invoice mgmt below |
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

## Invoice management

| Item | Status | Notes |
|------|--------|-------|
| Generate from approved estimate | **Done** | Convert quote→invoice; recalc after rejected lines |
| Unique doc # / customer / vehicle / RO links | **Done** | `document_no` INV-#####; search by number |
| Auto totals (due / paid / unpaid) | **Done** | `invoice_math` + UI columns |
| Accrual on finalize | **Done** | `CustomerLedger` debit once on convert/create; payments credit AR only |
| Cash ≠ re-recognize revenue | **Done** | Payments / deposit apply never change `net_total` |
| Partial payments | **Done** | `update-balance` + management UI |
| Credit notes / authorized reversal | **Done** | `POST /invoice/{id}/credit-note` |
| One invoice per RO | **Done** | 409 duplicate guard |
| Print | **Done** | `/invoices/:id/print` PrintShell |
| Search | **Done** | Name, phone, plate, INV-#, status, dates |
| Payment lock | **Done** | Unpaid editable; locks on partial/full payment; credit note after lock |
| Migration | **Done** | `migrate_invoice_management.py` |

## Repair Execution

| Item | Status | Notes |
|------|--------|-------|
| Technician board (`/repair-execution`) | **Done** | Assigned/open jobs, vehicle, progress, deadlines, job cost |
| Workbench (`/repair-orders/:id/execution`) | **Done** | Tasks, parts, faults, notes/photos, submit for inspection |
| Start / pause / resume / record time | **Done** | Clock + Add hours / Set total; manual entry auto-pauses open clock |
| Labour cost = rate × actual hours | **Done** | Uses `LabourCode.rate` / line rate; updates RO totals |
| Payroll hours separate | **Done** | Repair time never feeds attendance / payroll |
| Approval gate on variation work | **Done** | `assert_line_workable`; faults → variation |
| Parts issue / return on RO | **Done** | `stock.issue_to_ro` / `return_from_ro`; over-issue blocked |
| Promote approved variations | **Done** | Adds RO labour/parts after customer approval |
| Migration | **Done** | `migrate_repair_execution.py` |

## Inventory / stock ledger

| Item | Status | Notes |
|------|--------|-------|
| StockMovement via `inventory_transactions` | **Done** | `po_receive`, reserve/release/issue/return, `return_to_vendor`, adjustment, wastage, opening |
| on_hand / reserved / available | **Done** | `Inventory.quantity` = on_hand; `reserved`; available computed |
| Unit + pack conversion | **Done** | `unit`, `pack_size`; 3 packs × 10 = 30 base pcs (`to_base_pieces`) |
| Valuation | **Done** | Weighted avg; `GET /inventory/valuation`; method field defaults `avg` |
| Opening stock via ledger | **Done** | Create with qty/packs posts `opening` movement (not silent qty write) |
| Wastage | **Done** | `POST /inventory/wastage` |
| Barcode scan + search + saved units | **Done** | Scan panel; list search; `/inventory/units` |
| Movement history | **Done** | Real ledger types + actor; History UI filters fixed |
| avg_cost on GRN only | **Done** | `stock.compute_avg_cost` / `po_receive` |
| Adjustments | **Done** | reason + evidence + `adjust_stock`; optional negative override flag |
| Reorder → draft POs | **Done** | Inventory UI + `/reorder-suggestions/draft-pos` |
| Part ownership + old-parts-returned | **Done** | |
| Repair issue / return / reserve | **Done** | Execution path via `stock.*`; issued ≠ consumed (issued − returned) |
| Preferred supplier on item | **Partial** | `preferred_vendor_id` column; UI select optional next |
| Legacy restock/deduct paths | **Partial** | Prefer `stock.*` / PO receive; legacy endpoints still present |
| Migration | **Done** | `migrate_inventory.py` + `migrate_inventory_store.py` |

## Vendor / PO / AP (procurement)

| Item | Status | Notes |
|------|--------|-------|
| Vendor contacts + payment terms | **Done** | `payment_terms_days`, bank details, notes; search/create once |
| PO commitment only | **Done** | Draft → approve → order; expected delivery; known-rate autofill |
| Goods receipt (separate) | **Done** | `goods_receipts`; stock + avg_cost; **no payable** |
| Supplier invoice → payable | **Done** | `supplier_invoices` + VendorLedger debit; due from terms |
| Supplier payment | **Done** | `supplier_payments` + ledger credit; allocates to invoice |
| Returns / credit notes / refunds | **Done** | `supplier_credit_notes` + `return_to_vendor` |
| Statement + outstanding | **Done** | `/statement`, summary, CSV export on vendor detail |
| Overdue payables report | **Done** | `/api/reports/overdue-payables` + Reports UI |
| Price override permission | **Done** | `override_po_price`; approve via `approve_po` |
| Migration | **Done** | `migrate_procurement.py` |

## Docs

- Root `design.md`, `architecture.md`
- This gap report
- `docs/SHARED_DATA_FOUNDATION.md`

## Tests / CI

| Item | Status |
|------|--------|
| pytest | foundation + pipeline + stock + procurement + customer/vehicle + dashboard/PO/money/next_action |
| Lint | `oxlint` |
| Build | `tsc -b && vite build` |
