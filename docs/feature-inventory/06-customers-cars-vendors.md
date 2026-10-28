# Feature inventory: Customers & Cars, Vendors (ledger and purchase orders)

## car.html — Car & Customer Management

### 1. Purpose, URL, access
- **Purpose:** keep the customer master list and the cars each customer owns. Customers can be added, edited, deleted and searched, and so can cars.
- **URL:** `/car.html`, served by `app.py:192-195` (`serve_car`) with no server-side auth. The sidebar links it as "Cars & customers" (`app-shell.js:73`, permission `car`).
- **Client page guard:** none. `car.js` never calls `auth.requirePageAccess("car")`, unlike the vendor pages. Access is enforced only on the API side. An unauthenticated user hits a 401, the token refresh fails, and api-helper redirects to `login.html` (`api-helper.js` performRequest).
- **API access** (`car_routes.py`, blueprint prefix `/api`, `app.py:81`):
  - `GET /api/customers`, `/api/cars`, `/api/cars/<id>`, `/api/cars/search`, `/api/customers/search`, `/api/cars/customer/<id>`: `@login_required`. Any active logged-in user, with no permission check.
  - `POST`/`PUT` customers and cars: `role_required(['admin','accountant','inventory_manager'])`.
  - `DELETE` customers and cars: `role_required(['admin','accountant'])`.
  - `role_required` maps `/api/customers*` and `/api/cars*` to permission `car` (`jwt_auth.py:42-43`). Admin always passes. While the RolePermission table is empty, the role fallback list above applies. Once that table has rows, the role must hold the `car` permission.
  - Default role permissions: admin and accountant have `car`. inventory_manager does NOT have `car` (`jwt_auth.py:24-35`), so once RolePermission is seeded that role loses create/edit access.

### 2. Layout
- **Header:** logo, "Car & Customer Management" / "Manage cars and customers", and a Back button. app-shell hides the Back button and logo with CSS (`app-shell.css:488-495`).
- **Back button href** (`car.js:19-35`): `?from=` param, then `localStorage.lastPage`, then "admin". Values map as follows:
  - `admin` → `admin.html`
  - `home` → `home.html`
  - `invoiceSystem` → `invoiceSystem.html`
  - anything else → `admin.html`
  - The page then sets `localStorage.lastPage = "car"` (`car.js:38`).
- **Two tabs:** "Cars" (default active) and "Customers" (`car.html:48-96`). Switching tabs only toggles the `.active` class (`car.js:47-64`). Tab state is not persisted and nothing is reloaded on switch.
- **Three modals:** Car add/edit, Customer add/edit, Customer Cars (read view).
- Footer.

### 3. Lists and tables

**Cars table** (`car.html:149-166`, `car.js:326-371`)
- **Columns:** Make | Model | Plate No. | Mileage | VIN | Color | Chassis # | Customer | Actions.
  - Empty VIN, Color and Chassis show "-".
  - The Customer cell shows `customer_name` plus a `<span class="customer-code">` badge (CNxxx, styled in `theme.css:1178`).
  - Actions: Edit, Delete.
- **Order:** server-side `ORDER BY Car.id` ascending. There is no client sort and no pagination.
- **Orphan cars are hidden.** `GET /api/cars` does an INNER `join(Customer)` (`car_routes.py:270`), so cars with `customer_id NULL` never appear. Such cars can be created by the invoice and repair-order flows. Search and `GET /api/cars/<id>` also inner-join.
- **Empty state:** car icon, "No cars found", "Add your first car to get started" (colspan 9).
- **Loading:** "Loading..." row. `showLoading` uses colspan 6 even on the 9-column table, a cosmetic bug (`car.js:605-611`).
- **Search** (`#car-search`):
  - Triggered by the button or the Enter key (`car.js:98-125`). There is no live filtering.
  - An empty query reloads the full list.
  - Calls `GET /api/cars/search?q=`. The backend matches `ILIKE %q%` on make, model, plate_no and customer name (`car_routes.py:567-574`). It does NOT match VIN, chassis, color, customer phone or customer code.
  - **Search results omit `vin`, `color` and `chasis_no`** (`car_routes.py:578-590`), so those columns show "-" after a search.
  - **Data-loss bug:** pressing Edit on a search result opens the form with VIN/Color/Chassis blank. Saving then sends `null` and wipes those fields (`car.js:483-491`, `545-547`; backend sets them unconditionally, `car_routes.py:481-483`).
  - **"Did you mean":** on zero results the backend adds `did_you_mean` and `closest`, using a corpus of distinct `Car.plate_no` (`car_routes.py:598-600`, `search_suggestions.py`). **car.js ignores both fields** and just shows the empty state.

**Customers table** (`car.html:225-239`, `car.js:373-419`)
- **Columns:** ID (shows `code`, e.g. CN001) | Name | Phone | Address | Cars (a "View Cars" button) | Actions (Edit, Delete).
- **Order:** `ORDER BY Customer.id`. No pagination.
- **Empty state:** "No customers found" / "Add your first customer to get started".
- **Search** (`#customer-search`):
  - Button or Enter. An empty query reloads the full list.
  - Calls `GET /api/customers/search?q=`, matching `ILIKE` on name, phone and address (`car_routes.py:619-625`). It does NOT match the code (typing "CN001" finds nothing).
  - Zero results return suggestions from a corpus of distinct `Customer.name`. These are ignored by the UI.
  - Search replaces the global `customers` array but not the car-modal customer dropdown, which is filled only in `loadCustomers`.

