# Inventory (Stock) Management — Feature Inventory

Shared modules (auth_jwt, app-shell, api-helper, theme, notification-utils) are covered elsewhere. This section only notes how these pages use them.

**Backend access model (applies to every page below).** `inventory_bp` is mounted at `/api` (app.py:78).
- **Reads:** every inventory GET endpoint uses `@login_required`, so any active logged-in user can call it, whatever their role or permissions.
- **Writes:** POST `/inventory`, PUT/DELETE `/inventory/<id>`, `receive`, `restock` and `deduct-items` use `@role_required(['admin','inventory_manager'])`. `role_required` then goes through `has_configured_permission` (jwt_auth.py:88-111):
  - `admin` is always allowed.
  - If the `RolePermission` table has any rows, a role is allowed when it holds the permission `inventory` (path prefix map, jwt_auth.py:41).
  - Otherwise the fallback role list applies.
- **Default role permissions:** `inventory` belongs to admin and inventory_manager only (jwt_auth.py:24-35). `/api/settings/categories` GET is `login_required`; category writes are `role_required(['admin','inventory_manager'])` under permission `settings`.
- **Login landing page:** inventory_manager users land on `inventory.html` after login (auth_jwt.js:276).

---

## inventory.html — Inventory Management

### 1. Purpose, URL, access
- **Purpose:** list, add, edit and delete stock items; receive stock by barcode, part number or product search; show the low-stock view; export Excel reports and per-item ledgers.
- **URL:** `/inventory.html` (app.py:177).
- **Page guard:** `auth.requirePageAccess("inventory")` (inventory.html:460-465). If permissions are not cached yet, the page initialises and enforcement runs after `auth.ready`. A user without access gets `alert("You do not have permission…")` and is redirected to their role's home.
- **Actions in the UI:** no buttons are hidden by role. All actions are shown to anyone who passes the page guard, and the server enforces the write roles above.
- **Sidebar and command palette (app-shell):**
  - Nav entry "Inventory" (app-shell.js:71).
  - Palette action "Add inventory item" goes to `/inventory.html?new=1`. On `load`, app-shell's `handleNewParam` calls `window.openAddModal()` (app-shell.js:110, 361-370).
  - app-shell tags `.top-header` as `page-header`, and the redundant chrome (Back button and so on) is hidden by CSS.

### 2. Layout
- **Header:** logo, h1 "Inventory Management", subtitle "Manage your product inventory and stock levels", and a Back link `#back-btn` (href set in JS, see §11).
- **Controls row, left side (`.controls-left`):**
  1. **Add New Item** → `openAddModal()`
  2. **Receive Stock** → `openRestockModal()`
  3. **Repair Orders** → `repair-orders-management.html?from=inventory`
  4. **Low Stock Items** → `toggleLowStockView()`
  5. **Transaction History** → `inventory-history.html`
  6. **Print Sheet** → `openPrintSheet()`. Despite the label, this exports the complete inventory to Excel; nothing is printed.
- **Controls row, right side:** `#search-input` (placeholder "Search inventory...") plus a **Search** button → `searchInventory()`.
- **Low stock section `#low-stock-section`** (hidden by default):
  - "Export Low Stock" button → `exportLowStockReportXlsx()`.
  - "URGENT - Negative Stock Items" panel `#urgent-grid` (pulsing red).
  - "Low Stock Items — Items that need to be reordered" panel `#low-stock-grid`.
- **Main grid:** `#inventory-grid`, with collapsible category sections.
- **Modals:** `#item-modal` (Add/Edit) and `#restock-modal` (Receive Stock).
- **Footer:** "© 2025 GermanATO. All rights reserved."
- **No stats cards** on this page. `/api/inventory/stats` exists but no frontend uses it.

### 3. Item list
**Load sequence** (`loadInventory`, inventory.js:175-219):
- On DOMContentLoaded: `loadInventory()`, `loadCategories()`, `setupEventListeners()`, `setupPagination()`.
- With no search term:
  1. `ensureCategoryList()`: GET `/api/inventory/categories` returns the distinct `Inventory.category` values, sorted.
  2. These are merged after `DEFAULT_CATEGORY_ORDER = ["parts","tools","fluids","accessories","other"]` (inventory.js:13, 147-172).
  3. In parallel, one GET `/api/inventory/by-category?page=1&per_page=50&search=&category=<cat>` per category.
  4. `renderInventory()` runs once all of them return.
- **Busy guard:** `isLoading` makes `loadInventory` return immediately while a load is in flight. A search typed during a load is silently dropped (bug).
- **Spinner:** `PerformanceUtils.showLoading("inventory-grid","Loading inventory...")`.

**Grouping and sections:**
- One `.category-wrapper` per category that has items, **collapsed by default** (inventory.js:527).
- Header shows an icon, a display name and a count.
- Clicking the header calls `toggleCategory(cat)`, which toggles `.collapsed` and the ▶/▼ icon.
- Display names: parts→"Auto Parts", tools→"Tools", fluids→"Fluids & Lubricants", accessories→"Accessories", other→"Other". Any other category shows its raw name (inventory.js:726-735).
- Icons are empty strings for the default categories (the emoji were stripped). Other categories get 📦 (inventory.js:827-836).
- Count text is `"N item(s)"`, plus `" (showing M)"` when more pages exist (inventory.js:620-623, 760-763).
- Categories with zero items are not rendered.

