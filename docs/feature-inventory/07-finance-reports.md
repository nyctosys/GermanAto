## daily-expenses.html — Daily Expenses & Cash Management (petty-cash till)

**1. Purpose / URL / access**
- URL `/daily-expenses.html`. Flask serves it with `Cache-Control: no-cache, no-store` (app.py:269-275). `<title>` is "Daily Expenses & Cash Management - GermanATO". The H1 is "Daily Expenses & Cash".
- Header copy: "The petty-cash till. Parts live in the vendor ledger and invoice payments live on the invoice, so neither is counted twice — everything else the day costs is here." (html:24-28)
- Page guard: `auth.requirePageAccess("daily-expenses")` (dailyExpenses.js:826). Admin always passes. Everyone else needs the `daily-expenses` permission. By default (jwt_auth.py:24-35) admin and accountant have it, inventory_manager does not, but admin.html can grant it to inventory_manager. If permissions are not cached yet, the page loads and the check runs after `auth.ready`.
- Server rules:
  - GET `/api/expenses` and GET `/api/cash-received` are only `login_required`, with no permission check.
  - POST on both needs `role_required(['admin','accountant'])`. Once RolePermission rows exist, the path permission `daily-expenses` replaces the role check (jwt_auth.py:88-110, PATH_PERMISSIONS `/api/expenses`, `/api/cash-received` → `daily-expenses`).
  - PUT and DELETE use `can_edit_expense` / `can_edit_cash_received`. These check only for a valid active user plus the 1-day rule, with no role or permission check. So an inventory_manager can edit or delete a record under 24h old through the API.
- Entry points:
  - finance-management.html links `daily-expenses.html?from=finance-management`.
  - financeManagement.js:8 uses `?from=finance`, which is not recognised and falls back to the default.
  - app-shell nav "Daily expenses".
  - app-shell quick action "Record daily expense" → `/daily-expenses.html?new=1`. **`new=1` is never read: dead param.**
  - dashboard.js "Expenses today" card.

**2. Layout (top to bottom)**
1. Sticky header: logo, title and subtitle, **Back** button (`#back-btn`).
2. Card "Add New Expense" (`#expense-form`).
3. Card "Add Cash Received" (`#cash-received-form`).
4. Search/filter bar.
5. Summary row with 3 cards: "Today's Expenses" (`#today-amount`), "Today's Cash Received" (`#today-cash-amount`), "Balance (Cash - Expenses)" (`#today-balance-amount`).
6. Empty placeholder comment "Monthly Ledger Section" (html:349; the ledger moved to its own page).
7. Table "Expenses List".
8. Table "Cash Received List".
9. Footer "© 2025 GermanATO".
10. Two modals: Edit Expense and Edit Cash Received.

Scripts loaded: `libs/xlsx.full.min.js` (**loaded but never used on this page**), auth_jwt, app-shell, api-helper, dailyExpenses.js.

**3. Lists / tables**
- **Expenses List** (`#expenses-table`)
  - Columns: Date (`formatDate` → en-US "Oct 28, 2026"), Category (`.category-badge`), Description, Amount ("PKR " + `toFixed(2)`, bold, no thousands separator), Notes ("-" if empty), Actions (Edit, Delete).
  - Sort: server `ORDER BY date DESC`. Ties have no defined order. No client sorting, no pagination, no totals row.
  - Empty state: one row, colspan 6, "No expenses found".
- **Cash Received List** (`#cash-received-table`)
  - Columns: Date, Description, Amount, Payment Method (`.payment-method-badge`), Notes, Actions.
  - Empty state: "No cash received records found". Same sort.
- **Filters** (shared bar). Every change triggers `performSearch()`, which reloads both lists.
  - "Search by Description" (`#search-keyword`, fires on `input` with no debounce). Sent as `keyword`. The server matches description OR notes with ILIKE.
  - "Filter by Category" (`#search-category`): All Categories plus the 6 till categories. Sent as `category`.
  - "From Date" / "To Date" (`#search-from-date`, `#search-to-date`). Both default to today on load (js:38-45). Sent as `start_date` / `end_date`. If an input is blank, the JS substitutes today (js:105-110).
  - Every request appends `scope=till` (js:118, 209, 528, 610).
  - **Keyword and category are applied to the expenses list only.** `loadCashReceived()` sends only dates and scope (js:514-529).
  - "Clear" button (`clearSearch`, js:379-385): blanks keyword, category and both dates, then calls `loadExpenses()` only. The blank dates mean "today" in the request, and **the cash list is not reloaded**.
