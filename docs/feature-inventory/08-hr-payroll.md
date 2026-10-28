# HR area: feature inventory (employees, attendance, salaries/advances/payroll, worker detail, ZKTeco devices)

### Rules that apply to every page in this area
- **Page gate:** each page JS calls `auth.requirePageAccess("hr")`. Worker detail uses `"worker-detail"`, which maps to `hr` (`static/js/auth_jwt.js:6`). By default `hr` belongs to admin and accountant only. inventory_manager does not have it (`jwt_auth.py:24-35`). Admin always passes. While permissions are still loading on first sign-in, the page is allowed to start (`auth_jwt.js:224-226,251-254`). The HTML page routes have no server-side auth.
- **API role lists are only fallbacks:** `role_required` maps the path prefixes `/api/workers`, `/api/salary`, `/api/attendance` and `/api/zkteco` to the permission `hr` (`jwt_auth.py:51-55`).
  - If the `RolePermission` table has any rows, the decorator's role list is ignored. Any role holding `hr` can then call every HR endpoint, including the "admin-only" payroll run (`jwt_auth.py:97-105`).
  - Admins always pass.
  - Parity risk: a rewrite that hard-codes the role lists will behave differently.
- **Shared helpers:**
  - `APIHelper` throws on any non-2xx response, with `error.message` set to the server's `error`. It also shows a global sticky red error banner (`api-helper.js:480-498`).
  - Non-GET calls disable the button that was just clicked until the request finishes, and identical in-flight requests are de-duplicated (`api-helper.js:399-428`).
  - `showSuccess` and `showError` come from notification-utils.
- **Shared header:** logo, page title and subtitle, and a maroon "Back" button. On screens of 768px or less the Back label is hidden (hr.css). The footer reads "© 2025 GermanATO".
- **Not present anywhere in this area:** Excel or CSV export, autofocus, polling or auto-refresh, page-specific localStorage or sessionStorage keys.

---

## employees.html — Employees Management

**1. Purpose, URL, access**
- Worker CRUD list. URL `/employees.html` (`app.py:298`), linked from the HR hub card and the app-shell nav "Employees".
- Page gate is `hr`.
- API access:
  - GET `/api/workers`: admin, accountant, inventory_manager.
  - POST, PUT, DELETE: admin, accountant (`hr_routes.py:41,104,167,240`).

**2. Layout**
- Header: "Employees Management" / "Manage worker information and roles".
- Controls bar with a "+ Add Worker" button.
- Search bar and filters.
- Workers table.
- Add/Edit modal and Delete confirm modal.
- Back button: `setupBackButton` always resolves to `/hr`, because the pathname contains "employees". The `?from=hr` and `/home.html` fallback branches can never run here (`hr.js:38-51`).

**3. Table**
- Columns: Employee ID | Name (`first last`) | Position | Department | Phone | Status | Hire Date | Actions.
- **Status badge:** `status-badge status-{active|inactive|terminated}`, uppercase. Green for active, yellow for inactive, red for terminated (`hr.css:612-635`).
- **Hire Date format:** `toLocaleDateString("en-US",{year:"numeric",month:"short",day:"numeric"})`, e.g. "Jan 15, 2025". Shows "N/A" if empty and "Invalid Date" if unparseable (`hr.js:419-430`).
- **Actions:**
  - "View" is a link to `/hr/{id}`.
  - "Edit" opens the modal.
  - "Delete" opens the confirm modal.
- **Sorting:** server order only, `hire_date DESC` (`hr_routes.py:75`). No column sorting.
- **Pagination:** none.
- **States:**
  - Loading row: "Loading workers...".
  - Empty: `APIHelper.renderEmpty` with "No workers found".
  - Error: `APIHelper.renderError` with a Retry button.
- Rows fade in with a staggered animation (hr.css). Cell values are inserted without HTML escaping, which is an XSS risk (`hr.js:162-197`).

**Search and filters (all client-side, over the full list loaded once)**
- **Search input** (placeholder "Search workers..."):
  - Runs on Enter (`keypress`) or the "Search" button.
  - Case-insensitive substring match on first_name, last_name, employee_id, phone and position (`hr.js:209-218`).
- **Status select:** All Status / Active / Inactive / Terminated. Filters on `change`.
- **Department select:** "All Departments" plus names from `GET /api/settings/departments` (the Settings Department table). Exact match on `worker.department`, filtered on `change`.
- **"Clear Filters":** resets all three controls and re-renders.
- The server also accepts `search`, `status` and `department` query parameters on `/api/workers` (`hr_routes.py:45-72`), but the UI never sends them.

**4. Add/Edit Worker form (`#workerForm`)**
The form uses HTML5 `checkValidity`/`reportValidity`. Required fields that are invalid get a red border (`hr.css:793`).