**Per-category pagination:**
- 50 items per page. A **Show More** button appears when `has_next`.
- `showMoreItems` loads `page+1` using the current search box value and appends the cards with a staggered `animationDelay` of `index*0.1s`. The button reads "Loading..." and is disabled while loading.
- `setupPagination()` looks for `.inventory-container`, which does not exist. Global pagination is therefore never rendered, and `updatePaginationControls` is dead code (inventory.js:338-396).

**Sorting:**
- by-category: no `ORDER BY`, so database order (unspecified).
- search-grouped: `ORDER BY name`.
- Category order: the defaults first, then API categories alphabetically, then any new categories appended.

**Item card** (`createInventoryItemElement`, inventory.js:632-723):
- Image `/static/<image_path>`, hidden on error; 📦 placeholder when there is no image.
- `part_number`, or `Product #<id>` if there is none.
- Name and category display name.
- `barcode || manufacturer_part_number`, shown in a second `.item-category` div.
- "Today · <movement_date>". This is the business date, computed in Asia/Karachi.
- Detail rows:
  - Opening Qty
  - Purchases (issue in)
  - Sales (issue out)
  - Adjustments: signed, `+` prefix when positive, green or red class.
  - Closing Qty
  - Location, only if set.
- Description paragraph, if set.
- Actions: **Excel** (`exportItemLedgerXlsx(id)`), **Edit** (`editItem(id)`), **Delete** (`deleteItem(id)`).
- Item data is injected as unescaped HTML (XSS risk for name, description and location).

**Low-stock highlighting on cards:**
- Closing Qty gets the `.low-stock` class (red pill) when `closingQuantity <= (item.reorder_level || 5)`.
- A reorder level of 0 is therefore treated as 5 (inventory.js:687).

**Day movement fields** (server, inventory_routes.py:130-186):
- Business day = today in `Asia/Karachi`. Bounds are converted to naive UTC.
- Today's transactions for the item:
  - `adjustment` rows: their signed quantity adds to `adjustments_quantity`.
  - Other rows: positive quantity adds to `purchases_quantity`; negative quantity adds `abs(qty)` to `sales_quantity`.
- `opening_quantity = quantity − purchases + sales − adjustments`
- `closing_quantity = quantity`

**Search (main box):**
- `keyup`: Enter runs `searchInventory()` immediately. Any other key (arrows and Shift included) debounces 500 ms (inventory.js:112-127).
- `searchInventory()` resets every category's pagination, then calls `loadInventory(1, term)`.
- **Non-empty term:** GET `/api/inventory/search-grouped?q=<term>` (one request) returns `results` (category → items), `total_count`, `returned_count`, `truncated` and `category_count`.
  - The server limit defaults to 200 (max 500 via `limit`). The client does not send a limit.
  - Matching is case-insensitive substring (`ilike %q%`) on part_number, barcode, manufacturer_part_number, name, description, location and category.
  - Code normalisation (`code_matches`, inventory_routes.py:292-304): strip every non-alphanumeric character from the term; on the DB side, remove spaces, dashes and dots from `manufacturer_part_number` and `barcode`; then `ilike %stripped%`. Example: "11-427 583.220" matches "11427583220".
  - **Truncated results:** the notice reads "Showing the first X of Y matches. Refine your search to narrow it down." (inventory.js:274-276).
  - **No matches** (`total_count === 0`): the server adds `did_you_mean` and `closest` from `suggestions_for(query, all inventory names)`. `APIHelper.renderNoMatches` paints "No matches for “q”", "Did you mean <btn>?" and "Closest on file: <btns>". Clicking one sets the search box and reruns `loadInventory(1, term)`.
  - Search results get no Show More.
- **Empty term:** full category reload.
- **Search field differences between endpoints:**
  - by-category also searches `location` and `category`.
  - `/api/inventory` (list) does not search location or category.
- **Suggestions while typing** (autocomplete): none in the main search box.

**Empty and error states:**
- No items in any category: "No inventory items found / Click "Add New Item" to get started" (inventory.js:486-493).
- Load error: "Failed to load inventory. Please try again." with a Retry button. The callback is an arrow function, so `onclick="${fn.name}()"` renders `onclick="()"` and Retry is broken.

**Response caching (quirk):**
- `PerformanceUtils.fetchWithRetry` is used for the by-category and search-grouped GETs (performance-utils.js:33-57).
- It caches identical URLs for **5 minutes** in memory and retries 3 times with 1 s and 2 s back-off, including on 4xx.
- After an add, edit or delete, a later full reload or a repeated identical search inside 5 minutes shows **stale** data until a page refresh.

### 4. Forms