- **Server till scope** (petty_cash.py):
  - Expenses are restricted to the allowlist `TILL_CATEGORIES` = Fuel, Maintenance, Utilities, Office Supplies, Transportation, Other.
  - Cash received is restricted to `invoice_id IS NULL`.
  - So Parts, Labor, the major-expense categories and any other category are hidden here, as are receipts that settle invoices.
  - **Docstring contradiction:** petty_cash.py:13-16 says "Payroll is NOT excluded… Labor entries", but `TILL_CATEGORIES` does exclude Labor, and lines 31-33 say Labor is excluded.

**4. Forms**
- **Add New Expense** (`#expense-form`)
  - Date: `name=date`, type=date, required, defaults to today. Today is computed as `new Date().toISOString()` (a UTC date; see quirks).
  - Category: `name=category`, select, required. Options are "Select Category" (empty) plus Fuel, Maintenance, Utilities, Office Supplies, Transportation, Other. The list is hardcoded in the HTML and must match `TILL_CATEGORIES`.
  - Description: text, required, placeholder "Enter expense description".
  - Amount (PKR): number, step 0.01, min 0, required, placeholder 0.00.
  - Notes (Optional): textarea.
  - Buttons: "Add Expense" (submit) and "Clear Form" (resets the form, sets date back to today).
  - Endpoint: POST `/api/expenses` with `{date, category, description, amount: parseFloat, notes: notes||""}`.
  - Server validation (expense_routes.py:141-198):
    - date, category, description and amount are required and must be truthy. **An amount of 0 is rejected as "amount is required".**
    - Date format must be YYYY-MM-DD.
    - amount < 0 → "Amount must be positive".
    - There is no server whitelist of categories.
    - The audit log records CREATE.
    - Returns 201 with the record.
  - UI result: success shows the toast "Expense added successfully", clears the form and reloads expenses. Any failure shows the toast "Error adding expense".
- **Add Cash Received** (`#cash-received-form`)
  - Date: required, defaults to today.
  - Amount (PKR): number, step 0.01, min 0, required.
  - Payment Method: `name=payment_method`, required. Options "Select Payment Method" plus Cash, Bank Transfer, Card Payment, Cheque, Mobile Payment, Other.
  - Description: text, required, placeholder "Enter description of cash received".
  - Notes (Optional): a text **input**, not a textarea.
  - Buttons: "Add Cash Received" and "Clear Form".
  - Endpoint: POST `/api/cash-received` with `{date, description, amount, payment_method, notes}`. **No `invoice_id` is sent, deliberately** (js:654-656).
  - Server validation (cash_received_routes.py:201-275):
    - Required: date, description, amount, payment_method. 0 is rejected.
    - amount < 0 is rejected.
    - The server would accept `invoice_id` and apply the receipt to the invoice: it checks overpayment against the amount remaining, updates `paid_amount`, `balance`, `status` and `payments_history` with `source:'cash_received'`. Error "This receipt of X PKR is more than the Y PKR still owed on invoice #N.", or "Payments can only be linked to an invoice, not a quote." This page never uses it.
  - UI result: success shows "Cash received added successfully", clears the cash form and reloads the cash list only.
  - Dead code: comment stubs for a "settles invoice" picker and an amount-mismatch warning, with no functions (js:506-512).
- **Edit Expense modal** (`#edit-modal`)
  - Same fields as Add, with `edit-` prefixed ids and a hidden `id`. Category has the same 6 options.
  - Opening: `editExpense(id)` calls GET `/api/expenses/{id}`, re-checks the lock (below) and fills the form.
  - Save: "Update Expense" → PUT `/api/expenses/{id}` with the same payload. Toasts "Expense updated successfully" / "Error updating expense".
  - Close: Cancel button, ×, or clicking the backdrop. Each one resets the form.
- **Edit Cash Received modal** (`#edit-cash-modal`)
  - Same pattern. GET `/api/cash-received/{id}`, then PUT `/api/cash-received/{id}` with `{date, description, amount, payment_method, notes}`.
  - Toasts "Cash received updated successfully" / "Error updating cash received".
  - Closing via × fires twice: an inline `onclick` plus an added listener. Harmless.
- **Delete**
  - Expense: `confirm("Are you sure you want to delete this expense?")` → DELETE `/api/expenses/{id}` → toast "Expense deleted successfully" / "Error deleting expense".
  - Cash: `confirm("Are you sure you want to delete this cash received record?")` → DELETE `/api/cash-received/{id}` → "Cash received record deleted successfully" / "Error deleting cash received record".
  - **The Delete button is never disabled in the UI.**