**Customer code** (`models.py:213-224`)
- `code` is derived, not stored: `f"CN{id:03d}"`, giving CN001 … CN999, CN1000.
- It is returned by the customer list, search, create, update and cars-by-customer endpoints, and as `customer_code` on car rows.

**Customer Cars modal** (`car.html:369-416`, `car.js:421-474`)
- Opened by "View Cars", which calls `GET /api/cars/customer/<id>`.
- Header block shows the customer's name, phone and address. The title is always "Customer Cars".
- **Columns:** Make | Model | Plate | Mileage | VIN | Color | Chassis # | Actions (Edit, Delete).
- **Bug:** `/api/cars/customer/<id>` does not return vin, color or chasis_no (`car_routes.py:672-683`), so those columns always show "-".
- **Edit from this modal** calls `editCar(id)`, which looks the car up in the global `cars` array (`car.js:483`). If the Cars tab is showing search results that exclude this car, the modal opens titled "Edit Car" with blank fields.
- The car modal opens on top of the Customer Cars modal. After a save or delete, the Customer Cars modal is not refreshed; only the main cars table reloads.
- Empty state: "This customer has no cars registered".
- The table has min-width 900px with horizontal scroll (`car.css:907-915`).

### 4. Forms

**Car form** (`car.html:268-318`, submit handler `car.js:537-556`)

| Label | id → payload key | Type | Required | Notes |
|---|---|---|---|---|
| Make * | car-make → make | text | yes (HTML) | trimmed |
| Model * | car-model → model | text | yes | trimmed |
| Plate Number * | car-plate → plate_no | text | yes | trimmed; duplicates allowed (`car_routes.py:359`) |
| Mileage * | car-mileage → mileage | text (free string; DB String(50)) | yes | trimmed |
| VIN (Optional) | car-vin → vin | text, maxlength 17, placeholder "17-character VIN" | no | `''` → null |
| Color | car-color → color | text, placeholder "e.g. White, Black, Red" | no | `''` → null |
| Chassis Number | car-chasis → chasis_no | text, placeholder "Chassis #" | no | `''` → null |
| Customer * | car-customer → customer_id | select, "Select Customer" + one option per customer (text = name only, no code, so same-name customers cannot be told apart) | yes | `parseInt` |

- **Endpoints:** add is `POST /api/cars`; edit is `PUT /api/cars/<id>`. The payload is JSON with all eight keys.
- **Backend validation** (`validate_car_data`, `car_routes.py:14-52`):
  - Every field is optional. A field that is present and not the string "N/A" must be non-blank.
  - `customer_id` must be an int. If given, the customer must exist, otherwise 404 "Customer not found".
  - Make, model and mileage are stored as `str(value).strip()`. A missing key is stored as the literal string "None"; the UI always sends them.
- **Duplicate check:** VIN must be unique, on create only. A clash returns 409 `{error:"Car with this VIN already exists", details, existing_car_id}` (`car_routes.py:371-378`). Update has no VIN duplicate check.
- **Update** overwrites every field, including `customer_id` (`car_routes.py:477-484`). A missing `customer_id` would unassign the car.
- **Ownership transfer:** done by editing the car and picking another customer. No history or audit is kept, and `log_action` is not called by car_routes.
- **Success:** `alert("Car created successfully")` or `alert("Car updated successfully")`, then the modal closes and the cars table reloads.
- **Error:** `alert("Error: Error creating car: <msg>")`, plus api-helper's global error banner.
- **Edit form fill:** `openCarModal` fills the fields from the cached row (`car.js:477-499`).
- **Closing:** the X button, Cancel, or a backdrop click closes the modal and resets the form. Esc does nothing.

**Customer form** (`car.html:345-364`, `car.js:558-572`)

| Label | id → key | Type | Required |
|---|---|---|---|
| Name * | customer-name → name | text | yes |
| Phone * | customer-phone → phone | tel | yes |
| Address * | customer-address → address | textarea | yes |

- **Phone formatting:** `phone-formatter.js` auto-attaches to `customer-phone` on DOMContentLoaded (it is in the ID list at `phone-formatter.js:136-143`). It reformats on input, paste and blur, keeping the cursor in place:
  - `+92` → `+92 xxx xxxxxxx` (at most 10 digits after +92)
  - leading `0` → `0xxx xxxxxx(x)` (at most 11 digits)
  - no leading 0 → a 0 is prepended: `0xxx …`
- **Endpoints:** add is `POST /api/customers`; edit is `PUT /api/customers/<id>`. Payload `{name, phone, address}`.
- **Backend:** all fields are optional but must be non-blank if present (`car_routes.py:54-74`). Values are stored with `str().strip()`, so a missing key becomes "None".
- **Duplicate check:** on create only, an exact match on name + phone + address returns 409 `{error:'Customer already exists', details, existing_customer_id}` (`car_routes.py:122-134`). Update has no duplicate check. Because `details` is a string, not an array, api-helper does not append it; the user sees only "Customer already exists".
- **Success:** alert, then the modal closes and the customers table and car dropdown reload.