| Label | id → payload key | Type | Req | Default / notes |
|---|---|---|---|---|
| Employee ID * | employeeId → employee_id | text | yes | trimmed; must be unique (server) |
| CNIC * | cnic → cnic | text | yes | **no format validation anywhere** (only required + unique server-side) |
| First Name * | firstName → first_name | text | yes | |
| Last Name * | lastName → last_name | text | yes | |
| Email | email → email | email | no | browser email validation; "" sends null |
| Phone * | phone → phone | text | yes | phone-formatter auto-binds to id `phone` (see below) |
| Address * | address → address | textarea (3 rows) | yes | |
| Date of Birth * | dateOfBirth → date_of_birth | date | yes | |
| Hire Date * | hireDate → hire_date | date | yes | defaults to today on Add, as a UTC date via `toISOString` (`hr.js:257`) |
| Position * | position → position | text | yes | free text |
| Department * | department → department | select | yes | options come from Settings departments. On Edit, if the worker's department is not in the list, it is appended as "X (Legacy)" (`hr.js:296-314`) |
| Salary | salary → salary | number, step 0.01, min 0 | no | parseFloat or null |
| Status | status → status | select | no | active (default) / inactive / terminated |
| Emergency Contact Name | emergencyContactName | text | no | "" sends null |
| Emergency Contact Phone | emergencyContactPhone | text | no | **not** auto-formatted, because its id is not in the formatter list |
| Notes | notes | textarea | no | "" sends null |

**Phone formatting** (`phone-formatter.js:9-61`):
- Strips everything except digits and `+`.
- `+92xxxxxxxxxx` becomes `+92 xxx xxxxxxx`, capped at 10 digits after +92.
- A number starting with `0` becomes `0xxx xxxxxx(x)`, capped at 11 digits.
- A number without a leading 0 and longer than 3 digits gets a 0 prepended.
- Runs on input (preserving cursor position), on paste and on blur.

**Save**
- **Endpoints:**
  - Add: POST `/api/workers`.
  - Edit: PUT `/api/workers/{id}`.
  - Both send the full payload above.
- **Server validation on POST** (`hr_routes.py:114-127`):
  - Required fields: employee_id, first_name, last_name, phone, address, cnic, date_of_birth, hire_date, position, department. Error message: "{Field Title} is required".
  - Duplicate checks: "Employee ID already exists", "CNIC already exists" (400).
  - Bad date: "Invalid date format. Use YYYY-MM-DD".
  - `status` defaults to `active`.
- **PUT** updates only the keys present, and re-runs both uniqueness checks excluding the current worker (`hr_routes.py:180-202`).
- **Success:** toast with the server message ("Worker created successfully" / "Worker updated successfully"), then the list reloads and the modal closes.
- **Error:** a generic toast "Error saving worker. Please try again." The server's message appears only in the global APIHelper banner.
- The modal closes on Cancel, ×, or a click on the backdrop. There is no submit button, so Enter does not submit.

**Delete**
- The confirm modal reads "Are you sure you want to delete {first} {last}?".
- `DELETE /api/workers/{id}` is a hard delete. Toast "Worker deleted successfully", then the list reloads. Error toast: "Error deleting worker. Please try again."

**13. Quirks**
- After a save, delete or "Clear Filters", the full list is shown even if search or filters are still set.
- The department filter lists Settings departments, including inactive ones (no `is_active` filter). Workers whose department text is not a Settings department can only be found under "All".
- notification-utils.js is loaded twice (head and body).
- Probable bug: hard-deleting a worker who has attendance or payroll rows will likely fail with a 500 "Failed to delete worker".
  - `AttendanceRecord.worker_id` is NOT NULL with no cascade (`models.py:691,702`).
  - The `payroll_runs` backref has no ORM cascade, so SQLAlchemy will try to set the FK to NULL.
  - Only salary advances cascade (`models.py:614-615`).
- `GET /api/workers/departments` and `/api/workers/positions` (distinct values from Worker) exist but nothing calls them. The same is true of `/api/workers/debug` (admin) and `/api/workers/test-auth`.

---

## attendance.html — Attendance

**1. Purpose, URL, access**
- List and manually record check-in/check-out. URL `/attendance.html` (`app.py:316`), linked from the HR hub and the nav "Attendance".
- Page gate is `hr`.
- API access:
  - GET: admin, accountant, inventory_manager.
  - POST, PUT, DELETE: admin, accountant.
- **No period lock on attendance.** Attendance in a closed or already-paid month can still be edited.

**2. Layout**
- Header: "Attendance" / "Record and view check-in / check-out". Back goes to `/hr`.
- **Filter bar:**
  - Worker select ("All Workers").
  - From and To date inputs.
  - Apply and Clear buttons.
  - "Manage devices" link to `/hr/device-management`.
  - "+ Add Record" button.
- Table below the filter bar, plus the Add/Edit modal.

**3. Table**
- Columns: Date | Employee ID | Name | Check-in | Check-out | Hours | Notes | Actions.
- **Data:** `GET /api/attendance?worker_id=&start_date=&end_date=`, including only the parameters that are set.
- **Server order:** `date DESC, check_in_time DESC` (`hr_routes.py:366`). Server enrichments:
  - `worker_name` = "first last", or employee_id if that is blank.
  - `employee_id`.