- **Edit lock: client side** (js:4-31, 476-503)
  - Admin: never locked.
  - Accountant: locked when `now - new Date(created_at) > 24h`.
  - Any other role: always locked.
  - If localStorage `user` is missing: not locked.
  - A locked button gets class `disabled`, the `disabled` attribute and the text "Edit (Locked)".
  - If editing is attempted anyway: `alert("You cannot edit expenses older than 1 day. Please contact an administrator.")`, with a matching message for cash.
- **Edit lock: server side**
  - Non-admins get 403 "Cannot edit expenses older than 1 day" / "Cannot edit cash received records older than 1 day" when `created_at < utcnow - 1 day`. This applies to both PUT **and DELETE**.
  - Server role rules differ from the client: non-admin, non-accountant roles are allowed by the server within 24h.
- **Period lock** (period_lock.py). It applies to POST, PUT and DELETE on both resources.
  - A month closes automatically once it has ended. The current month and future months are open.
  - A `FinancialPeriod` row overrides the default either way.
  - Admins bypass the lock entirely.
  - Create: blocked if the body date falls in a closed month.
  - Edit (`guard_both`): blocked if either the stored date or the new date falls in a closed month.
  - Delete: blocked if the stored date falls in a closed month.
  - Response: 403 `{error: "<YYYY-MM> is closed. Records from a finished month cannot be changed - ask an admin if this needs a correction.", period, closed: true}`.
  - **The page shows only its generic toast** ("Error adding expense" etc.). The real message reaches the user only through APIHelper's global banner, which shows "Could not load this data — /api/expenses: <message>" (api-helper.js:186-214), even for saves.
  - There is no UI for closed months on this page.

**5. Balance cards (client-side)**
- `__todayExpensesTotal` = Σ `parseFloat(amount)` of the expenses returned, re-filtered on the client to `from ≤ date ≤ to` (js:224-232). The data is already in till scope and already filtered by category and keyword on the server.
- `__todayCashTotal` = Σ amount of the cash records returned, in till scope and range, ignoring keyword and category.
- Balance = cash − expenses, shown with `toFixed(2)` (js:188-193).
- The labels say "Today's", but the figures cover **whatever date range is selected**.
- There is no opening balance or carry-forward: the balance covers only the range.
- Excluded from the balance: invoice settlements, Parts, Labor/payroll, major categories, and salary advances (those live in HR).
- **Inconsistency:** with a category or keyword set, the balance becomes cash for the whole range minus the filtered expenses.
- `updateSummary()` and `updateCashSummary()` run once with no arguments at init. Each issues its own extra GET (duplicates of the list calls).

**6–8.** No ledger, chart, Excel export or print on this page. There are no print CSS rules in dailyExpenses.css.

**9. Calculations:** covered in item 5. Display format is "PKR " + `toFixed(2)`.

**10.** No keyboard shortcuts, no autofocus, no polling.

**11. Persisted state and navigation**
- Reads localStorage `user` (`role`).
- Writes `lastPage = "daily-expenses"`.
- Writes `originalFrom = ?from` when that param is present.
- Back button target: `?from` or localStorage `lastPage`, then mapped `home` → home.html, `admin` → admin.html, everything else → finance-management.html.

**12. Quirks / bugs**
- "Today" is the UTC date (`toISOString`). In Pakistan (UTC+5), between 00:00 and 05:00 local time the defaults and fallbacks point at yesterday.
- `created_at` is serialised as a naive UTC ISO string with no "Z", and the client parses it as local time. In UTC+5 the client therefore locks the Edit button about 5 hours before the server would.
- `clearSearch` leaves the cash table stale.
- Description and notes are injected through `innerHTML` without escaping (XSS).
- xlsx is loaded but never used.
- `?new=1` is ignored.
- The two summary endpoints are not used by this page. GET `/api/expenses/summary` and `/api/cash-received/summary` both exist and both support `scope=till`, but nothing in frontend/ or static/js calls them.
- Server gap that matters for the rewrite: editing or deleting a cash_received that is linked to an invoice does **not** reverse the invoice's `paid_amount`. This page cannot reach such rows, but the API allows it.

---

## major-expenses.html — Major Expenses

**1. Purpose / URL / access**
- URL `/major-expenses.html` (served with no-cache headers, app.py:277-283). Header: "Major Expenses — Track and manage significant business expenses".
- Page guard: `auth.requirePageAccess("major-expenses")`. By default only admin has it; admin.html can grant it to accountant and inventory_manager.
- **The API uses a different permission.** POST `/api/expenses` is checked against the path permission `daily-expenses`. jwt_auth's PATH_PERMISSIONS has `/api/expenses/major` → `major-expenses`, but **no such route exists (dead mapping)**. A user who has only `major-expenses` can open the page but gets 403 on Add once RolePermission is configured.
- Entry points: finance-management.html (`?from=finance-management`) and the app-shell nav.