**Deletes**
- **Car:** `confirm("Are you sure you want to delete this car?")`, then `DELETE /api/cars/<id>`, then the cars table reloads.
- **Customer:** `confirm("…This will also delete all associated cars.")`, then `DELETE /api/customers/<id>`. Both tables reload.
  - The ORM cascade `all, delete-orphan` deletes the customer's cars (`models.py:211`).
  - Invoices and repair orders keep their text. Their `customer_id` and `car_id` FKs are `ON DELETE SET NULL` (`models.py:110-113`, `264-267`), so history survives.

### 5. Customer → documents linkage
- **The car page shows no invoices, repair orders or history for a customer or car.** There is no endpoint for this in car_routes.
- The link exists only in data:
  - Invoice and RepairOrder have `customer_id` and `car_id` FKs (indexed, SET NULL).
  - These are set by `document_links.apply_links()` when documents are created or saved elsewhere.
  - `resolve_customer`: an explicit id wins. Otherwise it tries an exact name+phone match, then a unique phone match, then a unique name match.
  - `resolve_car`: an explicit id wins. Otherwise it tries VIN, then plate, preferring a car owned by that customer, then a unique match.
  - `adopt_orphan_car`: if a document names both a customer and an ownerless car, the car is assigned to that customer. It never reassigns a car that already has an owner (`document_links.py:81-92`).
- **Parity note:** a "customer history" view does not exist today. The data to build one exists.

### 6–9. Ledger, purchase orders, exports, client calculations
Not applicable to this page. There is no export and no print on the car page.

### 10. Keyboard, autofocus, polling
- Enter in either search box runs the search.
- Cmd/Ctrl+K command palette comes from app-shell (shared).
- No autofocus. No polling.

### 11. Persisted state
- `localStorage.lastPage` is read, then set to "car".
- `?from=` query param.
- Tokens are shared via auth_jwt.

### 12. Quirks, bugs, dead code
- No client-side `requirePageAccess("car")`.
- Orphan cars are invisible (inner join).
- Search and cars-by-customer responses lack vin/color/chasis_no, which causes blank columns and **data loss on edit**.
- Suggestions are returned but not rendered.
- Loading-row colspan mismatch.
- Notifications use `alert()`; the page does not use notification-utils.
- The customer dropdown shows names only (no code).
- No VIN uniqueness check on update.
- `GET /api/cars/<id>` exists but this page does not use it.
- Footer says "© 2025".
- app-shell `guardUnsavedChanges`: typing in a `<form>` sets a dirty flag that triggers a beforeunload prompt. A submit or `api:saved` clears it. Inputs whose id contains "search" are ignored.

---

## vendors.html — Vendor Management

### 1. Purpose, URL, access
- **Purpose:** the supplier master list: create, edit, delete, and open a vendor's ledger and purchase orders.
- **URL:** `/vendors`, served by `vendor_routes.py:18-21` with no server auth. Sidebar "Vendors" (`app-shell.js:72`).
- **Command palette action:** "New vendor" goes to `/vendors?new=1`. app-shell `handleNewParam` then calls `window.openAddVendorModal()` on window load (`app-shell.js:361-370`).
- **Client guard:** `auth.requirePageAccess("vendors")` (`vendors.js:27`).
  - If `auth` is undefined it retries once after 100 ms, then redirects to `login.html` (`vendors.js:9-20`).
  - Without permission: alert "You do not have permission to access this page.", then redirect home (`auth_jwt.js:257-265`).
- **API:** every `/api/vendors*` route is `role_required(['admin','accountant'])`, permission `vendors` (`jwt_auth.py:47`). The default accountant role has `vendors` and `vendor-detail`; inventory_manager does not.

### 2. Layout
- **Header:** "Vendor Management" / "Manage vendors, ledger entries, and consignment reports", and a Back button. The Back button is hidden by app-shell; if clicked it would go to `/home.html` (`vendors.js:37-45`).
- **Controls row:** "Add New Vendor" button, "Refresh" button, search input and search button.
- **Table**, an Add/Edit Vendor modal, and a Delete confirmation modal.

### 3. List
- **Columns** (`vendors.html:99-108`, `vendors.js:150-194`): ID | Name | Company | Contact Person | Phone | Email (shows "N/A" if empty) | Created | Actions (View, Edit, Delete). All values are HTML-escaped.
- **Created** uses `formatDate` (`vendors.js:319-348`):
  - Input "YYYY-MM-DD HH:MM:SS" is treated as UTC by appending "Z".
  - Rendered as `toLocaleDateString("en-US", {year:numeric, month:short, day:numeric, hour:2-digit, minute:2-digit, timeZone:"Asia/Karachi"})`, e.g. "Oct 7, 2025, 03:08 PM".
  - Empty input gives "N/A"; unparseable input gives "Invalid Date".
- **Order:** server `ORDER BY created_at DESC` (`vendor_routes.py:49`).
- **Response:** `{vendors:[...]}`. The client also tolerates a bare array (`vendors.js:136-139`).
- **Search is client-side only.**
  - It filters live on every `input` event, and also on the search button (`vendors.js:50-56`, `126-129`, `197-206`).
  - Match: case-insensitive substring on name, company_name, contact_person, phone and email. CNIC and address are not searched.
  - The server's `?search=` param, with did_you_mean/closest suggestions built from distinct vendor names plus company names (`vendor_routes.py:34-58`), **is never used by the UI**.
