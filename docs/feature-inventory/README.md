# GermanATO feature inventory

This is the parity checklist for the Next.js + FastAPI rewrite: every page, action, field, calculation, export and backend rule the current Flask app has. It was built on 2026-10-28 from two sources:

1. **Code study.** Eight readers each covered one feature area and read every HTML, JS and CSS file in it in full, together with the Flask handlers those pages call. Each report ends with "Endpoints used" and "Files read" tables.
2. **Live run.** The app ran on a fresh Postgres database with seeded demo data, and every page was opened in a browser. Bugs were reproduced against the running app ([00-live-browser-findings.md](00-live-browser-findings.md)).

**Coverage check.** All 103 UI files (32 HTML pages, 41 JS files, 30 CSS files) and all 175 Flask routes were matched against the reports. The only items not described in a report are six page stylesheets (admin, dashboard, finance-management, home, settings and whatsapp-notifications CSS), which hold only responsive breakpoints (1024, 768, 640 and 480px) and reduced-motion rules, and two operational routes: `GET /api/health` and the favicon/apple-touch-icon stubs that return 204.

## Where each page is documented

| Page (URL) | Report |
|---|---|
| login.html (`/`), home.html (dashboard), admin.html (users, roles & permissions, app logs), settings.html (theme, departments, categories), whatsapp-notifications.html, hub pages invoiceSystem.html, finance-management.html and `/hr`; shared app-shell (sidebar, command palette, unsaved-changes guard), auth_jwt, api-helper, theme, notifications, phone formatter, performance-utils | [01-shell-auth-admin.md](01-shell-auth-admin.md) |
| invoice.html (new or edit invoice), quote.html, the customer/car picker shared with repair orders | [02-invoice-quote-forms.md](02-invoice-quote-forms.md) |
| invoice-management.html, pending-quotes.html, invoice-template.html (print/PDF), the per-document history modal | [03-invoice-lists-and-print.md](03-invoice-lists-and-print.md) |
| repair-order.html, repair-orders-management.html, repair-order-template.html | [04-repair-orders.md](04-repair-orders.md) |
| inventory.html, inventory-history.html, low-stock-print.html (orphaned) | [05-inventory.md](05-inventory.md) |
| car.html, `/vendors`, `/vendors/<id>` (ledger, purchase orders) | [06-customers-cars-vendors.md](06-customers-cars-vendors.md) |
| daily-expenses.html, major-expenses.html, monthly-ledger.html, reports.html | [07-finance-reports.md](07-finance-reports.md) |
| employees.html, attendance.html, salaries-management.html (slips, advances, payroll), `/hr/<id>`, device-management.html, the ZKTeco `/iclock` push protocol | [08-hr-payroll.md](08-hr-payroll.md) |

## Rules that cut across the whole app (decide these once in the rewrite)

- **Permissions.** There are three roles: admin, accountant and inventory_manager. Each permission string (home, invoice, inventory, car, reports, daily-expenses, major-expenses, vendors, hr, repair-order, settings, logs…) gates both a page and an API path prefix.
  - Until the `role_permissions` table has any row, the defaults in `jwt_auth.py` apply. After that, the table alone decides and the per-route role lists are ignored.
  - Admins bypass everything.
  - Several pages have no client-side guard (car, inventory-history, monthly-ledger, invoice lists, templates), and several GET APIs check only that the user is logged in.
  - The full matrix is in 01 §0.
- **Month-end lock** (`period_lock.py`). Past months close automatically; admins bypass the lock and can reopen a month with a reason.
  - It covers expenses, cash received and salary advances, and payroll through its pay date.
  - It does **not** cover invoices, vendor ledger entries, purchase orders or attendance.
  - No page calls `/api/financial-periods`, so there is no UI to see or reopen periods.
- **Edit locks.**
  - Expenses and cash received: non-admins can't edit after 24 hours.
  - Invoices: other roles can't edit after 1 day.
  - Completed repair orders: admin only.
- **Documents keep a historical snapshot.** Invoices and repair orders store customer and car text as it was on the day, plus `customer_id`/`car_id` links resolved by `document_links.apply_links`. Unknown cars with no owner are adopted by the customer named on the document.
- **Audit log.** Most writes call `log_action`. The per-document history modal reads it, with an Excel export.
- **Dates and timezones.**
  - The server stores naive UTC.
  - Many pages compute "today" with `toISOString()`, which gives the UTC date. In Pakistan (UTC+5), between midnight and 05:00 local time, "today" means yesterday.
  - The business day for inventory movements uses Asia/Karachi.
  - Pick one rule for the rewrite.