**2. Layout**
1. Header with Back. The link is hard-coded to `finance-management.html`, and the JS also sets it to finance-management whatever the input (js:445-459).
2. Card "Add New Major Expense".
3. Search bar.
4. A single summary card, "Total Major Expenses" (`#total-amount`).
5. Table "Major Expenses List".
6. Edit modal "Edit Major Expense".

The same dailyExpenses.css is used. Paths are `../static/...`.

**3. List**
- Columns: Date, Category badge, Description, Amount (PKR, `toFixed(2)`), Notes, Actions (Edit / Delete). Identical to the daily page.
- Empty state: "No expenses found". No pagination, no totals row. Order is server date DESC.
- Filters:
  - "Search by Description": keyword sent to the server, which matches description OR notes.
  - From / To dates, defaulting to today.
  - "Clear": resets keyword and **sets both dates back to today**. The daily page blanks them instead.
  - There is no category filter control.
- **Fetch:** GET `/api/expenses?start_date&end_date[&keyword]`, with no `scope` and no `category`. The result is then **filtered on the client** to the six major categories (js:107-114).

**4. Forms**
- **Add**
  - Date: required, defaults to today.
  - Amount (PKR): step 0.01, min 0, required.
  - Description: required.
  - Category: required, defaults to "Major Expenses". Options: Major Expenses, Capital Expenditure, Equipment Purchase, Infrastructure, Major Repairs, Other Major. No empty option.
  - Notes: textarea.
  - POST `/api/expenses` with the same payload and validation as the daily page.
  - "Clear Form" resets the form, sets date to today and category back to "Major Expenses" (`EXPENSE_CATEGORY_FILTER`).
- **Edit modal:** the same six categories. GET then PUT `/api/expenses/{id}`, with the same 1-day lock, period lock and toasts as the daily page.
- **Delete:** confirm, then DELETE `/api/expenses/{id}`.
- **"Major" versus "daily" on the server:** there is no separate model or flag. A major expense is an `Expense` row whose category is one of the six major categories. None of these are in `TILL_CATEGORIES`, so they never appear on the Daily page. The Monthly Ledger and Reports both count them in full.

**5. Summary card:** "Total Major Expenses" = Σ amount of the client-filtered major rows within the date range (default today), formatted "PKR " + `toFixed(2)`.

**10–11.**
- No keyboard shortcuts.
- Writes `lastPage = "major-expenses"`. Reads `user`.

**12. Quirks**
- The client-side category filter means every expense in the range is downloaded on each keystroke.
- The summary card is labelled "Total" but covers the selected range only (default today).
- Same UTC "today" and `created_at` timezone issues as the daily page.
- No HTML escaping in the table.
- There is also an unused GET for the summary at init (`updateSummary()` with no arguments issues a duplicate fetch).

---

## monthly-ledger.html — Monthly Financial Ledger

**1. Purpose / URL / access**
- URL `/monthly-ledger.html` (app.py:137-139, no no-cache headers). Header: "Monthly Financial Ledger — Opening and closing balances, day by day".
- It shows the full picture: all expenses (parts, labor, major, till) and all cash received, including invoice settlements. It never sends `scope=till` (js:1-10).
- **There is no page guard** (`requirePageAccess` is never called). The app-shell nav item is gated by `daily-expenses`.
- The API `/api/expenses/monthly-ledger` is `login_required` only, so any authenticated user (including inventory_manager) can read it.
- **The Back button (`href="#"`) is never wired up and goes nowhere.**
- Loads xlsx, auth_jwt, app-shell, api-helper and monthlyLedger.js. `PerformanceUtils` is not loaded, so the loading spinner calls are no-ops.

**2. Layout**
1. **Period picker card**
   - Preset chips: "This month", "Last month", "Last 3 months", "This year".
   - Month stepper: ‹ `#month-prev`, `<input type=month id=ledger-month-select>`, › `#month-next`.
   - "or" separator.
   - From (`#ledger-start-date`) and To (`#ledger-end-date`) date inputs.
   - "Apply range" (`#btn-apply-range`) and "Export Excel" (`#btn-export-ledger`).
   - Scope line `#ledger-scope`, initially "Loading…".
2. **Totals strip**: Opening balance, Money in (green), Money out (red), Net change, Closing balance (maroon).
3. Two breakdown cards: "Money out, by category" and "Money in, by method".
4. **"Every transaction"** table, with tools: search box ("Search description, category or notes"), type select ("In and out" / "Money in only" / "Money out only"), bucket select ("All categories" plus the buckets found).
5. **"Balances by day"** table, with the checkbox "Hide days with no activity" (checked by default).