- **Refresh** reloads the full list and does NOT re-apply the text still sitting in the search box.
- **Empty state:** `APIHelper.renderEmpty(tbody, "No vendors found")`.
- **Error state:** `APIHelper.renderError(..., retry=loadVendors)`.
- **Loading:** "Loading vendors...".
- No pagination and no sorting UI.
- **View** navigates to `/vendors/<id>` (`vendors.js:209-211`).

### 4. Forms

**Vendor form** (`vendors.html:135-191`). Save is a button click, not a form submit. HTML validity is checked with `checkValidity` / `reportValidity` (`vendors.js:264-269`).

| Label | id → key | Type | Required | Notes |
|---|---|---|---|---|
| Vendor Name * | vendorName → name | text | yes | trimmed |
| Company Name * | companyName → company_name | text | yes | |
| Contact Person * | contactPerson → contact_person | text | yes | |
| Phone * | phone → phone | text | yes | Pakistani auto-format, because id `phone` is in phone-formatter's list |
| Email | email → email | email (browser validation) | no | `''` → null |
| CNIC | cnic → cnic | text, no format or mask | no | `''` → null |
| Address * | address → address | textarea rows 3 | yes | |

- Hidden `vendorId` field.
- **Create:** `POST /api/vendors`.
  - The server requires truthy name, company_name, contact_person, phone and address, otherwise 400 "`<field>` is required".
  - Duplicate check: exact name + company_name + phone returns 409 "Vendor already exists" with details and `existing_vendor_id` (`vendor_routes.py:97-109`).
  - Values are not trimmed server-side.
  - Writes `log_action(CREATE,'vendors')`.
  - Returns 201 with `{message:'Vendor created successfully', vendor}`.
- **Edit:** the Edit button fills the form from the cached row, retitles the modal "Edit Vendor", and saves with `PUT /api/vendors/<id>`.
  - The server does a partial update via `data.get(field, old)`, so sending `null` email or CNIC clears it.
  - No duplicate check. Sets `updated_at`, logs UPDATE.
- **Success:** `showSuccess(data.message)` (notification-utils toast), then the list reloads and the modal hides.
- **Error:** `showError(error.message)`. The 409 `details` string is not shown.
- **Delete:** opens the confirm modal: `Are you sure you want to delete vendor "<name>"? This action cannot be undone and will also delete all associated ledger entries and consignment records.` Confirm calls `DELETE /api/vendors/<id>`.
  - The ORM cascade removes the vendor's VendorLedger and PurchaseOrder rows (`models.py:438-439`).
  - Logged as DELETE. Then a toast "Vendor deleted successfully" and a reload.
- **Modals:** shown with `style.display="flex"` plus class `show`. They close only via the X or Cancel; there is no backdrop-click or Esc close.

### 5–9.
No document linkage, ledger, export, print or client calculations on this page.

### 10. Keyboard
- Cmd/Ctrl+K palette (shared).
- No Enter handler (search is live anyway).
- No autofocus. No polling.

### 11. Persisted state
- `?new=1` opens the add modal (via app-shell).
- No localStorage use of its own.

### 12. Quirks
- **`?edit=<id>` is not handled.** The vendor detail page's Edit button sends users to `/vendors?edit=<id>` (`vendor_detail.js:637-639`), but vendors.js never reads it. The user just lands on the list; the edit feature from the detail page is broken.
- The server search and its suggestions are dead from the UI's point of view.
- The delete message mentions "consignment records", legacy naming for purchase orders.

---

## vendor_detail.html — Vendor Details

### 1. Purpose, URL, access
- **Purpose:** one vendor's profile, their payable ledger (debit, credit, running balance, proof attachments) and their purchase orders.
- **URL:** `/vendors/<int:vendor_id>`, served by `vendor_routes.py:23-27`.
  - The server runs `Vendor.query.get_or_404` with no auth, so an unknown id returns an HTML 404 before any JS runs.
  - The JS takes the id from the **last path segment**: `parseInt(pathname.split("/").pop())` (`vendor_detail.js:36-37`). There is **no query-param form.**
  - Opening `vendor_detail.html` directly gives NaN, which shows the toast "Invalid vendor ID" and loads nothing.
- **Client guard:** `auth.requirePageAccess("vendor-detail")`, which maps to the `vendors` permission (`auth_jwt.js:4-9`). The same 100 ms auth retry as vendors.js applies.
- **API:** admin and accountant, permission `vendors`. The same rule covers `/api/ledger*`, `/api/purchase-orders*` and `/api/consignments*` (`jwt_auth.py:47-50`).
- **Relative redirect bug:** `"login.html"` redirects (auth retry fallback, api-helper on refresh failure, `auth.requireAuth`) resolve to `/vendors/login.html`, which 404s on this page.

### 2. Layout
- **Header h1** is replaced with `"<name> - <company_name>"`. The subtitle `#vendorCompany` is hidden after load (`vendor_detail.js:205-214`). The Back button (hidden by app-shell) goes to `/vendors`.
- **Vendor info card:**
  - Name (h2) and company.
  - **Edit** (pencil) goes to `/vendors?edit=<id>`, which is broken as noted above.
  - **Delete** (trash) deletes the vendor.
  - Detail grid: Vendor Name, Company Name, Contact Person, Phone, Email (or "N/A"), CNIC (or "N/A"), Address. These are **not HTML-escaped** (`vendor_detail.js:229-258`).
  - Created and updated dates are not shown.