- **Money formatting is inconsistent.** Pages variously use `toFixed(2)` + " PKR", Intl en-PK currency with 0 or 2 decimals, and "PKR " + `toLocaleString`.
- **Exports.** Excel (SheetJS) exports exist for:
  - the inventory: full list, low stock, per-item ledger;
  - the monthly ledger;
  - a vendor's ledger and purchase orders;
  - each document's history.

  The invoice/quote PDF is built with html2canvas + jsPDF and shared through the system share sheet. Everything else is printed from the browser (salary slip, repair order, reports). Exact columns and file names are in each report.
- **Mobile.** Every page has a phone layout with a hamburger sidebar and stacked cards.

## Bugs confirmed in the current app (fix them, don't port them)

These are confirmed. "L" means reproduced live; "C" means confirmed in code.

| # | Area | Bug |
|---|---|---|
| 1 | Invoice form | The on-screen balance ignores tax; the server and print add it (L) |
| 2 | Invoice form | Price never autofills from inventory, because the API doesn't return `price` (C) |
| 3 | Invoice form | Saving does not move stock. "Check & Deduct Inventory" is a separate, repeatable click; it is refused for accountants and crashes on rows without a part number (L/C) |
| 4 | Invoice, quote and repair-order forms | Every save writes the form's customer and car text back to the master records. In edit mode that writes the document's old snapshot over current data (C) |
| 5 | Quotes | Approve never changes the status, so the "Approved" tab is effectively dead (L) |
| 6 | Quotes → invoice | Convert says it deducts inventory but doesn't, isn't audit-logged, and forces status to unpaid even when there is an advance (C) |
| 7 | Invoice list | The `partially_paid` status gets the grey fallback badge; `customer_code` is never in the search results (L/C) |
| 8 | Repair orders | Delete calls a route that doesn't exist (405) (L) |
| 9 | Repair orders | Status accepts any string (L). Stock deduction commits per part and isn't atomic. Bringing a quote in fails when a part isn't among the first 50 inventory items (C) |
| 10 | Repair-order template | The history log uses the wrong token key, so it always shows "no logs" (L) |
| 11 | Reports | Vendor balances sum running balances (80,000 shown vs 30,000 owed) (L). "Vehicle" shows the phone number (L). Duplicate loads race (L). Profit trend skips days with only expenses (C) |
| 12 | Vendors | Running balance breaks on back-dated or deleted entries; the ledger shows insert time instead of the transaction date; Edit from the detail page goes to an unhandled `?edit=` (C) |
| 13 | Cars | Search and cars-by-customer omit VIN, colour and chassis, so editing from search wipes them (L/C). Cars without an owner are invisible (C) |
| 14 | Inventory | 5-minute stale cache after edits; Retry button broken; reorder level 0 shows as 5; deleting an item wipes its transaction history; the history page ignores its item search (L/C) |
| 15 | HR | Deleting a worker with attendance returns 500 (L). Clearing a time on attendance edit doesn't clear it (C) |
| 16 | ZKTeco | Unregistered devices can push attendance, and that feeds payroll (L, security) |
| 17 | WhatsApp | Stats always show 0; the message template sends the literal `+92-XXX-XXXXXXX` (L) |
| 18 | Monthly ledger | `logger` is undefined in expense_routes, so errors become raw 500s. Invoice advances don't count as money in (L/C) |
| 19 | Many pages | Unescaped `innerHTML` with customer, vendor and item text (XSS) (C) |

## Dead or orphaned code (don't port)

| Item | Status |
|---|---|
| `login.js` | Dead code |
| `script.js` | Dead code |
| `editInvoiceUtils.js` | Dead code |
| `invoiceTemplateUtils.js` | Dead code |
| `repairOrderTemplateUtils.js` | Dead, but it holds traces of vehicle-condition, diagnosis and notes intake features. Ask the business whether those should come back |
| `low-stock-print.html` | Nothing feeds it data |
| `/transaction-history.html` | The route exists but the file doesn't |
| `/hr.html` | Never existed; the hub is `/hr` |
| local `libs/chart.js` | Unused; reports loads Chart.js from a CDN |
| `/api/inventory/stats`, `/api/attendance/summary`, `/api/salary/payroll`, `/api/expenses/summary`, `/api/cash-received/summary`, `/api/financial-periods`, part/labour status routes, `/api/workers/debug`, `/api/workers/test-auth` | Unused endpoints. Keep any that the new UI needs; the period and attendance summaries are useful |
| `?new=1` on daily-expenses, `?id=` on repair-orders-management, `?id=` on invoice-management | Query parameters that pages receive but ignore |