**6. Month picker and period behaviour**
- On load: month input = current UTC month, then `loadMonth`, i.e. GET `?month=YYYY-MM`. No chip is shown as active at first.
- Changing the month input loads that month and clears the From/To inputs.
- ‹ / › step one month (`stepMonth(±1)`).
- Presets (clicking one marks it with `.is-on` and clears the others):
  - "This month" and "Last month" load by `month`, which always means the whole calendar month, future days included.
  - "Last 3 months" = the 1st of the month two months back → today, loaded by range.
  - "This year" = Jan 1 → today.
- "Apply range" needs both dates; otherwise `alert("Choose both a from and a to date.")`. If end is before start: `alert("The end date is before the start date.")`.
- Chip highlighting is not cleared when the user steps months, picks a month or applies a range.
- **Server** (expense_routes.py:356-514):
  - An explicit start/end wins over `month`.
  - Errors (400): "Invalid date format. Use YYYY-MM-DD", "end_date is before start_date", "Invalid month format. Use YYYY-MM", "Range is too long. Choose 400 days or fewer." (limit is span > 400 days).
  - With no params the server defaults to the current UTC month.

**Opening balance (exact):** `initial_balance = Σ CashReceived.amount where date < start − Σ Expense.amount where date < start`.
- This runs over all history and all categories, invoice settlements included.
- There is no opening float or capital entry.
- Vendor ledger payments, salary advances and anything else not posted as an Expense are not included.

**Totals:**
- `total_in` = Σ cash in range. `total_out` = Σ expenses in range.
- `net_change = total_in − total_out`, displayed with a "+" prefix when ≥ 0.
- `closing = initial + in − out`. All values rounded to 2 dp.

**Scope line:** "`{start} to {end} · N day(s) · M transaction(s)`". When settlements exist it appends " · includes K invoice settlement(s) worth PKR X". Settlements are cash rows with an `invoice_id`.

**Breakdowns:**
- Server-side, grouped by bucket and sorted by total descending.
- Out bucket = `category` or "Uncategorised". In bucket = `payment_method` or "Unspecified".
- Each row shows: bucket name, PKR total, then "pct% · count", where pct = bucket total / total_out (or total_in) × 100, to 1 dp. Bar width = `max(pct, 0.6)%`.
- Empty state: "Nothing in this period."

**"Every transaction" table**
- Columns:
  - Date.
  - Type: pill "In" / "Out".
  - Description, plus the pill "Invoice #id" when the row is linked to an invoice.
  - Category / method (bucket).
  - Notes ("—" if empty).
  - Amount: "+" or "−" followed by PKR, green or red.
  - Balance: running balance, PKR.
- Server sort key is `(date, in before out, id string)`. The id is a string such as "in-12", so **ids sort lexicographically**: "in-10" comes before "in-9".
- Each row's running balance = initial + cumulative signed amount in that order.
- Filters are client-side only, with no refetch. Search is a case-insensitive substring match on description, bucket or notes. The type and bucket selects listen to the `input` event.
- The bucket select is rebuilt on every load from the distinct buckets, sorted, and keeps the previous selection if it still exists.
- **Filtering does not recompute the Balance column**: rows keep their full-ledger balances.
- Footer count:
  - All rows shown: "N transaction(s)".
  - Filtered: "x of N transactions · net ±PKR sum", where sum = Σ(in) − Σ(out) of the visible rows.
- Empty state: "No transactions match this filter."

**"Balances by day" table**
- One row for every day in the range. Columns: Date, Opening, In, Out, Entries, Closing (bold).
- In, Out and Entries show "—" when zero.
- Day opening = the previous day's closing (the first day starts from `initial_balance`). Closing = opening + inflow − outflow.
- When "Hide days with no activity" is checked, rows with `entry_count == 0` are dropped. If shown, they get the `quiet-day` class (opacity 0.55).
- Empty state: "No activity in this period."

**8. Excel export** (`exportLedger`, js:189-239; SheetJS from local `libs/xlsx.full.min.js`)
- Does nothing if no data has loaded.
- Filename: `ledger_{start_date}_to_{end_date}.xlsx`.
- Sheet "Transactions": Date, Type ("In"/"Out"), Description, "Category / method", Invoice (id or ""), Notes, "Amount (PKR)" (negative for out), "Balance (PKR)".
- Sheet "Balances by day": Date, "Opening (PKR)", "In (PKR)", "Out (PKR)", Entries, "Closing (PKR)". Includes every day, quiet ones too.
- Sheet "Breakdown": Direction ("Out" rows first, then "In"), Bucket, "Total (PKR)", Entries.
- **The export always contains all data, ignoring the on-screen filters.**