- **Two tabs:** "Ledger Statement" (`#ledger`, default) and "Purchase Orders" (`#consignments`).
  - `switchTab()` refetches the tab's data on every switch (`vendor_detail.js:60-91`).
  - Tab state is not persisted.
- **Ledger tab:** header with "Add Transaction" and "Export Excel"; a filter card (Start Date, End Date, Filter, Clear); the table; and three summary cards: **Total Debits** (red), **Total Credits** (green), **Closing Balance** (maroon) (`vendor_detail.css:605-621`).
- **Purchase Orders tab:** header with "Add Purchase Order" and "Export Excel"; filters (Start Date, End Date, Invoice No text "Search by invoice number...", Filter); the table. There is no Clear button and no totals.

### 3. Lists

**Ledger table** (`vendor_detail.html:228-252`, `vendor_detail.js:293-342`)
- **Columns:**
  - **Date / Time:** shows `entry.created_at || entry.date`. created_at always exists, so this is the **raw UTC insert timestamp** "YYYY-MM-DD HH:MM:SS". The user-chosen transaction `date` is never displayed, even though filtering and sorting use it. Notable bug.
  - Description.
  - Folio ("N/A" if empty).
  - Debit (PKR) and Credit (PKR).
  - Balance (PKR).
  - Payment Notes ("N/A" if empty).
  - **Proof:** if `attachment_path` is set, a blue "Proof" badge with a paperclip linking to `/static/<attachment_path>` in a new tab; otherwise "None".
  - Added By: `created_by_user || "System"`.
  - Actions: Delete.
- Debit and Credit cells get class `positive` when > 0; Balance gets `positive` when ≥ 0, else `negative`. **None of these classes has CSS**, so they do nothing.
- Money is formatted by `formatCurrency`: `Intl.NumberFormat("en-PK",{style:"currency",currency:"PKR",minimumFractionDigits:2})` (`vendor_detail.js:864-870`).
- Description, notes, folio and user are not escaped (XSS risk).
- **Order:** server `ORDER BY date DESC, id DESC` (`vendor_router.py:246`), newest first.
- **Filters:** `start_date` / `end_date` (YYYY-MM-DD, inclusive, applied to `VendorLedger.date`). A bad format returns 400.
  - Clear empties both fields and reloads.
  - Filtering affects the table, the totals and the export.
- Empty: "No ledger entries found". Loading: "Loading ledger entries...". Error: renderError with retry.

**Purchase Orders table** (`vendor_detail.html:353-377`, `vendor_detail.js:397-461`)
- **Columns:**
  - Date (the PO `date`, YYYY-MM-DD).
  - Invoice No.
  - Item Name.
  - Quantity.
  - Rate (PKR) and Amount (PKR), both formatCurrency.
  - Remarks ("N/A" if empty).
  - **Status:** an inline `<select>` with options Ordered / In Transit / Received. The text colour follows the status: received `#2f855a`, in transit `#dd6b20`, ordered `#2b6cb0`.
  - Added By (or "System").
  - Actions: Delete.
- **Order:** `date DESC, id DESC`.
- **Filters:**
  - `start_date` and `end_date` on PO `date`.
  - `invoice_no`: `ILIKE %x%`.
  - The server also supports a `status` filter (`vendor_routes.py:397-419`) that has **no UI**.
- Empty: "No purchase order records found". Loading: "Loading purchase orders...".

### 4. Forms

**Ledger entry modal**
- Title "Add Ledger Entry". There is no edit mode: hidden `#ledgerId` is unused.

| Label | id → FormData key | Type | Required | Default/validation |
|---|---|---|---|---|
| Date * | ledgerDate → date | date | yes | defaults to `new Date().toISOString().split("T")[0]`, the **UTC** date, so before 05:00 Pakistan time it defaults to yesterday (`vendor_detail.js:802-807`) |
| Folio | ledgerFolio → folio | text | no | trimmed; `''` is sent |
| Description * | ledgerDescription → description | text | yes | trimmed; DB String(500) |
| Debit Amount | ledgerDebit → debit | number step 0.01 min 0 | no | `parseFloat || 0` |
| Credit Amount | ledgerCredit → credit | number step 0.01 min 0 | no | `parseFloat || 0` |
| Payment Notes | ledgerPaymentNotes → payment_notes | textarea rows 3, placeholder "Enter payment details, cheque number, bank receipt notes..." | no | trimmed |
| Proof Attachment (Optional) | ledgerAttachment → attachment | file, `accept="image/*,application/pdf"` | no | the only type check is client-side `accept`; no size limit |

