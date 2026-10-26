# Shared data foundation — schema & API notes

## Permanent codes (integer PKs kept)

| Entity | Column | Format | Notes |
|--------|--------|--------|-------|
| Customer | `code` | `CN{id:03d}` | Unique; backfilled |
| Car / vehicle | `code` | `VH{id:03d}` | Unique; backfilled |
| Vendor | `code` | `VN{id:03d}` | Unique; backfilled |
| Invoice | `document_no` | `INV-{id:05d}` or `QT-…` for quotes | Unique |
| Repair order | `document_no` | `RO-{id:05d}` | Unique |
| Expense | `document_no` | `EXP-{id:05d}` | Unique |
| Cash received | `document_no` | `CR-{id:05d}` | Unique |
| Purchase order | `document_no` | `PO-{id:05d}` | Alongside staff `invoice_no` |
| Gate pass | `document_no` | `GP-{id:05d}` | New table |
| Inventory | `part_number` | `PN###` (existing) | Unchanged |
| Worker | `employee_id` | existing unique | Display via helper |

Assigned automatically after insert (`after_flush` → `assign_document_numbers`).

## Actor fields

`created_by_user` / `updated_by_user` added where missing (customer, car, expense, cash_received, vendors) and stamped from JWT user on flush.

## Relationships reused

- Invoice / RepairOrder → `customer_id`, `car_id` (SET NULL)
- Car → `customer_id`
- GatePass → customer, car, optional visit, optional repair order
- Existing `document_links.apply_links` still links snapshot text to FKs

## APIs

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/entities/search?type=&q=` | Autocomplete for customer/car/worker/vendor/inventory |
| GET | `/api/entities/customers/{id}` | Customer + vehicles bundle |
| POST | `/api/entities/check-duplicate` | Duplicate warnings before create |
| GET/POST | `/api/entities/gate-passes` | Gate pass list/create |

Existing `/api/customers/search`, `/api/cars/search`, `/api/cars/customer/{id}` remain.

## Migration

```bash
cd api
python migrate_shared_foundation.py
```

Safe to re-run. Additive only; backfills codes from existing ids.

## Frontend

- `web/src/components/EntitySelect.tsx` — searchable combobox
- `web/src/api/entities.ts` — client helpers
- Wired into `RepairOrderCreatePage`, `InvoiceDocumentForm` (customer → contact + vehicles; inventory search on lines)
