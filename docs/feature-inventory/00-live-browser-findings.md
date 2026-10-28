# Live browser check (2026-10-28)

The Flask app ran on a fresh Postgres database. Demo data was seeded through the API (scratch script: 3 customers/cars, 6 items, 3 invoices, 2 quotes, 3 repair orders, 3 workers, expenses, cash, 2 vendors with ledger and purchase orders, 1 ZKTeco device). Every page was opened as admin at desktop width, and some at phone width. Each finding below was reproduced in the browser or against the running API, not only read in code.

## Page reachability
| Page | Result |
|---|---|
| login, home, reports, invoice-management, pending-quotes, repair-orders-management, inventory, inventory-history, vendors, /vendors/1, car, daily/major expenses, monthly-ledger, employees, attendance, salaries-management, /hr, /hr/1, device-management, finance-management, invoiceSystem, admin, whatsapp-notifications, settings, invoice, repair-order, invoice-template | Loads, with no console errors of its own |
| /hr.html | 404. The HR hub lives at `/hr` |
| /transaction-history.html | 404. The route exists but the file does not |
| low-stock-print.html | Loads but always shows "0 items / Excellent Inventory Management!", because nothing writes the `lowStockItems` sessionStorage key. The working low-stock view and export are inside inventory.html |

The sidebar has 20 entries: Dashboard, New invoice, New quote, New repair order, Invoices, Quotes, Repair orders, Inventory, Vendors, Cars & customers, Daily expenses, Major expenses, Monthly ledger, Reports, Employees, Attendance, Salaries, Users & roles, WhatsApp, Settings.

Pages that are not in the sidebar are reached from other screens: hubs (/hr, finance-management, invoiceSystem), inventory-history, device-management, worker and vendor detail, and the print templates.

Admin login lands on **reports.html**, not on home.

## Behaviour confirmed live
- **Reports, vendor balances:** each vendor has 50,000 debit and 20,000 credit, so 30,000 is owed. Reports shows **Rs 80,000**, because it sums the stored running balances.
- **Reports, "Completed Repair Orders (Today)":** the VEHICLE column shows the customer's phone number.
- **Reports:** every load requests `/api/reports` twice (once with empty dates, once with the range), so the two responses race.
- **Invoice form, live totals:** with 2×1000 parts, 500 labour, 17% tax (425) and a 1000 advance, the form shows **Balance 1500**. The server stores and prints **1925**. The on-screen balance ignores tax.
- **Invoice form, saving:** generating an invoice does **not** deduct stock (engine oil stayed at 12). Stock moves only through the separate "Check & Deduct Inventory" button.
- **Invoice form, item search:** the suggestion list showed only "Engine oil 5W-30 4L" for "oil", while `/api/inventory/search?q=oil` returns both that and "Oil filter". The code renders every result (02-invoice-quote-forms.md §row search), so the likely cause is the dropdown being clipped by its section or a debounce race. The cause has not been confirmed. Re-test this in the rewrite.
- **Invoice form, price autofill:** picking a part leaves Price blank, because the inventory API never returns `price` (confirmed by the code report).
- **Invoice form, required fields:** Vehicle is required; the form refuses to submit without a car picked.
- **Invoice template, right after create:** shows "Customer ID: N/A". The template renders from the submitted payload, which has no `customer_code`; the server stored CN002.
- **Invoice list:** the status `partially_paid` gets the grey fallback badge, because the UI expects `partially paid`. Lists render collapsed under an "Invoices (N)" header. The card actions are View, Edit, Update Balance, Payments and Delete.
- **Quotes, approve:** `PUT /api/invoice/4/status {"status":"approved"}` returns `{"message":"Status auto-calculated","status":"pending"}`. A quote can never become "approved", so the Approved tab only shows legacy rows.
- **Repair orders, delete:** the UI's `DELETE /api/repair-orders/<id>` returns **405**. The real route is `/api/repair-orders/<id>/delete`, so the Delete button never works.
- **Repair-order template, history:** the logs call uses `localStorage.token`, which does not exist, so the request returns **422** and the template says "No edit history logs found".
- **Repair orders, status:** the API accepted `in_progress`, which is not one of the five UI statuses. The server has no status whitelist.
- **Inventory history:** the "Inventory Item" search is ignored by the server (with or without a nonsense term, the total is the same: 3).
- **Car search:** results lack `vin`, `color` and `chasis_no`. Editing a car from a search result wipes those fields on save.
- **ZKTeco:** a POST to `/iclock/cdata?SN=NOT-REGISTERED&table=ATTLOG` was accepted and created an attendance row for E003. **Unregistered devices can inject attendance.** That attendance feeds payroll.
- **HR:** deleting a worker who has attendance returns **500** "Failed to delete worker".
- **WhatsApp:** 5 notifications are stored, but the stats cards show 0 sent, 0 delivered and 0 failed, because their status is none of the counted values. The message template contains the literal placeholder `+92-XXX-XXXXXXX`, which would be sent to customers.
- **Monthly ledger:** "Money in" shows only cash_received (1,500). The 15,200 in invoice advances does not appear, because advances are not cash_received rows.
- **Attendance:** the default filter is today only, so past records (and the 5 seeded days) are hidden until the dates are changed.
- **Layout:** at narrow pane widths every page switches to a mobile layout (hamburger menu, stacked cards). This needs to carry over.