- `vendor_id` is appended to the form data.
- **Endpoint:** `POST /api/ledger/add` as multipart/form-data. The backend also accepts JSON (`vendor_routes.py:254-349`).
- **Backend rules:**
  - Required keys: vendor_id, date, description, debit, credit (present and not None).
  - Date format `%Y-%m-%d`.
  - **No check** that debit or credit is non-negative, that at least one is non-zero, or that they are mutually exclusive. Both can be non-zero, and both can be 0.
  - The file is saved by `save_uploaded_file` as `static/uploads/<unix_ts>_<secure_filename>`, and the stored path is `uploads/<name>` (`log_utils.py:14-33`).
  - `created_by_user` is the JWT user's username.
  - Logged as `CREATE_LEDGER`.
  - Returns 201 `{message:'Ledger entry added successfully', entry}`.
- **Success:** toast with `data.message`, the ledger reloads, the modal hides.
- **Error:** generic "Error saving ledger entry. Please try again."

**Purchase order modal**
- Title "Add Purchase Order". There is no edit mode: hidden `#consignmentId` is unused.

| Label | id → JSON key | Type | Required | Notes |
|---|---|---|---|---|
| Date * | consignmentDate → date | date | yes | defaults to today's UTC date |
| Invoice No * | consignmentFormInvoiceNo → invoice_no | text | yes | trimmed |
| Item Name * | consignmentItemName → item_name | text | yes | free text; **not linked to inventory** |
| Quantity * | consignmentQuantity → quantity | number min 1 | yes | `parseInt`, so decimals are truncated |
| Rate * | consignmentRate → rate | number step 0.01 min 0 | yes | `parseFloat` |
| Remarks | consignmentRemarks → remarks | textarea rows 2 | no | `''` → null |
| Status * | consignmentStatus → status | select: ordered (default) / in transit / received | yes | reset to "ordered" each time the modal opens |

- `vendor_id` is included.
- Client-side, JS also checks that all required values are truthy, otherwise "Please fill in all required fields" (`vendor_detail.js:521-524`).
- **Endpoint:** `POST /api/purchase-orders/add` (alias `/api/consignments/add`).
- **Backend:**
  - Required fields are checked with `if not data.get(f)`, so **rate 0 or quantity 0 is rejected** with "rate is required" even though the form allows min 0.
  - `amount = int(quantity) * float(rate)`, computed server-side.
  - Status on add is **not validated**; any string is accepted. The default is 'ordered'.
  - Logged as `CREATE_PO`.
  - Response 201 `{message:'Purchase order record added successfully', consignment: {...}}` (legacy key).
- **Success:** toast, reload, hide, reset. **Error:** generic message.

**Status change**
- The inline select's `change` event sends `PUT /api/purchase-orders/<id>/status` with `{status}`.
- The server allows only `ordered`, `in transit` and `received`, otherwise 400 "Invalid status". It sets `updated_at` and logs `UPDATE_PO_STATUS` with the old and new values.
- **Success:** toast "Purchase order status updated successfully!" and a reload.
- **Failure:** toast "Failed to update status" and a reload, which reverts the select.
- Any transition is allowed, in any direction.

**Deletes** (one shared `#deleteModal`)
- **Ledger:** "Are you sure you want to delete this ledger entry?", then `DELETE /api/ledger/<id>` (logged `DELETE_LEDGER`), then toast "Ledger entry deleted successfully" and a ledger reload.
- **Purchase order:** "Are you sure you want to delete this consignment record?", then `DELETE /api/purchase-orders/<id>` (alias `/api/consignments/<id>`, logged `DELETE_PO`), then "Purchase order deleted successfully".
- **Vendor:** "Are you sure you want to delete this vendor? This will also delete all associated ledger entries and consignment records.", then `DELETE /api/vendors/<id>`, then a redirect to `/vendors`.
- Any delete failure shows the generic "Error deleting item. Please try again."

### 6. Vendor ledger logic
- **Running balance is stored, and computed once, at insert time** (`vendor_routes.py:300-307`):
  - `last = latest entry for vendor ORDER BY date DESC, id DESC`
  - `new_balance = (last.balance or 0) + debit − credit`
  - So debit increases the balance (the amount owed to the vendor) and credit decreases it (payments).
- **Back-dated entries corrupt the chain.** "last" means the latest *date*, not the latest insert. A back-dated entry takes the newest-dated entry's balance plus its own delta, and the balances of entries dated after it are never recomputed.
- **Delete does not recompute** any later balances either (`vendor_routes.py:351-379`).
- **Totals** (`vendor_detail.js:345-363`):
  - Total Debits = Σ debit over the loaded (filtered) rows.
  - Total Credits = Σ credit over the loaded rows.
  - **Closing Balance = `entries[0].balance`**, the stored balance of the newest row in the filtered range, or 0 if there are none.
  - There is no opening balance, and nothing reconciles totals against the balance.
- **Folio:** free text, String(100). No numbering or uniqueness.
- **Payment notes:** free text.
- **Date rules:** any valid date is accepted, past or future. The ledger is filtered and sorted by `date` but displays `created_at`.
- **Period lock:** none. `vendor_routes.py` does not import `period_lock` (`guard_period` and the rest exist in `period_lock.py` but are not applied here), so ledger and PO adds and deletes ignore closed financial months.
- **Delete rules:** any admin or accountant can delete any entry. The attachment file stays on disk.
- **Related (reports, outside this area):** `reports_routes.get_vendor_balances()` computes `SUM(vl.balance)` across *all* rows (`reports_routes.py:400-425`). That adds up running balances rather than taking the latest one, so the dashboard's vendor balances are wrong. Flag this for parity.