#### Add / Edit Item (`#item-form`, multipart FormData)
| Label | name / id | Type | Required | Default | Notes |
|---|---|---|---|---|---|
| Item Name | `name` / item-name | text | yes (HTML + server) | — | server: must be non-blank after trim |
| Category | `category` / item-category | select | yes (HTML + server) | "Select Category" | options from `/api/settings/categories` (all rows, **inactive included**; option text = raw name). Falls back to `/api/inventory/categories`, then to the in-memory/default list (inventory.js:859-921). The previous selection is restored if still present. On edit, a missing value is added as `"<cat> (Legacy)"`. |
| Barcode | `barcode` / item-barcode | text, autocomplete off | no | — | placeholder "Scan or enter manufacturer barcode". Server trims, empty→NULL, must be unique. |
| Manufacturer Part Number | `manufacturer_part_number` | text | no | — | placeholder "Used when no barcode exists". Trimmed, empty→NULL, must be unique. |
| Quantity | `quantity` | number min 0 | yes | — | server: int, ≥0 |
| Reorder Level | `reorder_level` | number min 0 | yes | 5 | server: int ≥0, default 5 |
| Description | `description` | textarea rows 3 | no | — | empty → NULL |
| Storage Location | `location` | text | no | — | placeholder "e.g., Shelf A1, Warehouse B" |
| Item Image | `image` | file accept image/* | no | — | help text "JPG, PNG, GIF - Max 5MB". Preview via FileReader. |
| (hidden) | `remove_image` | hidden | — | "false" | set to "true" by the × on the current image |

**Not exposed by the forms or the API:**
- `price`: the server always sets 0.0 on create, and it is not returned by `inventory_item_to_dict`.
- `reorder_quantity`: model default 10; not returned and not editable.

**Part number generation** (models.py:177-200, Inventory `__init__`):
- Auto-assigned as `PN` + the next integer, zero-padded to 3 digits (PN001 … PN999, PN1000…).
- Every part_number starting with `PN` and a numeric suffix is scanned for the maximum numeric value (deliberately not SQL MAX), then incremented until a free value is found.
- Not editable in the UI. Column is `String(20)`, unique, not null.

**Duplicate detection** (server only, `ensure_unique_inventory_codes`, inventory_routes.py:352-369):
- Exact match after trim, excluding the item's own id on edit.
- Errors: "Barcode X is already assigned to another inventory item" and "Manufacturer part number X is already assigned to another inventory item" (400).
- DB unique constraints back this up. `inventory_database_error_message` maps IntegrityError and missing-column errors to friendly text, including "Run: alembic upgrade head".
- Uniqueness ignores the normalisation used by search, so "11-427" and "11427" can coexist.
- No client-side duplicate check.

**Create:**
- `openAddModal()`: resets the form, reloads categories, hides the image preview, shows the modal.
- Submit: POST `/api/inventory` (FormData) returns 201 `{message, item}`.
- Server: if `request.form` is present, the image is saved to `static/uploads/<uuid4>.<ext>`. Allowed extensions: png, jpg, jpeg, gif, webp; anything else returns 400 "Invalid file type. Only image files are allowed.". `MAX_FILE_SIZE` (5 MB) is defined but **never enforced**.
- Validation errors return 400 `{error:"Validation failed", details:[…]}`. APIHelper turns this into an alert of the error plus "Details:" lines.
- Client: the new item is unshifted into its category (a new category slot is created if needed) and the category is re-rendered.

**Edit:**
- `editItem(id)` first requires the item to be present in the loaded `categoryPagination`. If it is not (for example, clicking Edit on a low-stock card whose item is beyond page 1 of its category), it logs to the console and does nothing (inventory.js:949-958).
- It then GETs `/api/inventory/<id>` for fresh data.
- Fills the fields. Reorder level is filled as `item.reorder_level || 5`, so a reorder level of 0 is shown as 5 and would be saved as 5 (bug).
- Shows the current image if one exists.
- Submit: PUT `/api/inventory/<id>` (FormData) returns `{message,item}`.
- Server image rules: `remove_image=='true'` takes priority (the file is deleted from disk and the column set NULL). Otherwise a new upload replaces the old file and deletes it.
- **Quantity change:** if quantity changed, the server logs an `adjustment` transaction:
  - quantity = new − old
  - reference_description "Manual quantity adjustment - <name>"
  - notes "Quantity changed from X to Y"
  - created_by = current user
- **Negative stock:** the HTML `min="0"` blocks saving any edit of an item whose current stock is negative until the quantity is changed to 0 or more.
- Client after edit: the item is removed from its old category and unshifted into the new one (counts adjusted), and both categories are re-rendered.

**After any re-render** (add, edit, delete, receive): `renderCategorySection` deletes the wrapper and **appends it at the bottom of the grid, collapsed**. The category the user was working in jumps to the end and closes (quirk).

**Closing the modal:**
- `closeModal()` hides it and resets the image state.
- Clicking the backdrop also closes it. Esc does not.
- Success has no message; the modal just closes.
- Error: `alert(error.message || "Error saving item. Please try again.")`.

**Delete:**
- `confirm("Are you sure you want to delete this item?")`, then DELETE `/api/inventory/<id>`.
- Server:
  - Sets `RepairOrderPart.inventory_id = NULL` for linked parts.
  - **Hard-deletes every InventoryTransaction for the item** (history lost).
  - Deletes the item. The image file is not removed.
- Client: splices the item out, decrements `totalItems` and re-renders.
- Failure: "Failed to delete item. Please try again."
- If the delete was done from the low-stock view, the low-stock grid is not refreshed.

#### Receive Stock modal (`#restock-form`)
| Label | id / name | Type | Notes |
|---|---|---|---|
| Scan Barcode / Part Number | `restock-code` / `code` | text, autocomplete off | placeholder "Scan barcode or enter manufacturer part number". Status line `#restock-code-status`. |
| Or Select Product | `restock-product-search` (visible) + hidden `restock-product` / `product_id` | searchable dropdown | |
| Received Quantity * | `restock-quantity` / `quantity` | number min 1, required | |
| Notes | `restock-notes` / `notes` | textarea | placeholder mentions supplier, batch number and quality notes |

**Code lookup** (`handleRestockCodeLookup`, inventory.js:1130-1155):
- Triggered by Enter in the code field (keydown, `preventDefault` so the form is not submitted) or by its `change` event (blur).
- Status "Looking up item..." → GET `/api/inventory/lookup?code=<code>`.
- Server matching (inventory_routes.py:341-350): trim, then **exact, case-sensitive** match in this order: `barcode`, then `manufacturer_part_number`, then `part_number`. No space or dash normalisation.
- Hit: `selectProduct()` fills the product box and hidden id; status "Matched: <name>".
- 404: clears the product fields; status "No matching inventory item found". The GET is not `silent`, so APIHelper's global error banner also shows.

**Product search dropdown:**
- `input` with fewer than 2 characters: nothing happens (the previous dropdown stays). Empty: dropdown hidden.
- Otherwise, 300 ms debounce → "Searching..." → GET `/api/inventory/search?q=<term>`. Server limit is 200; the endpoint computes `total_count` but does not return it, so there is no truncation hint here.
- Each row shows the name, then "Current Stock: <closing_quantity ?? quantity> | Category: … | Part #: … | Barcode: … | MPN: …".
- Click selects the item. Focus shows the dropdown; blur hides it after 200 ms.
- Empty results: "No products found". Error: "Error searching items".

**Submit** (`handleRestockSubmit`, inventory.js:1296-1384):
- Needs a code or a product, plus a quantity. Otherwise: alert "Please scan a code or select a product, then enter the quantity received." A quantity of 0 or less: alert "Quantity must be greater than 0."
- **If the code field is non-empty**, it wins over the selected product: POST `/api/inventory/receive` `{code, quantity:int, notes}`.
  - Server: same exact lookup. 404 "Inventory item not found for scanned code".
  - quantity += n, and `updated_at` is set.
  - Logs a `received` transaction: reference "Inventory received by code scan - <name>", notes = given notes or `"Scanned code: <code>"`.
- **Otherwise:** POST `/api/inventory/restock` `{product_id:int, quantity, notes}`.
  - Server logs `received` with reference "Inventory restock - <name>" and notes = notes.
- Both return `{product_id, product_name, quantity_added, old_quantity, new_quantity, item, …}`.
- Button shows "Receiving..." and is disabled while the request runs.
- Success alert: "Successfully received N units of <name>.\n\nOld quantity: X\nNew quantity: Y". The modal closes (form reset), and the item is replaced with `result.item` in its category, which is re-rendered.
- Any failure: generic alert "Error receiving stock. Please check your connection and try again." The server's error message is not shown.
- Dead branch: `else { await response.json() }` references an undefined `response` (inventory.js:1370-1375).

**Deduct / adjust from this page:** there is no standalone deduct or adjust form. Adjustments happen only by editing the quantity. `/api/inventory/check-stock` and `/deduct-items` are used by invoiceShared.js (invoice flow), not by these pages.
- check-stock matches by part_number, then name ilike, then description ilike.
- deduct-items matches by inventory_id, or part_number, then name ilike, then description ilike, then exact name. It allows negative stock and logs `issue_out` with "Manual deduction - <product_name>".

### 5. Barcode scanner support
- No keystroke-timing detection. Everything relies on the scanner sending a trailing Enter, or on the field's `change` event.
- **Receive modal code field:** Enter or change triggers an exact-code lookup. This is the "quick receive" flow: scan, type a quantity, press Receive. Submitting with a code goes straight to `/receive`, even if the lookup failed (the server then returns 404).
- **Main search box:** a scan plus Enter runs search-grouped immediately, which normalises codes.
- **Add/Edit barcode field:** no Enter handling, so a scanner's Enter **submits the item form** (quirk).
- No autofocus on the code field when the modal opens.

### 6. Low stock view (on this page)
- `toggleLowStockView()`:
  - Shows `#low-stock-section` and hides the grid.
  - Button becomes "📦 All Items" with a green inline gradient. Toggling back sets the text "<span></span> Low Stock Items" and a red inline gradient, and the SVG icon is lost.
  - On return the grid is restored with `display:grid`; the CSS uses flex (minor).
- Data: GET `/api/inventory/low-stock`.
  - Server returns items with `quantity <= reorder_level`, ordered by id.
  - `quantity < 0` goes to `urgent_items` (`stock_status:'URGENT - Negative Stock'`, `urgency_level:'critical'`).
  - `== 0` goes to `low_stock_items` as 'Out of Stock'/'high'; the rest are 'Low Stock'/'medium'.
- Fallback on failure: filters the `inventoryItems` array. That array is only filled by adds in this session, so the fallback is effectively dead.
- Cards (`createLowStockItemElement`):
  - Name, category, `part_number || "No Part Number"`, "Today · date", status badge.
  - Badge: urgent shows `stock_status`; closing 0 shows "Out of Stock"; otherwise "Low Stock".
  - Rows: Opening, Purchases, Sales, Closing, Location. Adjustments are not shown here.
  - Buttons: Excel, Edit Item, Delete.
- Empty states: "No Urgent Items! / No items with negative stock levels." and "🎉 No Low Stock Items! / All inventory items are above their reorder levels."
- No reorder-quantity suggestion is shown. The `.reorder-info` CSS exists but is unused.

### 8. Excel exports on this page (SheetJS `static/js/libs/xlsx.full.min.js`). No import.
**(a) Per-item ledger** — Excel button on a card: GET `/api/inventory/<id>/ledger` (inventory.js:1784-1936).
- **Sheet "Daily In-Out"** — columns Date, Opening, In (Purchases), Out (Sales), Adjustments, Closing.
  - One row per consecutive business day from the first transaction date through today, including days with no movement.
  - Server algorithm (inventory_routes.py:189-289):
    - start = `quantity − Σ(all txn quantities)`
    - per day, opening = running total
    - adjustments: signed sum of adjustment rows
    - in/out: from non-adjustment rows
    - closing = running total
  - With no transactions: a single row for today.
- **Sheet "Transactions"** — columns Date, Date Time (Asia/Karachi `YYYY-MM-DD HH:MM:SS`), Type, In, Out, Previous Qty, New Qty, Reference, Notes, Repair Order. Adjustments put 0 in In and Out. With no transactions: a placeholder row "No transactions recorded".
- **Sheet "Summary"** — rows:
  - "GermanATO Item Stock Ledger"
  - Item Name, Part Number, Barcode, Manufacturer Part Number
  - Business Date
  - Today Opening, Today Purchases (In), Today Sales (Out), Today Adjustments, Today Closing
  - The note "Each day's closing becomes the next day's opening. Card values are for today only."
  - "Monthly Summary Breakdown", with header Month | Total Received (In) | Total Issued (Out) | Total Adjustments and one row per `YYYY-MM`, summed from the daily rows.
- Column widths are set.
- **Filename:** `inventory-ledger-<part_number|name|item-<id>>-<movement_date>.xlsx`. The name part is sanitised: trim, `[\\/:*?"<>|]+`→`-`, whitespace→`-`, max 60 characters.
- Error: alert "Could not export this item's Excel ledger. Please try again."

**(b) Complete inventory** — "Print Sheet" button: pages through GET `/api/inventory?page=N&per_page=200` until `has_next` is false.
- **Sheet "Inventory"** — columns: Part Number, Barcode, Manufacturer Part Number, Item Name, Category (display name), Business Date, Opening Qty, Purchases (issue in), Sales (issue out), Closing Qty, Location, Reorder Level, Stock Status, Description, Created At, Updated At.
  - Adjustments are not exported.
  - Stock Status: closing < 0 "Negative Stock"; = 0 "Out of Stock"; ≤ reorder_level (`||0`) "Low Stock"; otherwise "In Stock".
- **Sheet "Summary"** — "GermanATO Complete Inventory Report", Generated At (`toLocaleString`), Total Items, and Low Stock Items = count where closing ≤ reorder_level.
- **Filename:** `complete-inventory-report-YYYY-MM-DD.xlsx` (UTC date from `toISOString`).
- The button shows "Exporting..." and is disabled while running. The selector `.print-btn` matches the first such element, which is the Print Sheet button.
- Error: "Could not export the inventory report. Please try again."

**(c) Low stock** — "Export Low Stock" button: GET `/api/inventory/low-stock`, urgent items first, then low-stock items.
- Same 16 columns as (b), in a single sheet "Low Stock".
- **Filename:** `low-stock-inventory-report-YYYY-MM-DD.xlsx`.
- Error: "Could not export the low stock report. Please try again."

### 9. Client-side calculations
- **Card low-stock flag:** `closing <= (reorder_level || 5)`.
- **Stock status for exports:** see §8(b) (uses `reorder_level || 0`).
- **Monthly ledger summary:** sums of the daily rows by `date.substring(0,7)`.
- **After receive without `result.item`:** `purchases += quantity_added`, `quantity = closing = new_quantity`.
- No stock value or money totals on this page; price is always 0 and is not returned.

### 10. Keyboard, focus, polling
- Enter in the main search box searches. Enter in the restock code field looks up the code.
- Ctrl/Cmd+K opens the app-shell command palette.
- Clicking a modal backdrop closes it. No Esc handler. No autofocus. No polling or auto-refresh.

### 11. Persisted state and navigation
- **Back button href:** `?from=` param, else `localStorage.lastPage`, else "home". Values map: `admin`→admin.html, `home`→home.html, `invoiceSystem`→invoiceSystem.html, anything else→home.html. The page then sets `localStorage.lastPage="inventory"` (inventory.js:72-91).
- **`?new=1`:** handled by app-shell, which opens the Add modal.
- **Outbound links:** `repair-orders-management.html?from=inventory` and `inventory-history.html`.
- **Unsaved-changes guard (app-shell):** typing in item-form fields, and in `restock-code` (its id contains neither "search" nor "filter"), marks the page dirty and triggers beforeunload. A successful write fires `api:saved`, which clears it.
- No sessionStorage use, so nothing is written for low-stock-print.html.

### 12. Quirks, bugs and dead code (inventory page)
- Dead code: `loadSampleData()`, `groupItemsByCategory()`, `populateRestockProductDropdown()`, `setupPagination()` / `updatePaginationControls()` (target container missing), the `inventoryItems` array (fallback only), `FallbackUtils` (unused while performance-utils loads).
- Two search timers: a global `searchTimeout` (for restock) and a local one in `setupEventListeners`.
- Category icon map is all empty strings.
- Collapse and reorder on every re-render (see §4).
- The 5-minute GET cache causes stale lists (see §3).
- `isLoading` drops concurrent searches.
- Retry button is broken.
- Item data rendered as raw HTML (XSS).
- Reorder level 0 is coerced to 5 in both the card flag and the edit form.
- Negative-stock items cannot be edited without changing the quantity.
- Receive errors hide the server's message.
- Deleting an item wipes its transaction history.
- The image size limit is not enforced server-side.
- Inactive settings categories still appear in the dropdown.

---

## inventory-history.html — Inventory Transaction History

### 1. Purpose, URL, access
- **Purpose:** read-only log of all stock movements.
- **URL:** `/inventory-history.html` (app.py:183). Reached via the "Transaction History" button on inventory.html.
- **Page guard:** this page does **not** call `auth.requirePageAccess`. Any authenticated user can open it, and the API (`login_required`) serves any logged-in user. An unauthenticated user gets 401 from the API, then the refresh/login redirect in APIHelper.
- Not in the sidebar nav.

### 2. Layout
- Header: "Inventory Transaction History" / "Track all inventory movements and adjustments", and "Back to Inventory" → inventory.html.
- Filter panel.
- Four summary cards:
  - **Issue Out**, **Received**, **Adjustments**: counts of that type **on the current page only**.
  - **Total Transactions**: `pagination.total` across all pages (inconsistent with the other three).
- Table, loading state, empty state, pagination bar.

### 3. Filters
| Label | id | Sent as | Server behaviour |
|---|---|---|---|
| From Date | date-from (date) | `date_from=YYYY-MM-DD` | `created_at >= date 00:00:00` |
| To Date | date-to (date) | `date_to` | `created_at <= date 23:59:59` |
| Transaction Type | transaction-type select: All / Issue Out(`issue_out`) / Received(`received`) / Adjustment(`adjustment`) | `transaction_type` | validated against these three values (400 otherwise) |
| Inventory Item | inventory-search text, "Search by name or part number..." | `search` | **IGNORED by the backend** (`get_inventory_transactions_route` never reads `search`). This filter does nothing. |
| Repair Order ID | repair-order-search number | `repair_order_id` | exact match |

- **Default dates:** From = today − 30 days, To = today, both via `toISOString()` (UTC date; in Pakistan, between 00:00 and 05:00 local time the UTC date is still the previous day).
- **Timezone mismatch:** the date bounds are naive and compared against `created_at` stored in naive UTC. Local (PKT, UTC+5) days are off by 5 hours.
- **Apply Filters:** button, or Enter (`keypress`) in the item or RO field. Resets to page 1.
- **Clear:** empties **all** fields, dates included (so all time), and reloads.
- Not supported by this page: the `inventory_id` filter (API supports it, UI doesn't send it).

### 4. Table columns (`createTransactionRow`, inventoryHistory.js:120-155)
1. **ID:** `#<id>`.
2. **Date & Time:** the server string "YYYY-MM-DD HH:MM:SS" is treated as UTC (adds `T` and `Z`) and shown in browser local time. Date as `en-GB` "DD Mon YYYY"; time as `en-GB` hh:mm with am/pm.
3. **Inventory Item:** `inventory_name` (or "Unknown Item") and `inventory_part_number`.
4. **Type:** badge "Issue Out" (red, down arrow), "Received" (green, up arrow), "Adjustment" (amber). An unknown type shows its raw value.
5. **Quantity:** header says Quantity, but the value is **`previous_quantity`** (tooltip "Quantity before this transaction").
6. **Stock Change:** signed `quantity`. `issue_out` or negative is red; `received` or positive is green with a `+`; 0 is neutral.
7. **Total:** `new_quantity` (tooltip "Quantity after this transaction").
8. **Repair Order:** link "RO #<id>" → `repair-orders-management.html?id=<id>`. repairOrdersManagement.js does not read `id`, so this lands on the unfiltered list. "-" when there is no RO.
9. **Description:** `reference_description` (or "-"), single line with ellipsis at max-width 180px, full text in the tooltip. Plus `notes` truncated to 30 characters + "...", full notes in the tooltip.

- Row class `transaction-row <type>`: colored left border by type.
- `created_by_username` is returned by the API but not shown.
- **Links to source documents:** only to the repair order. There are no invoice links; transactions carry no invoice id.

**Transaction types** (inventory_transaction_utils.py):
- **issue_out:** quantity stored as negative.
  - Default reference "Issued out for Repair Order #X", or "Manual inventory deduction".
  - Created by `/deduct-items` ("Manual deduction - <name>") and by repair-order flows.
- **received:** quantity stored as positive.
  - Default reference "Restored from Repair Order #X deletion", or "Inventory restock".
  - Created by `/restock` ("Inventory restock - <name>") and `/receive` ("Inventory received by code scan - <name>").
- **adjustment:** signed net change.
  - Default reference "Adjustment from Repair Order #X edit", or "Manual quantity adjustment".
  - Created by an inventory edit that changes quantity ("Manual quantity adjustment - <name>").
- Each row stores `previous_quantity`, `new_quantity`, `created_by` and `created_at` (UTC). The logging helpers never commit; the caller commits.

### 5. Pagination, ordering, export
- GET `/api/inventory/transactions?page&per_page=50[&filters]`.
- Server caps `per_page` at 200 and orders by `created_at DESC`.
- Footer: "Showing <start> - <end> of <total> transactions", where start = (page−1)·per_page+1 and end = min(page·per_page, total). "Page X of Y" (Y defaults to 1).
- Previous and Next are enabled from `has_prev` / `has_next`.
- **Export:** none.

### 6. States
- **Loading:** the `#loading-state` spinner "Loading transactions..." and table body opacity 0.5.
- **Empty** (zero rows): "No Transactions Found / There are no inventory transactions matching your filters." The pagination bar is hidden.
- **Error:** an in-table row "Failed to load transactions" or "Error loading transactions", with `colspan=8` while the table has 9 columns (minor bug).
- Server errors inside `get_inventory_transactions` are swallowed and returned as an empty page, so they show as "No Transactions Found".

### 7. Keyboard, persistence, polling
- Enter to apply filters in the two text fields.
- No URL parameters, no localStorage, no polling.
- CSS: responsive breakpoints at 1200, 992, 768 and 480px (filters collapse to 3, 2, then 1 column). Under 768px the table scrolls horizontally (min-width 800px). No print rules.

---

## low-stock-print.html — Inventory Status Report

### 1. Purpose, URL, access
- **Purpose:** a printable or exportable reorder report of urgent, out-of-stock and low-stock items, with prices and reorder costs.
- **URL:** `/low-stock-print.html` (app.py:334).
- **Access:** standalone page. It loads only `static/js/libs/xlsx.full.min.js` (relative path, which works at the site root). It has no auth, theme, app-shell or api-helper, so **no access control** applies and no API calls are made.
- **No page in the app links to it**, and nothing writes its data source (see §2). In practice it always shows the empty state. It is a legacy page.

### 2. Data loading
- Reads `JSON.parse(sessionStorage.getItem("lowStockItems") || "{}")`. `grep` finds no writer of this key anywhere.
- **New format** `{urgent_items, low_stock_items}`:
  - urgent = `urgent_items`
  - out-of-stock = `low_stock_items` with `quantity === 0`
  - low = `low_stock_items` with `quantity > 0`
- **Old format** (an array):
  - urgent: `quantity < 0`
  - out-of-stock: `== 0`
  - low: `> 0 && <= reorder_level`
- Uses `quantity`, not `closing_quantity`.
- With no items: "🎉 Excellent Inventory Management! / All inventory items are above their reorder levels. No action required." The summary counts stay at 0.

### 3. What is shown and printed
- Action bar (hidden in print): "Export Excel" (calls `exportToPDF()`, misnamed) and "← Back to Inventory" (→ inventory.html). There is no Print button; the user prints with the browser.
- Header "GermanATO / Inventory Status Report / Comprehensive overview of stock levels and reorder requirements".
- Info strip:
  - Report Date (`en-US` long date with hh:mm)
  - Total Items
  - Urgent Items
  - Out of Stock
  - Low Stock
- Summary cards:
  - Urgent
  - Out of Stock
  - Low Stock
  - **Total Value** = `PKR Σ(reorder_quantity × price)` with 2 decimals
- Tables:
  - **Urgent** — "🚨 URGENT - Negative Stock Items" + count. Columns: Priority ("Critical"), Part Number (or "N/A"), Item Name, Category, Current Stock (red), Location (or "N/A"), Price "PKR x.xx", Reorder Qty, Total Cost = reorder_quantity×price, Status badge "URGENT" (blinking).
  - **Out of Stock** — Priority "High", Part Number, Item Name, Category, Location, Price, Reorder Qty, Total Cost, Status "Out of Stock". No Current Stock column.
  - **Low Stock** — Priority "High" if `quantity <= reorder_level/2`, else "Medium". Columns: Part Number, Item Name, Category, Current Stock, Reorder Level, Location, Price, Reorder Qty, Total Cost, Status "Low Stock".
- Footer: "GermanATO - Professional Auto Services", "This report was generated on <date>", contact line.
- Category display mapping: same as inventory.js.

**Reorder quantity logic:**
- Uses `item.reorder_quantity` directly (model column default 10). Nothing is computed, for example from reorder_level minus stock.
- Neither `price` nor `reorder_quantity` is returned by any inventory API (`inventory_item_to_dict`). Data from today's API would make `item.price.toFixed` throw (bug, if it were ever wired up).

**Print layout** (`@media print`):
- Removes the action bar and body padding; font 12px; tables 11px.
- Summary grid becomes 4 columns.
- `print-color-adjust: exact` on badges, coloured rows, section headers and summary cards.

**Responsive:** under 768px, the summary and info grids become 2 columns and the actions stack.

**Editing:** none.

### 4. Excel export (`exportToPDF`)
- Rebuilds the item lists from sessionStorage. With no items: alert "No items to export!".
- **Sheet "Inventory Status"** — columns:
  - Priority: <0 "Critical", 0 "High", else "Medium". This differs from the on-screen Low-Stock priority rule.
  - Part Number (or "N/A"), Item Name, Category
  - Current Stock, Reorder Level
  - Location (or "N/A"), Price (PKR), Reorder Quantity
  - Total Cost (PKR): `(reorder_quantity×price).toFixed(2)`, stored as a string
  - Status: `stock_status`, or a derived value
  - Description (or "N/A"), Last Updated (`updated_at` or "N/A")
- Column widths: 10, 12, 25, 15, 12, 12, 15, 12, 15, 15, 20, 30, 20.
- **Filename:** `GermanATO_Inventory_Status_YYYY-MM-DD.xlsx` (UTC date).

---

## transaction-history.html — missing file
- `app.py:342-344` defines `@app.route('/transaction-history.html')`, which calls `send_from_directory(frontend, 'transaction-history.html')`.
- **The file does not exist** (`ls frontend/transaction-history.html` → No such file), so the route returns 404.
- Nothing in frontend/ or static/js references it.
- The real page is `inventory-history.html`. Drop this route in the rewrite, or redirect it to the history page.

---

## Backend rules the UI relies on (summary)
- **Models** (models.py:153-200, 818-858):
  - `Inventory`:
    - Identifiers: id; part_number (String20, unique, auto `PN###`); barcode (String100, unique, nullable); manufacturer_part_number (String100, unique, nullable).
    - Descriptive: name (255, required); category (String100, free text, required); description; location; image_path.
    - Stock: quantity (int, may go negative through deductions); price (float, default 0, never set by the UI); reorder_level (default 5); reorder_quantity (default 10, unused by the API).
    - Timestamps: created_at and updated_at (naive UTC).
  - `InventoryTransaction`: as described in the history section.
- **Categories:**
  - Model `Category` (`categories` table: name unique, description, is_active).
  - CRUD at `/api/settings/categories` (GET, POST, PUT and DELETE `/<id>`), managed from the Settings page.
  - Inventory stores category **as a string**, not a foreign key. Renaming or deleting a settings category does not touch items, which is why edits show the "(Legacy)" option.
- **`/api/inventory/stats`:** `low_stock_items` uses a hardcoded `quantity < 10`, not reorder_level. Unused by any UI.
- **Unused by these pages:** `/api/inventory/transactions/<id>` and `/api/inventory/<id>/transactions` (no frontend callers). `inventory_utils.py` is legacy: `deduct_inventory_quantity` is a no-op, and `process_repair_order_parts` is a no-op; neither is used by these pages.

---

### Endpoints used
| METHOD | path | page/action |
|---|---|---|
| GET | /api/inventory/categories | inventory.html: build the category list for the grid; fallback for the category select |
| GET | /api/inventory/by-category?page&per_page=50&search&category | inventory.html: initial per-category load, Show More |
| GET | /api/inventory/search-grouped?q= | inventory.html: main search, including the no-match suggestions |
| GET | /api/inventory/search?q= | inventory.html: Receive Stock product dropdown |
| GET | /api/inventory/lookup?code= | inventory.html: Receive Stock barcode/part-number lookup |
| GET | /api/inventory/<id> | inventory.html: Edit modal prefill |
| POST | /api/inventory (multipart) | inventory.html: Add item |
| PUT | /api/inventory/<id> (multipart) | inventory.html: Edit item (may log an adjustment) |
| DELETE | /api/inventory/<id> | inventory.html: Delete item |
| POST | /api/inventory/receive {code,quantity,notes} | inventory.html: Receive Stock with a code |
| POST | /api/inventory/restock {product_id,quantity,notes} | inventory.html: Receive Stock with a selected product |
| GET | /api/inventory/low-stock | inventory.html: Low Stock view, Export Low Stock |
| GET | /api/inventory?page=N&per_page=200 | inventory.html: Print Sheet (complete Excel export) |
| GET | /api/inventory/<id>/ledger | inventory.html: per-item Excel ledger |
| GET | /api/settings/categories | inventory.html: category select options (silent) |
| GET | /api/inventory/transactions?page&per_page=50&date_from&date_to&transaction_type&repair_order_id&search | inventory-history.html: table; `search` is ignored by the server |
| — | (none) | low-stock-print.html makes no API calls; it reads only sessionStorage `lowStockItems` |
| GET | /transaction-history.html | app.py route to a non-existent file (404) |
| (exist, not used by these pages) | GET /api/inventory/stats, GET /api/inventory/transactions/<id>, GET /api/inventory/<id>/transactions, POST /api/inventory/check-stock, POST /api/inventory/deduct-items | check-stock and deduct-items are used by invoiceShared.js; the others have no frontend caller |

### Files read
| File | Lines |
|---|---|
| frontend/inventory.html | 471 |
| frontend/inventory-history.html | 214 |
| frontend/low-stock-print.html | 937 |
| static/js/inventory.js | 2076 |
| static/js/inventoryHistory.js | 382 |
| static/js/performance-utils.js | 348 |
| static/css/inventory.css | 1888 |
| static/css/inventoryHistory.css | 752 |
| inventory_routes.py | 1469 |
| inventory_utils.py | 94 |
| inventory_transaction_utils.py | 272 |
| settings_routes.py | 248 |
| models.py (Inventory 153-200, RepairOrderPart 281-290, Category 791-815, InventoryTransaction 818-858 read in full; rest of file not in scope) | 875 |
| Consulted excerpts: app.py (routes 176-186, 333-346, blueprint registration), jwt_auth.py (permissions/decorators 18-170), auth_jwt.js (requirePageAccess/canAccessPage 1-20, 211-285), app-shell.js (NAV/ACTIONS 55-130, handleNewParam/slimHeader/unsaved guard 361-445), api-helper.js (renderNoMatches 309-354, request/performRequest/responseError 384-524), repairOrdersManagement.js (URL params 5-20), search_suggestions.py (suggestions_for 88-98) | — |
| frontend/transaction-history.html | does not exist |