- **Default filter:** From and To both default to **today**, as a UTC date via `toISOString` (`attendance.js:26-33`), so on load only today's records show.
- **Filter behaviour:**
  - Apply reloads with the current values.
  - Clear sets worker to all and both dates back to today, then reloads.
  - Filters do not apply on change.
- **Worker select:** every worker, of any status, labelled "First Last (EMPID)". Filled from `/api/workers`.
- **Cell formatting:**
  - Times are "HH:MM", from server `to_dict`.
  - Hours shows `"{work_hours} h"`, rounded to 2 decimals by the server, or "—".
  - Empty cells show "—".
  - Values are HTML-escaped.
- **Incomplete record** (exactly one of check-in or check-out present, `attendance.js:103-117`):
  - The row gets class `attendance-row-incomplete` (amber tint, `attendance.css:335`).
  - Check-in only: the Check-out cell shows "(missing out)".
  - Check-out only: the Check-in cell shows "(missing in)".
  - The Notes cell gets a "Manual review" badge (`status-warning`).
- **States:**
  - Loading: `renderLoading` with "Loading attendance...".
  - Empty: "No attendance records.".
  - Error: error box with Retry.
- **No pagination, no column sorting, no source column.** Device rows can be recognised only by their notes text, "ZKTeco push".

**4. Add/Edit Attendance modal (`#attendanceModal`, shown with class `active`)**

| Label | id → key | Type | Req | Notes |
|---|---|---|---|---|
| Worker * | attWorkerId → worker_id (Number) | select | yes (JS check) | **disabled on Edit**, so the worker cannot be changed |
| Date * | attDate → date | date | yes | Add defaults to today (UTC) |
| Check-in (e.g. 09:00) | attCheckIn → check_in_time | **free text**, placeholder 09:00 | no | "" sends null |
| Check-out (e.g. 17:00) | attCheckOut → check_out_time | free text, placeholder 17:00 | no | "" sends null |
| Notes | attNotes → notes | text | no | |

- **Client validation:** only worker and date ("Worker and date are required.").
- **Create:** `POST /api/attendance`. Server behaviour (`hr_routes.py:398-472`):
  - Requires worker_id and date ("worker_id and date are required"). Unknown worker returns 404 "Worker not found". A bad date returns "Invalid date format (use YYYY-MM-DD)".
  - Time strings of up to 5 characters are split as `H:M`. Longer strings go through `strptime('%H:%M')`. **Unparseable times are silently dropped** and stored as NULL.
  - `work_hours = (out - in) / 3600` only when out > in. Otherwise NULL, so an overnight shift gets no hours.
  - `source = "manual"`.
- **Toasts:** "Attendance record added." on create. Errors show the server message.
- **Edit:** `PUT /api/attendance/{id}` with date, check_in_time, check_out_time and notes. Toast "Attendance updated.".
  - **Bug:** a time sent as `null` means "unchanged" (`hr_routes.py:494,504`). Clearing a time field on Edit therefore does **not** remove the stored time.
  - An unparseable non-null time sets the field to NULL.
  - If the date changes and the times are null, the existing datetimes keep their old date.
  - work_hours is recalculated.
- **Delete:** native `confirm("Delete this attendance record?")`, then `DELETE /api/attendance/{id}`. Toast "Record deleted.".

**5. Device vs manual records, pairing, rules**
- **Manual:** each Add creates a new row, so several rows can exist for the same worker and date. There is no uniqueness constraint.
- **ZKTeco push:** the device posts ATTLOG data; each line is merged into the **first** record found for (worker, date) (`hr_routes.py:961`). That can be a manual record; its `source` and notes are kept, and `zkteco_device_id` is overwritten. Full details are under device-management.html.
- **What does not exist:** late, overtime, half-day, absent or leave rules. There is no "mark absent" or "mark leave", no shift definition and no monthly calendar view.
  - `GET /api/attendance/summary?worker_id&month&year` returns days_worked (distinct dates), total_hours, records_count, incomplete_records_count, incomplete_dates and requires_manual_review (`hr_routes.py:551-602`). **No UI calls it.**
- **Payroll impact:** any record for a date counts as a worked day, even one with no times at all.

**13. Quirks**
- Using UTC "today" means that before 05:00 PKT the default filter shows yesterday.
- `attendance.css:139-298` holds dead pull-mode styles: `.zkteco-*` cards, online/recent/offline/unknown badges, `.btn-zkteco.btn-test` and `.btn-sync`, `.sync-info`.
- There are no responsive @media rules in attendance.css.

---

## salaries-management.html — Salaries Management

**1. Purpose, URL, access**
- Per-worker salary slip (preview and print), salary advances, and the monthly payroll run.
- URL `/salaries-management.html` (`app.py:307`), linked from the HR hub and the nav "Salaries".
- Page gate is `hr`.
- API access:
  - `/api/salary/calculate`: admin, accountant, inventory_manager.
  - Advances (list, create, delete): admin, accountant.
  - Payroll preview and history: admin, accountant.
  - **Payroll run: admin** (subject to the RolePermission caveat above).