### 7. Purchase orders vs consignments
- **They are the same thing.** There is one model, `PurchaseOrder` (table `purchase_orders`). "Consignment" is the old name.
- The old name survives in:
  - route aliases `GET /api/vendors/<id>/consignments`, `POST /api/consignments/add`, `DELETE /api/consignments/<id>`
  - the `consignment` key in the add response
  - DOM ids (`#consignments`, `consignment*`)
  - JS function names
  - delete-modal copy ("consignment record")
  - the vendors page subtitle
- **Statuses:** `ordered` → `in transit` → `received`, freely changeable.
- **Amount:** `quantity × rate`, computed on the server only. `calculateConsignmentAmount()` computes it on the client and throws the result away; it is dead code (`vendor_detail.js:551-560`). No amount preview is shown in the form.
- **No link to inventory receiving.** Marking "received" does not touch Inventory or InventoryTransaction. `item_name` is free text with no part link. No ledger entry is created automatically. There is no edit of a PO beyond its status.

### 8. Excel exports
Both use SheetJS (`libs/xlsx.full.min.js`, loaded in the head). Print: none, and no `@media print` rules exist in any of the three CSS files.

**Ledger export** (`vendor_detail.js:670-736`)
- With no rows loaded: error "No ledger entries available to export".
- **Header row:** Date / Time | Description | Folio | Debit (PKR) | Credit (PKR) | Balance (PKR) | Payment Notes | Proof Attachment URL | Added By.
- **Rows** are the loaded (filtered) entries, **reversed to oldest-first** (a copy, so the screen is untouched).
- **Values:**
  - `created_at || date`
  - description
  - folio or "N/A"
  - debit, credit and balance as raw numbers
  - payment_notes or "N/A"
  - `${location.origin}/${attachment_path}` or "None". **Bug:** this URL is missing `/static/`, so it gives `/uploads/...` while the on-screen link uses `/static/uploads/...`.
  - created_by_user or "System"
- **Column widths:** 20, 30, 10, 15, 15, 15, 35, 45, 15.
- **Sheet:** "Ledger Statement". **File:** `vendor_ledger_<vendorId>_<UTC YYYY-MM-DD>.xlsx`.
- No vendor name or header block and no totals row. Success toast via `showInfo("Ledger exported to Excel successfully!")`.

**Purchase orders export** (`vendor_detail.js:739-799`)
- With no rows: "No purchase order records available to export".
- **Header row:** Date | Invoice No | Item Name | Quantity | Rate (PKR) | Amount (PKR) | Remarks | Status | Added By.
- Rows are in on-screen order (date desc). Remarks default "N/A", status defaults to "ordered", user defaults to "System".
- **Column widths:** 15, 15, 25, 10, 15, 15, 30, 15, 15.
- **Sheet:** "Purchase Orders". **File:** `vendor_purchase_orders_<vendorId>_<UTC date>.xlsx`.
- Success: `showInfo("Purchase orders exported to Excel successfully!")`.

### 9. Client-side calculations
- Total Debits = Σ `parseFloat(debit)`.
- Total Credits = Σ `parseFloat(credit)`.
- Closing = `parseFloat(entries[0].balance)`.
- Ledger payload: `debit = parseFloat(x) || 0`, and the same for credit.
- PO payload: `quantity = parseInt`, `rate = parseFloat`.
- Default dates: `toISOString().split("T")[0]`, which is UTC.
- `formatDate` (UTC → Asia/Karachi) is defined but **unused** on this page.

### 10. Keyboard, autofocus, polling
- Only the Cmd/Ctrl+K palette (shared). No Enter-to-filter, no Esc, no backdrop close.
- No autofocus. No polling.

### 11. Persisted state
- The vendor id comes from the path.
- Edit goes to `/vendors?edit=<id>` (unhandled).
- Delete redirects to `/vendors`. The Back button goes to `/vendors`.
- No local or session storage of its own.

### 12. Quirks, dead code, bugs
1. The Date column shows the UTC `created_at`, not the transaction date.
2. Running balances break on back-dated inserts and on deletes.
3. No period lock.
4. Export proof URL is missing `/static/`.
5. Edit vendor goes to an unhandled `?edit=`.
6. Vendor info, ledger and PO cells are not HTML-escaped.
7. `positive`/`negative`/`currency` classes have no CSS.
8. `calculateConsignmentAmount`, `openDeleteModal()` (`vendor_detail.js:130-138`, never called) and `formatDate` are dead code.
9. Hidden `ledgerId` and `consignmentId` fields exist, and the HTML comments say "Add/Edit", but there is no edit for ledger entries or POs.
10. `notification-utils.js` is included twice (`vendor_detail.html:12` and `:593`).
11. Rate or quantity of 0 is rejected by the server despite min=0 in the form.
12. PO status on add is not validated.
13. Relative `login.html` redirects break under `/vendors/<id>`.
14. The server-side 404 for a missing vendor comes before auth.
15. The UTC "today" default date is wrong before 05:00 PKT.
16. The upload has no server-side type or size validation.
17. Deleting an entry leaves its attachment file on disk.
18. The PO status filter has no UI.