**9. Formatting:** `PKR(n)` = "PKR " + `toLocaleString("en-PK", 2 dp)`. Values are escaped with `esc()`.

**10.** No keyboard shortcuts, no polling.

**11.** No localStorage writes and no URL query params.

**12. Quirks**
- Load errors render APIHelper's `renderError` (with "Try again") inside the details tbody only. The stats, breakdowns and daily table keep stale data.
- **`logger` is never defined or imported in expense_routes.py**, but line 513 calls `logger.error`. Any exception in the ledger therefore raises NameError inside the except block, and the client gets a raw 500 instead of the JSON error.
- "This month" includes future days with zero activity.

---

## reports.html — Reports & Analytics (Business Intelligence Dashboard)

**1. Purpose / URL / access**
- URL `/reports.html`. Default landing page for admins (`auth.redirectToHome`, auth_jwt.js:279-281). Also linked from dashboard.js ("Sales this month", "Profit this month") and the app-shell nav.
- Page guard: `requirePageAccess("reports")`. It is called twice, once in reports.js:11 and once in the inline script at html:527. By default only admin has `reports`.
- API: GET `/api/reports` requires `role_required(['admin','accountant'])`. When RolePermission rows exist, the `reports` permission is what counts.
- Chart.js 4.4.0 loads from the CDN `https://unpkg.com/chart.js@4.4.0/dist/chart.umd.js`. A local `static/js/libs/chart.js` exists but is not used. notification-utils.js is also loaded.
- An inline head script suppresses `console.error` messages containing "source map" and rejects `fetch` for URLs ending in `.map` (html:12-39).

**2. Layout**
1. **Header**: "Refresh" button (`onclick=loadReports()`) and Back. Back always goes to `home.html`; both branches of reports.js:681-696 lead there.
2. **Quick filters**: pills Today, Last 7 Days, **Last 30 Days** (active by default), This Year, Custom Range.
   - Custom shows the hidden `#custom-date-range` with From (`#start-date`) and To (`#end-date`).
   - A hidden `<select id=period-select>` (day / week / month [selected] / year) is kept for compatibility.
3. **Loading state** ("Loading reports..." spinner).
4. **Error state**: "Failed to load reports" plus a Retry button. The JS sets the message "Failed to load reports. Please try again.", or "Chart library not loaded. Please refresh the page." if Chart.js is missing.
5. **Dashboard content**:
   - "Key Performance Indicators": 4 cards.
   - "Trend Analysis": 3 charts.
   - "Alerts & Insights": 3 alert cards.
   - "Detailed Reports": 2 tables.

**Date controls**
- Presets (`setQuickFilter`; dates via `toISOString`, so UTC):
  - today: start = end = today; period=day.
  - 7days: start = today − 7, so **8 days inclusive**; period=week.
  - 30days: start = today − 30, so **31 days inclusive**; period=month.
  - year: Jan 1 → today; period=year.
  - custom: only reveals the inputs, with no load.
- Each request is GET `/api/reports?period=…&start_date=…&end_date=…`.
- Server: if both dates are non-empty and parse, they win. Otherwise the period applies:
  - day = today.
  - week = today − 6 → today. This does not match the client's 7days.
  - month = **1st of the month → today**. This does not match "Last 30 Days".
  - year = Jan 1 → today.
  - Invalid → month.
  - The bounds are datetimes from 00:00:00 to 23:59:59.999. Response also includes `period` and `date_range{start,end}`; the UI does not show them.

**KPI cards** (`formatCurrency` = Intl en-PK, currency PKR, 0 decimals)
- **Sales** (`#sales-total`):
  - Formula: `SUM(invoice.net_total)` where `type_of='invoice'` and `created_at` falls in the range.
  - Excludes tax and ignores discount. Uses created_at, not an invoice date.
  - Subtitle = the preset's label ("Last 30 Days", etc.).
- **Expenses** (`#expenses-total`): `SUM(expense.amount)` where `expense.date` falls in the range. **All categories** count: till, Parts, Labor, major.
- **Profit** (`#profit-total`): sales.total − expenses.total.
- **Receivables** (`#receivables-total`, subtitle "Outstanding"): **all-time, not date-filtered.** Formula: Σ(due − paid) over invoices (`type_of='invoice'`) where due > paid.
  - due = net_total + (tax_amount if include_tax) − discount.
  - paid = advance + paid_amount.
  - This matches invoice_math.py.