- The "Run payroll" button is shown to every user who can open the page.

**2. Layout**
- Header: "Salaries Management" / "View salaries and print salary slips". Back goes to `/hr`.
- Filter bar:
  - Department select (from `/api/settings/departments`).
  - Status select (All / Active / Inactive / Terminated).
  - "Clear Filters".
  - "Run payroll" button.
- Workers table, plus three modals: Payroll, Advance and Slip. There is also a hidden `#slipPrintArea`.

**3. Workers table**
- Columns: Employee ID | Name | Position | Department | Salary | Actions.
- **Salary** shows "PKR 30,000.00" (`en-PK`, 2 decimals) or "—".
- **Actions:** "Print slip" (`.btn-slip`) and "Advance" (`.btn-advance`). The Advance button carries the worker's id, name and salary as data attributes.
- **Filters:** client-side, exact match on department and status, applied on change. Clear resets both.
- **No search, sorting or pagination.** Order is the server's `hire_date DESC`.
- **States:**
  - Empty: "No workers to display".
  - Error: renderError with Retry.
- All workers are listed, including inactive and terminated ones and those without a salary.

**6. Salary formula** (`payroll.py:47-93`; same for the slip and the payroll run)
- `DAYS_IN_PAY_MONTH = 30.0`. This is fixed, whatever the length of the calendar month.
- `base_salary` = worker.salary, or 0.
- `days_worked` = the number of **distinct dates** with any AttendanceRecord in that calendar month. Hours, missing punches and empty records are not weighed.
- `daily_rate = base / 30`.
- `earned = round(daily_rate × days_worked, 2)`.
  - A 31-day month with 31 days of records earns 31/30 of the salary.
  - February can earn at most 28/30.
- `total_hours` = sum of work_hours. Display only; it does not affect pay.
- `advances_total` = the sum of SalaryAdvance rows dated in that month.
- `net = round(earned − advances_total, 2)`.
- `overdrawn = net < 0`.
- `incomplete` = records with exactly one of check-in or check-out. This sets `requires_manual_review`, `incomplete_records_count` and `incomplete_dates`.
- **Not in the formula:** overtime, absence deduction (other than days not paid), late penalties, bonuses and tax. `/api/salary/calculate` also returns `deductions = advances_total` and `bonuses = 0`.

**4a. Salary slip modal (`#slipModal`, opened with "Print slip")**
- **Inputs:**
  - Month select (January–December), defaulting to the current month.
  - Year number input, min 2020 and max 2030, defaulting to the current year.
- **Preview updates on:** month `change` and every year keystroke (`input`). Requests are not de-bounced or cancelled, so out-of-order responses could show the wrong month.
- **Data:** `GET /api/salary/calculate?worker_id&month&year` (`hr_routes.py:605-652`). Response: all compute_salary fields, plus first_name, last_name, month, year, deductions, bonuses, `already_paid`, `paid_on` (the run_at date), `review_notes` and `advance_notes`.
  - `review_notes`: "Incomplete attendance exists. Please review missing check-in/check-out entries before final payroll."
  - `advance_notes`: "{first} drew X in advances but only earned Y this month. Recover Z rather than paying it."
- **Fallback when the API fails** (`salaries-management.js:162-219`):
  - The payload uses the full monthly salary as earned and net, with no advances or days.
  - It sets `unverified: true`, which prints a warning: "Could not reach the salary records… Do not pay from this slip."
- **Slip contents** (`renderSlipHtml`, `:251-324`), in order:
  - Heading "GermanATO" and the line "Salary Slip (based on attendance)".
  - Warning boxes, in order: manual review (review_notes), overdrawn (advance_notes), unverified.
  - Table rows:
    - Employee ID, Name, Position, Department.
    - Period ("{MonthName} {year}").
    - Days worked (if not null) and Total hours ("{n} h").
    - Incomplete attendance "{n} record(s)" (only when review is required).
    - Only if advances_total is non-zero: "Earned this month" and "Less advances taken −PKR X", then one sub-row per advance ("  {date} · {notes}", "−PKR amount").
    - Final row: **"Net Salary"**, or **"To recover"** when overdrawn, bold "PKR x" (shown negative when overdrawn).
  - **Not shown on the slip:** base salary, daily rate, payment method of advances, already_paid and paid_on.
- **Print** (`:349-364`):
  - Fetches the payload again, renders it into `#slipPrintArea`, adds `.visible`, calls `window.print()`, then removes `.visible`.
  - **Print CSS** (`salaries-management.css:479-512`):
    - Hidden: `.top-header`, `.main-content`, `.main-footer`, `.modal`, `.no-print` and `.back-btn`.
    - Shown: `.slip-print-area.visible` (display block, padding 40px).
    - White body background.
    - Advance sub-rows forced to #333.
    - Warnings get a grey #999 border with black text.
  - No `@page` rule, no logo and no signature lines.
- Cancel, × and the backdrop close the modal.

**4b. Advance modal (`#advanceModal`, opened with "Advance")**
- Intro line: "{name} · monthly salary PKR x".
- **Form `#advanceForm`** (a real `<form>` submit, so Enter submits):