### CSS behaviour (all three pages)
- **car.css:**
  - Tabs `.tab-content{display:none}`, `.active` shows. `.modal.active` shows.
  - At ≤768px: actions and tabs stack, action buttons stack full-width, tables get min-width 600px with horizontal scroll, the back-btn label is hidden.
  - At ≤480px: header subtitle hidden.
  - `prefers-reduced-motion` disables animations.
  - `:focus-visible` outlines.
  - Customer-cars modal table min-width 900px.
- **vendors.css:** `.modal.show`. Table min-width 860px with horizontal scroll. At ≤768px the controls stack and form rows go to one column.
- **vendor_detail.css:**
  - `.tab-pane{display:none}`, `.active` shows.
  - Table min-width 940px with horizontal scroll.
  - At ≤768px: tabs, tab headers, filters, totals and form rows stack to one column; action buttons stack.
  - `.input-fields:invalid` gets a red border, so empty required fields show red as soon as the form opens.
- No print rules anywhere.

---

### Endpoints used

| METHOD | path | page/action |
|---|---|---|
| GET | /car.html | car page (app.py:192) |
| GET | /api/cars | car.html: load cars table (only cars with a customer) |
| POST | /api/cars | car.html: add car (409 on duplicate VIN) |
| PUT | /api/cars/<id> | car.html: edit car / transfer owner |
| DELETE | /api/cars/<id> | car.html: delete car |
| GET | /api/cars/search?q= | car.html: car search (suggestions ignored) |
| GET | /api/cars/customer/<customer_id> | car.html: View Cars modal |
| GET | /api/customers | car.html: customers table + car-modal dropdown |
| POST | /api/customers | car.html: add customer (409 on duplicate name+phone+address) |
| PUT | /api/customers/<id> | car.html: edit customer |
| DELETE | /api/customers/<id> | car.html: delete customer (cascades cars) |
| GET | /api/customers/search?q= | car.html: customer search (suggestions ignored) |
| GET | /api/cars/<id> | exists, unused by these pages |
| GET | /vendors | vendors page (vendor_routes.py:18) |
| GET | /vendors/<id> | vendor detail page (404 if vendor missing) |
| GET | /api/vendors | vendors.html: list (`?search=` supported, unused) |
| POST | /api/vendors | vendors.html: add vendor (409 on duplicate name+company+phone) |
| PUT | /api/vendors/<id> | vendors.html: edit vendor |
| DELETE | /api/vendors/<id> | vendors.html and vendor_detail.html: delete vendor (cascade) |
| GET | /api/vendors/<id> | vendor_detail.html: vendor info |
| GET | /api/vendors/<id>/ledger?start_date&end_date | vendor_detail.html: ledger tab |
| POST | /api/ledger/add (multipart) | vendor_detail.html: add ledger entry + proof |
| DELETE | /api/ledger/<id> | vendor_detail.html: delete ledger entry |
| GET | /api/vendors/<id>/purchase-orders?start_date&end_date&invoice_no[&status] | vendor_detail.html: PO tab (alias /consignments) |
| POST | /api/purchase-orders/add | vendor_detail.html: add PO (alias /api/consignments/add) |
| PUT | /api/purchase-orders/<id>/status | vendor_detail.html: inline status change |
| DELETE | /api/purchase-orders/<id> | vendor_detail.html: delete PO (alias /api/consignments/<id>) |
| GET | /static/uploads/<file> | vendor_detail.html: Proof link |

No endpoint is called that does not exist. The broken pieces are the unhandled `/vendors?edit=<id>` param, the export URL `/uploads/<file>` (missing `/static`), and relative `login.html` redirects resolving to `/vendors/login.html`.

### Files read
Read in full:
- frontend/car.html (429)
- frontend/vendors.html (245)
- frontend/vendor_detail.html (599)
- static/js/car.js (627)
- static/js/vendors.js (348)
- static/js/vendor_detail.js (870)
- static/js/phone-formatter.js (167)
- car_routes.py (698)
- vendor_routes.py (559)
- document_links.py (115)
- search_suggestions.py (98)

Read in part:
- static/css/car.css (915): responsive, a11y and modal/tab sections, plus a behaviour grep over the rest
- static/css/vendors.css (822): responsive, modal and table sections, plus a behaviour grep
- static/css/vendor_detail.css (940): table, form, totals, modal and responsive sections, plus a behaviour grep
- models.py (875): Customer, Car, Vendor, VendorLedger, PurchaseOrder, FinancialPeriod, and the Invoice/RepairOrder FK sections
- jwt_auth.py (231): permissions, path map, decorators
- app.py (371): blueprint registration, /car.html route, static
- period_lock.py (226): function list, to confirm it is not applied to vendor routes
- log_utils.py (102): save_uploaded_file
- reports_routes.py (671): get_vendor_balances
- static/js/app-shell.js (459): nav, ACTIONS, handleNewParam, slimHeader, unsaved guard, boot
- static/js/api-helper.js (578): request, performRequest, responseError, verbs
- static/js/auth_jwt.js (315): SUB_PAGE_PERMISSIONS, canAccessPage, requireAuth, requirePageAccess
- static/js/notification-utils.js (132): showSuccess, showError, showInfo signatures
- static/css/app-shell.css (630): back-btn hiding rule
- static/css/theme.css (1189): .customer-code rule location only

static/js/libs/xlsx.full.min.js is a vendored library; only its usage was reviewed, not the file.