**Charts** (Chart.js)
- **Sales Trend**
  - Type: line.
  - Labels: `sales.daily[].date`, formatted en-PK "Oct 28". Data: daily totals.
  - Style: border #8b1538, gradient fill rgba(139,21,56,0.3→0.02), width 3, tension 0.4, points 5/7 px, point fill #8b1538 with white border.
  - Only days that have invoices appear; there are no zero-fill days.
- **Profit Trend**
  - Type: line. Colour #a91d45, gradient rgba(169,29,69,…).
  - Data: `profit.daily`, i.e. sales day minus the expenses of that same day, **computed only for days that have sales**. Expense-only days are missing, so the chart does not add up to the Profit KPI.
- **Growth Metrics**
  - Type: bar. Labels Customers, Invoices, Cars. Bar fills rgba(139,21,56,.85) / rgba(169,29,69,.85) / rgba(109,16,41,.85), borders #8b1538 / #a91d45 / #6d1029, radius 8.
  - Data: **counts of records created** in the range from the customer, invoice and car tables. Invoices **include quotes**, since there is no `type_of` filter. These are counts, not growth rates.
- **Shared options**: no legend, no title, maroon tooltip (rgba(139,21,56,0.9)), `index` interaction mode. Line-chart y ticks are formatted as currency; bar-chart y ticks are raw numbers. `maintainAspectRatio: false`. CSS caps the canvas at max-height 260px (220px under 768px).
- Server also returns monthly/yearly rollups for sales, expenses, profit and growth. **The UI does not use them.**

**Alerts**
- **Low Stock Alert**
  - Count badge = the full list length.
  - Each row: `item_name` and "quantity / reorder_level".
  - Source: inventory rows where `quantity <= reorder_level`, ordered by quantity/reorder_level ascending. No limit, and the UI shows them all.
  - The server's `urgency` (critical if qty ≤ 50% of reorder level) and `category` fields are unused.
  - Items whose reorder_level is 0 and qty is 0 are included.
  - Empty state: "No low stock items".
- **Open Repair Orders**
  - The server returns at most 20 (`current_status NOT IN ('complete','completed')`, newest first). The UI shows the first 5 as "#id - customer_name" with the status.
  - **The count badge equals the list length, so it never shows more than 20.**
  - Empty state: "No open repair orders".
- **Pending Quotes**
  - Source: invoices with `type_of='quote'` and `status='pending'`, limit 20.
  - The UI shows 5 as "#id - customer_name" with `formatCurrency(total_amount = net_total)`. The count is capped at 20.
  - `quote_number` "Q-0001" is returned but unused.
  - Empty state: "No pending quotes".

**Tables**
- **Vendors with Outstanding Balance**: columns Vendor Name and Balance.
  - Source: `SUM(vendor_ledger.balance)` per vendor where > 0, top 10 descending.
  - **Bug:** `vendor_ledger.balance` is a *running* balance stored on every entry (vendor_routes.py:306 `new_balance = last_balance + debit - credit`). Summing it inflates the figure badly. The correct value is the last entry's balance, or Σdebit − Σcredit.
  - Empty state: "No vendors with outstanding balance".
- **Completed Repair Orders (Today)**: columns Order #, Customer, **Vehicle**, Status.
  - Source: `current_status IN ('complete','completed')` and `DATE(updated_at)` = server today.
  - **The "Vehicle" column actually shows `customer_phone`** ("N/A" if empty).
  - Status shows as a green "completed" badge.
  - Empty state: "No repair orders completed today".
  - Any later edit moves `updated_at`, so the "completed today" date shifts with it.

**8. Print / export**
- `@media print` (reports.css:1026-1042) hides the header and quick filters, zeroes the main padding, and sets `break-inside: avoid` on cards, charts and tables.
- `exportToPDF` and `exportToExcel` just call `showInfo("… coming soon!")` and nothing invokes them (dead code).

**10.**
- No auto-refresh. A manual Refresh button exists.
- No keyboard shortcuts.
- Responsive: KPI, chart and alert grids go to 2 columns under 1200px and 1 column under 768px; under 480px KPI cards stack vertically.

**11.** No localStorage writes and no URL params, except that the Back handler reads `?from` and ignores it.

**12. Quirks / bugs**
- **Double initial load with a race.** reports.js's DOMContentLoaded handler runs first and calls `loadReports()` while the date inputs are still empty. The server treats that as period=month, i.e. month-to-date. The inline handler then sets the 30-day dates and calls `loadReports()` again. Whichever response arrives last wins, so the "Last 30 Days" label can sit on month-to-date figures.
- Date inputs have both an inline `onchange="loadReports()"` and an added listener. Each change triggers 2 loads; same-URL requests may be deduped by APIHelper's in-flight map.
- If a custom date is cleared, the server falls back to whatever period the last preset set.
- Dead code: `getPeriodText`, `refreshData`, `handleLogout`, the export stubs, and the `period` returned in the response.
- No escaping of names in `innerHTML`.
- Dates come from UTC `toISOString`, but the server uses its local `date.today()`.
- The Profit figure mixes accrual sales (invoice net_total) with cash-basis expenses, and counts parts purchases recorded as expenses.