| Label | id → key | Type | Req | Default |
|---|---|---|---|---|
| Date | advanceDate → date | date | yes | today (UTC) |
| Amount (PKR) | advanceAmount → amount | number, min 1, step 0.01 | yes | blank; JS rejects ≤0 with "Enter an amount above zero" |
| Paid by | advanceMethod → payment_method | select: Cash / Bank Transfer / Cheque | — | Cash (not reset when the modal reopens) |
| Notes | advanceNotes → notes | text, "Optional" | no | blank |

- **Remaining line:**
  - With a salary: "Drawn this month: PKR {total} · still available: PKR {max(salary − total, 0)}". This is worked out in the browser.
  - With no salary: "This worker has no monthly salary set, so nothing can be advanced."
- **History "This month so far":**
  - Data: `GET /api/salary/advances?worker_id&year&month`, for the month of the **selected date**. It reloads when the date changes.
  - Each row: date | PKR amount | notes, or payment_method if there are no notes | × delete.
  - Empty: "Nothing drawn this month."
  - Error: "Could not load this month's advances."
- **Submit:** `POST /api/salary/advances` with `{worker_id, date, amount, payment_method, notes}`. The save button is disabled while the request runs.
- **Server rules** (`hr_routes.py:691-752`):
  - **Period lock** `guard_period(body_date('date'))`: a date in a closed month returns 403 "{YYYY-MM} is closed. Records from a finished month cannot be changed - ask an admin if this needs a correction." Admins bypass it (`period_lock.py:73-89`). Months close automatically once they end unless reopened (`period_lock.py:31-49`).
  - Validation errors, each shown verbatim as a toast:
    - "Choose a worker"
    - "Worker not found" (404)
    - "Enter a valid amount"
    - "An advance must be more than zero"
    - "Enter a valid date (YYYY-MM-DD)"
    - "{first} has no monthly salary set, so there is nothing to advance against"
  - **Cap:** advances already in that month + the new amount must be ≤ base salary + 0.01. Otherwise: "That would take {first} to X against a monthly salary of Y. At most Z can still be advanced this month."
  - The cap is the base salary, not the amount earned, so an advance can be overdrawn at payroll.
  - Stores payment_method (default "Cash"), notes and `created_by` (username). Writes an audit `log_action`.
  - An advance is **not** an Expense.
- **Success:** toast "Advance recorded". Amount and notes are cleared and the history reloads.
- **Delete advance:** `confirm("Remove this advance? The salary calculation will go back up by that amount.")`, then `DELETE /api/salary/advances/{id}`. This is period-locked on the advance's stored date. Toast "Advance removed". There is no edit; the intended workflow is delete and re-add.

**4c. Payroll modal (`#payrollModal`, opened with "Run payroll")**
- **Controls:**
  - Month select, defaulting to the **previous** month.
  - Year number input (min 2000, max 2100), defaulting to the previous month's year.
  - "Booked on" date (`payrollPayDate`), defaulting to today (UTC).
- A note explains that payroll books the **earned** salary, not the amount handed over.
- **Preview:** `GET /api/salary/payroll/preview?year&month` loads on open and on month or year `change`. Changing the pay date does not reload it. The preview writes nothing (`payroll.py:100-137`).
  - It covers **active workers only**, ordered by employee_id.
  - Each worker row carries `blocked`, checked in this order:
    1. "Already paid for this month"
    2. "No attendance recorded" (earned ≤ 0, which also covers a missing salary)
    3. "{n} day(s) missing a check-in or check-out"
    4. null, meaning payable
  - Overdrawn workers are **payable**, and their negative net reduces the total to hand over.
- **Summary cards:** "Workers to pay" (payable_count), "Will be booked" (total_earned), "Already drawn" (total_advances), "To hand over" (total_to_hand_over). Totals cover payable workers only.
- **Table:**
  - Columns: Employee (name with employee_id below) | Days | Earned | Advances ("—" if 0) | To hand over (red if overdrawn) | Status.
  - Status pill: "Ready" (green) or the blocked reason (grey). Blocked rows are shown at 55% opacity.
  - Loading: "Working it out…". Error: "Could not build the preview.". Empty: "No active workers.".
- **Run button:**
  - While loading: disabled.
  - With payable workers: label "Run payroll for N worker(s)".
  - With none: label "Nothing to pay", disabled.
- **Run:** `confirm("Book PKR {total_earned} of wages for {Month} {year}, covering N worker(s)?\n\nPKR {to_hand_over} is what you hand over — the rest was already drawn as advances.\n\nThis cannot be undone from here.")`, then `POST /api/salary/payroll/run {year, month, pay_date}`.
  - Server checks (`hr_routes.py:798-837`):
    - year and month must be integers, with month 1–12.
    - pay_date must be valid ("Enter a valid pay date (YYYY-MM-DD)").
    - **Period lock is checked against pay_date, not the payroll month.**
  - For each payable worker, it creates (`payroll.py:140-193`):
    - An **Expense**: date = pay_date, category `'Labor'`, description `"Salary MM/YYYY - Name (EMPID)"`, amount = **earned**, notes `"{days} days worked. Advances already drawn: X. Handed over at month end: Y."`.
    - A **PayrollRun**: worker, year, month, earned_salary, advances_total, net_paid, expense_id, run_by, run_at.
  - All of this is committed in one transaction, and an audit log entry is written.
  - If nothing was posted: 400 "Nothing to pay for this month." with the skipped list.
  - Response: `{message "Payroll booked for N worker(s)", posted[], skipped[], total_expensed, total_handed_over}`.
