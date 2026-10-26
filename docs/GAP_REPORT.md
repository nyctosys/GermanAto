# GermanATO — Gap report

Status key: **Done** / **Partial** / **Missing**

Last updated: design system + KPI dashboard + PO receive + Money In/Out + next-action UX.

---

## Target product features

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 1 | Entry-to-exit printables | **Partial** | Shared A4 CSS + packet; more stage polish open |
| 2 | Car history | **Done** | |
| 3 | Inventory via PO | **Done** | `POST /purchase-orders/{id}/receive`, shortages → draft POs |
| 4 | Job card → quote → RO → invoice chain | **Done** | + next-action banner |
| 5 | Barcode inventory | **Partial** | Field + scan; label UX open |
| 6 | Car transfer | **Done** | |
| 6b | Visit / check-in | **Done** | |
| 7 | Error prevention | **Done** | Foundation + wired overrides |
| 8 | Branch hex id | **Done** | |
| 9 | Offline sync | **Missing** | Deferred |
| 10 | Finance evidence | **Partial** | Deposits/transfers; expenses optional next |
| 11 | Money In | **Done** | `/money-in` facade |
| 12 | Money Out | **Done** | `/money-out` facade (payroll separate) |
| 13 | WhatsApp | **Done** | |
| 14 | Monthly / yearly close | **Partial** | Monthly exists; yearly open |
| 15 | Full reports | **Partial** | KPIs + invoices CSV export; more exports open |
| Design system | Shell + tokens | **Done** | Orange/black/off-white, Montserrat / Source Code Pro |

---

## Foundation

All foundation checklist items remain **Done** (branch, audit, soft delete, version, idempotency, settings, granular perms, validation CHECKs). Money-as-paisa still **Partial** (helpers only).

## Pipeline

Labour codes, job cards, WhatsApp line approval, deposits, reserve/issue/return, variations, QC, invoice lock, payment gate, gate pass, legacy visit backfill — **Done**. Next-action API — **Done**.

## Docs

- Root `design.md`, `architecture.md`
- This gap report

## Tests / CI

| Item | Status |
|------|--------|
| pytest | foundation + pipeline + dashboard/PO/money/next_action |
| Lint | `oxlint` |
| Build | `tsc -b && vite build` |