---

## Backend rules referenced (for parity)
- **`/api/financial-periods`**
  - GET (login): returns the last 13 months as `{year, month, label, is_open, is_current, overridden, changed_by, reason}`, plus `can_change` (true for admin).
  - POST (admin only): `{year, month, is_open, reason}`. Reopening without a reason → "Give a reason for reopening a closed month." Also "month must be between 1 and 12" and "year and month are required" / "is_open is required". Writes REOPEN / CLOSE audit entries.
  - **None of the four pages calls it.** A grep of frontend/ and static/js found no caller at all.
- Every write is audit-logged through `log_action` with CREATE / UPDATE / DELETE.
- `invoice_math.py`: `amount_due = net_total + tax (if include_tax) − discount`; `paid = advance + paid_amount`; `remaining = round(due − paid, 2)`; status is quote → pending, paid ≤ 0 → unpaid, paid ≥ due or balance ≤ 0 → paid, otherwise partially_paid. Used by cash-received invoice linking and by receivables.

### Endpoints used
| METHOD | path | page/action |
|---|---|---|
| GET | /api/expenses?start_date&end_date&scope=till[&category][&keyword] | daily-expenses: list and summary (summary called twice at init) |
| GET | /api/expenses?start_date&end_date[&keyword] | major-expenses: list and summary (filtered client-side to major categories) |
| GET | /api/expenses/{id} | daily and major: open the edit modal |
| POST | /api/expenses | daily and major: add expense |
| PUT | /api/expenses/{id} | daily and major: update expense |
| DELETE | /api/expenses/{id} | daily and major: delete expense |
| GET | /api/cash-received?start_date&end_date&scope=till | daily-expenses: cash list and summary |
| GET | /api/cash-received/{id} | daily-expenses: open the cash edit modal |
| POST | /api/cash-received | daily-expenses: add cash (no invoice_id) |
| PUT | /api/cash-received/{id} | daily-expenses: update cash |
| DELETE | /api/cash-received/{id} | daily-expenses: delete cash |
| GET | /api/expenses/monthly-ledger?month=YYYY-MM or ?start_date&end_date | monthly-ledger: all data |
| GET | /api/reports?period&start_date&end_date | reports: whole dashboard |
| GET | /api/expenses/summary, /api/cash-received/summary | exist (support scope=till), **not called by any page** |
| GET/POST | /api/financial-periods | exist, **not called by any page** |
| (mapping) | /api/expenses/major | listed in jwt_auth PATH_PERMISSIONS, **no route exists** |
| GET | https://unpkg.com/chart.js@4.4.0/dist/chart.umd.js | reports: CDN script |

### Files read
- frontend/daily-expenses.html — 627 lines (full)
- frontend/major-expenses.html — 338 lines (full)
- frontend/monthly-ledger.html — 177 lines (full)
- frontend/reports.html — 548 lines (full)
- static/js/dailyExpenses.js — 864 lines (full)
- static/js/majorExpenses.js — 464 lines (full)
- static/js/monthlyLedger.js — 316 lines (full)
- static/js/reports.js — 696 lines (full)
- static/css/dailyExpenses.css — 1114 lines (full)
- static/css/monthlyLedger.css — 210 lines (full)
- static/css/reports.css — 1042 lines (full)
- expense_routes.py — 514 lines (full)
- cash_received_routes.py — 432 lines (full)
- petty_cash.py — 59 lines (full)
- reports_routes.py — 671 lines (full)
- period_lock.py — 226 lines (full)
- invoice_math.py — 49 lines (full)
- Consulted in part:
  - static/js/api-helper.js: request, performRequest, responseError, renderError and showErrorState.
  - static/js/auth_jwt.js: SUB_PAGE_PERMISSIONS, canAccessPage, requirePageAccess, redirectToHome.
  - jwt_auth.py: ADMIN_PERMISSIONS, DEFAULT_ROLE_PERMISSIONS, PATH_PERMISSIONS, role_required, login_required.
  - app.py: page routes and blueprint prefixes.
  - models.py: Expense, CashReceived, FinancialPeriod, VendorLedger.
  - vendor_routes.py: around line 306, the running-balance calculation.
  - static/js/app-shell.js, dashboard.js, financeManagement.js, finance-management.html, admin.html: grep only, for links and permissions.