- **After success:** toast "Payroll booked: PKR {total_expensed} across N worker(s)", and the preview reloads, so those workers now show "Already paid".
- **Re-running a month:** this is idempotent through the unique key (worker_id, year, month) (`models.py:644-646`). Workers already paid are skipped. Workers who became payable since the last run (for example after attendance was fixed) are paid on the re-run.
- **No UI** to undo a run, re-pay or adjust one. Deleting the Expense leaves the PayrollRun in place (`ondelete SET NULL`). Changing attendance or advances after a run does not change the booked figures.
- **Payroll history** `GET /api/salary/payroll?year&month` returns runs plus total_expensed. **No UI uses it**; only tests do.

**13. Quirks**
- The slip's year input is capped at 2020–2030.
- The `.close-modal` buttons on the payroll and advance modals have no styling (only `.modal-header .close` is styled). The `.pill` base class and `.empty-row` are also unstyled.
- HTML comments at lines 92-94 are misplaced.
- Constants `MONTH_NAMES` and `MONTHS` duplicate each other.
- A stale comment at line 2 refers to a future `/api/salary/record`, which does not exist.
- Advance month detection uses `new Date("YYYY-MM-DD")` (UTC) and then `getMonth()` (local). In timezones behind UTC, the 1st of a month would map to the previous month.
- `already_paid` and `paid_on` are returned but never displayed.

---

## worker_detail.html — Worker Details

**1. Purpose, URL, access**
- One worker's profile with edit and delete. URL `/hr/<int:id>` (`hr_routes.py:27-31`). Flask returns a 404 page if the worker does not exist; the route has no auth.
- Reached via the "View" link on the employees table.
- The JS takes the id from the **last path segment** (`worker_detail.js:32-33`); there is no query parameter. An invalid id shows the toast "Invalid worker ID".
- Page gate is `worker-detail`, which maps to `hr`.
- Assets are loaded with relative `../static/...` paths.

**2. and 7. Sections**
- **Header:** "Worker Details", with the subtitle set to "First Last".
- **Info card:**
  - Name (h2), position and department, plus Edit (orange) and Delete (red) buttons.
  - Detail grid (auto-fit, min 300px; one column at ≤768px):
    - Employee ID, Phone, Email, CNIC.
    - Date of Birth and Hire Date, formatted en-US short, e.g. "Jan 15, 2025".
    - Salary: `Intl.NumberFormat("en-PK", {style:"currency", currency:"PKR", 0 decimals})`, or "N/A" if empty or 0.
    - Status: badge.
    - Address (full width).
    - Emergency Contact and Emergency Phone.
    - Notes (full width).
  - Missing values show "N/A".
- **Not on this page:** attendance history, advances, payroll history, assigned repair orders and documents. Only the profile is shown.

**4. Edit Worker modal**
- Same fields and validation as employees.html, with ids prefixed `edit*`.
- Differences from the employees form:
  - **Department is a free-text input**, not the Settings dropdown.
  - Salary is sent as a raw string, or null; the server converts it with `float()`.
  - The phone formatter binds to both `editPhone` and `editEmergencyContactPhone`.
- Save: "Update Worker", `PUT /api/workers/{id}`. On success: toast with the server message, the card re-renders from `data.worker`, and the modal closes. On error: "Error updating worker. Please try again.".

**Delete**
- Confirm modal: "Are you sure you want to delete this worker?".
- `DELETE /api/workers/{id}`, toast, then a redirect to `/hr` after 1500 ms. The same probable FK failure as on employees.html applies.

**Other behaviour**
- Back goes to `/hr` (the HR hub, not the employees list).
- Modals close on a backdrop click.
- Load error toast: "Error loading worker details. Please try again.".
- `worker_detail.html:123` has a stray `</div>`.

---

## device-management.html — ZKTeco Device Management

**1. Purpose, URL, access**
- Register ZKTeco devices that push attendance to this server (PUSH protocol).
- Two URLs serve this page:
  - `/hr/device-management` (`hr_routes.py:34`). Its docstring still says "pull method".
  - `/device-management.html` (`app.py:325`).
- Linked from the HR hub card and the Attendance page's "Manage devices" button.
- Page gate is `hr`.
- API access:
  - GET: admin, accountant, inventory_manager.
  - POST, DELETE: admin, accountant.

**2. and 8. Layout and what is shown**
- Header: "ZKTeco Device Management" / "Add devices (PUSH). Device sends attendance to this server.". Back goes to `/hr`.
- Section "ZKTeco attendance devices (PUSH)", with "Refresh" (disabled while loading) and "+ Add device" buttons.
- **Instruction hint:** "Add a device by its serial number (SN). On the device, set Cloud Server to this server's URL. Employee ID on device must match Worker Employee ID."
  - The page does not display the actual server URL or port.
- **Device list:** `GET /api/zkteco/devices`, active devices only, ordered by id.
- **Each card shows:**
  - Bold name.
  - "SN: {serial}", plus " · ip:port" only when both IP and port are set.
  - "Last push: {last_seen_at}". This is the raw "YYYY-MM-DD HH:MM:SS" in **UTC** with no timezone label. It is omitted if the device has never been seen.
- **Not shown:** online/offline status, relative time, record counts and push errors. The `last_sync` and `last_sync_status` model fields are unused leftovers from pull mode.
- **Card action:** "Remove" button.
- **Empty state:** 'No devices. Click "Add device" and enter the device serial number (SN). Set Cloud Server on the device to this server.'
- **Error state:** renderError with Retry.
- **No polling;** the list refreshes only manually.

**4. Add device modal** (shown with class `show`; hr.css provides the modal styles)

| Label | id → key | Type | Req | Notes |
|---|---|---|---|---|
| Name * | deviceName → name | text, "e.g. Office entrance" | yes (JS: "Name is required.") | the server would default it to the SN |
| Serial number (SN) * | deviceSn → serial_number | text, "e.g. UFS2252500425" | yes (JS: "Serial number (SN) is required.", checked first) | unique |
| IP address (optional) | deviceIp → ip_address | text | no | not validated; not used by the push protocol |
| Port (optional) | devicePort → port | number 1–65535, placeholder 4370 | no | parseInt; the server ignores invalid values |
| Timeout (optional) | deviceTimeout → timeout | number 5–120, default 30 | no | the server clamps it to 5–120 (default 30); unused |

- **Endpoint:** `POST /api/zkteco/devices` (`hr_routes.py:1014-1068`).
  - Error "serial_number is required".
  - An active duplicate returns 400 "A device with this serial number is already registered".
  - A **soft-deleted** SN is re-activated with the new values, message "Device re-added" (201).
  - An IntegrityError returns "A device with this serial number already exists".
- **Success:** toast "Device added successfully.", the modal closes and the list reloads.
- **Remove:** `confirm("Remove {name} from device list? You can add it again later.")`, then `DELETE /api/zkteco/devices/{id}`. This is a **soft delete** (`is_active=False`). Toast "Device removed.".

**5. Push protocol** (no auth; `hr_routes.py:864-997`)
- **`GET /iclock/getrequest?SN=`** (heartbeat): updates `last_seen_at` (UTC) if the SN is registered and active, and always returns plain-text `OK`. It never sends commands to the device.
- **`GET /iclock/cdata?SN=`** (handshake): updates last_seen and returns `OK`. It does not return the standard ZK options block.
- **`POST /iclock/cdata?SN=&table=`:** only `table=ATTLOG` is persisted. OPERLOG and other tables are logged at debug level and acknowledged with `OK`.
  - It always returns `OK`, even on internal errors, which are rolled back.
- **ATTLOG parsing:**
  - The body has one record per line; fields are tab-separated `user_id`, `YYYY-MM-DD HH:MM:SS` and `punch`, and extra fields are ignored.
  - `user_id` must equal `Worker.employee_id` exactly. Unknown users are skipped with a warning.
  - Punch must be `0`, `1` or `255`. Others, such as ZK break or overtime codes 2–5, are skipped.
  - Bad timestamps are skipped.
- **Merge rule** (one record per worker per date, `date = timestamp.date()`):
  - If no record exists, one is created with notes and source set to "ZKTeco push".
  - `0` (in): `check_in = min(existing, ts)`.
  - `1` (out): `check_out = max(existing, ts)`.
  - `255` (generic):
    - If check-in is empty, it becomes the check-in.
    - Else if the punch is earlier than the check-in, it replaces the check-in.
    - Else, if it is later than the current check-out (or there is none), it becomes the check-out.
  - `work_hours = round((out - in) / 3600, 2)` if out > in, else NULL.
  - Midnight splits overnight shifts into two days.
  - Device timestamps are stored as naive datetimes, with no timezone conversion.
- `zkteco_device_id` is set when the SN matches an **active** device; otherwise it is NULL.
- **Pushes from unregistered or removed devices are still accepted and recorded.** Anyone who can reach the server can inject attendance.
- Each request loads every worker and commits once.

**zkteco_push_server.py (developer test tool, not part of the app)**
- A standalone `http.server` that mirrors the two `/iclock` endpoints. It logs heartbeats, ATTLOG lines (punch "0" is labelled IN, anything else OUT), OPERLOG lines and selected `options` keys (DeviceName, MAC, IPAddress, FWVersion, UserCount, TransactionCount).
- It always replies `OK` and stores nothing.
- CLI: `--host/-H` (default 0.0.0.0), `--port/-p` (default **5000**, although the comment says 5001).
- The port-in-use hint checks `errno 98`, which is Linux only; macOS uses 48.

**13. Quirks**
- `device-management.css` contains dead styles: `.btn-test`, `.btn-sync`, `.sync-info`, `.sync-hint`, `.checkbox-label`, `.form-hint`.

---

### Cross-cutting: persisted state, keyboard, departments
- **localStorage / sessionStorage:** nothing page-specific. Only the auth keys (accessToken, refreshToken, user, userPermissions) are used, by the shared auth module.
- **URL state:** the worker id is the path segment `/hr/<id>`. The `?from=hr` check in hr.js is dead code.
- **Keyboard:** Enter runs the employees search. Enter submits the advance form. There are no other shortcuts and no autofocus.
- **Departments:** worker forms and filters use `GET /api/settings/departments`, the Settings Department table, CRUD at `/api/settings/departments[/<id>]` (`settings_routes.py:19-131`). Inactive departments are not filtered out.
  - `Worker.department` is a free string, not a foreign key, so renaming a department does not update existing workers.
- **Responsive:** hr.css and worker_detail.css have breakpoints at 768px and 480px. At those widths forms become one column, the modal footer stacks, the Back label and subtitle are hidden, and table padding shrinks. salaries-management.css and attendance.css have no @media rules except print. All tables use `overflow-x:auto`.

### Endpoints used
| METHOD | path | page/action |
|---|---|---|
| GET | /api/workers | employees list; attendance worker dropdowns; salaries table |
| POST | /api/workers | employees: add worker |
| GET | /api/workers/{id} | worker_detail: load |
| PUT | /api/workers/{id} | employees edit; worker_detail edit |
| DELETE | /api/workers/{id} | employees delete; worker_detail delete |
| GET | /api/settings/departments | employees filter + form; salaries filter |
| GET | /api/attendance?worker_id&start_date&end_date | attendance list |
| POST | /api/attendance | attendance add |
| PUT | /api/attendance/{id} | attendance edit |
| DELETE | /api/attendance/{id} | attendance delete |
| GET | /api/salary/calculate?worker_id&month&year | salaries: slip preview / print |
| GET | /api/salary/advances?worker_id&year&month | salaries: advance modal history |
| POST | /api/salary/advances | salaries: record advance (period-locked) |
| DELETE | /api/salary/advances/{id} | salaries: remove advance (period-locked) |
| GET | /api/salary/payroll/preview?year&month | salaries: payroll modal |
| POST | /api/salary/payroll/run | salaries: run payroll (admin; period-locked on pay_date) |
| GET | /api/zkteco/devices | device-management list |
| POST | /api/zkteco/devices | device-management add or re-add |
| DELETE | /api/zkteco/devices/{id} | device-management remove (soft) |
| GET | /iclock/getrequest | ZKTeco device heartbeat (no auth) |
| GET/POST | /iclock/cdata | ZKTeco device handshake / ATTLOG push (no auth) |
| GET | /hr, /hr/{id}, /hr/device-management, /employees.html, /attendance.html, /salaries-management.html, /device-management.html | page routes |
| — (no UI caller) | GET /api/attendance/summary, GET /api/salary/payroll, GET /api/workers/departments, GET /api/workers/positions, GET /api/workers/debug, GET /api/workers/test-auth | backend-only; payroll history is used only in `tests/test_api_smoke.py:213` |
| — (does not exist) | /api/salary/record | mentioned only in a comment (`salaries-management.js:2`) |

### Files read
| File | Lines |
|---|---|
| frontend/employees.html | 309 |
| frontend/attendance.html | 138 |
| frontend/salaries-management.html | 249 |
| frontend/worker_detail.html | 335 |
| frontend/device-management.html | 157 |
| static/js/hr.js | 447 |
| static/js/attendance.js | 278 |
| static/js/salaries-management.js | 652 |
| static/js/worker_detail.js | 329 |
| static/js/device-management.js | 208 |
| static/js/phone-formatter.js | 167 |
| static/css/salaries-management.css | 678 |
| static/css/attendance.css | 444 |
| static/css/device-management.css | 170 |
| static/css/hr.css | 1097 (behavioural sections read: modal, status badges, forms, responsive, a11y; hub nav-card and base theme only skimmed) |
| static/css/worker_detail.css | 802 (card, grid, badges, modal and responsive read; base theme skimmed, as it duplicates hr.css) |
| hr_routes.py | 1085 |
| payroll.py | 193 |
| zkteco_push_server.py | 180 |
| models.py | 875 (read Expense, FinancialPeriod, Worker, SalaryAdvance, PayrollRun, AttendanceRecord, ZKTecoDevice, Department: lines 298-372, 539-790) |
| settings_routes.py | 248 |
| Supporting: period_lock.py (lines 1-120), jwt_auth.py (lines 1-200), static/js/auth_jwt.js (lines 1-60, 200-290), static/js/api-helper.js (lines 1-200, 384-545), app.py (lines 290-360 + blueprint registration), tests/test_api_smoke.py (lines 205-240) | partial, for rules only |
