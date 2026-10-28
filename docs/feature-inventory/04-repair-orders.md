# Repair Orders (Job Cards): Feature Inventory

Shared backend facts used throughout:
- All `/api/repair-orders*` routes use `@login_required` and `@role_required(['admin','accountant','inventory_manager'])`. The path prefix `/api/repair-orders` maps to the permission `repair-order` (`jwt_auth.py:37-62`).
- Default page permissions: all three roles have `repair-order` and `repair-orders-management`. **accountant** does not have `inventory`. **inventory_manager** has neither `car` nor `invoice` (`jwt_auth.py:24-35`). Admins bypass permission checks. A RolePermission DB row can override these defaults.
- The model stores customer and vehicle data as text snapshots (`customer_name`, `_phone`, `_address`, `_reg_no`, `_made`, `_mileage`, `_vin`, `_color`, `_chasis`). Next to them sit the link ids `customer_id` and `car_id` (FK, ON DELETE SET NULL). Other columns: `problem_description`, `diagnosis_plan`, `worker_id`, `worker_name`, `workers_json`, `current_status` (default `received`), `status_timeline` (JSON text), `vehicle_condition` (JSON text), `notes`, `created_at`, `updated_at`, `created_by_user`, `updated_by_user` (`models.py:~240-278`).
- Child rows:
  - `RepairOrderPart`: `inventory_id`, `description`, `part_number`, `quantity` (int), `status` (default `pending`).
  - `RepairOrderLabour`: `description`, `status` (default `pending`).
  - Both use cascade delete-orphan and are ordered by id.

---

## repair-order.html — Create / Edit Repair Order

### 1. Purpose, URL, modes, access
- **Purpose:** create a job card from scratch, create one from an approved quote, or edit an existing one.
- **URL:** `/repair-order.html` (served by `app.py:237`). Query params:
  - `id=<roId>`: edit mode (`repairOrder.js:25,74`).
  - `quoteId=<invoiceId>`: prefill from a quote (`:24,69`). Linked from `pendingQuotes.js:255` as `repair-order.html?quoteId=X&from=pending-quotes`.
  - `from=`: back-button target and page wording (see §11).
- **Modes:**
  - **New (from quote).** This is the default wording: "Create Repair Order / Generate repair order from approved quote".
  - **New (from scratch).** Wording becomes "Create New Repair Order / Create a new repair order from scratch" when `from` is `invoice-management`, `invoiceSystem` or `repair-orders-management` (`:46-55`).
  - **Edit.** Applied by `setEditMode()` after the GET succeeds: title "Edit Repair Order", description "Update repair order details", button "Update Repair Order" (`:482-491`).
  - There is no separate read-only "view" mode. The only read-only case is the **completed lock**: if `current_status === "complete"` and `localStorage.user.role !== "admin"`, every input, textarea, select and button that exists in the form at that moment is disabled and set read-only. A red banner is inserted at the top of the form: "This repair order is Completed and Locked. Only administrators can make edits." (`:423-451`). The server enforces the same rule with a 403.
- **Access:** `auth.requirePageAccess("repair-order")` (`:13`).
- **Linked from:**
  - app-shell nav "New repair order" (`app-shell.js:57`)
  - `invoiceSystem.html:163` (`?from=invoiceSystem`)
  - Management "Create Repair Order" button (`?from=repair-orders-management`)
  - Management Edit button (`?id=X&from=repair-orders-management`)

### 2. Layout / sections
1. Sticky top header: logo, `#page-title`, `#page-description`, Back link `#back-btn`.
2. Form `#repair-order-form` containing section cards:
   - **Customer Information:** searchable customer picker, "+" button (add customer), "Customer Details" sub-heading with an Edit button (hidden until a customer is picked), then name, phone and address.
   - **Vehicle Information:** searchable vehicle picker, "+" button (add vehicle), "Vehicle Details" with an Edit button (hidden until a car is picked), then reg, make/model, mileage, VIN, color, chassis.
   - **Problem Description**
   - **Assigned Worker:** searchable picker plus a badge list.
   - **Parts Required:** dynamic rows and an "Add Part" button.
   - **Labour Tasks:** dynamic rows and an "Add Labour Task" button.
   - Submit button `#submit-btn`.
3. Footer "© 2025 GermanATO".
4. Modals, outside the form: `#customer-modal` and `#car-modal`.
- Scripts loaded: notification-utils, auth_jwt, app-shell, api-helper, phone-formatter, customer-car-utils, repairOrder.js (`repair-order.html:560-566`). phone-formatter is included but repairOrder.js never calls it directly.

### 3. Form fields

**Customer**

| Label | id / name | Type | Req | Notes |
|---|---|---|---|---|
| Select Customer | `customer-select` (no name) | text search | – | Client-side filter of options rendered as `"{code} · {name} - {phone}"` (code omitted if absent) (`:1179`). Click shows the full list. Typing does a case-insensitive substring filter on the option text (`:1219-1231`). Clicking an option calls `handleCustomerChange(id)`. No keyboard navigation. |
| Customer Name * | `customer-name` / `customer_name` | text | required, **readonly** | Filled from the picked customer, the quote, or the RO. |
| Phone Number * | `customer-phone` / `customer_phone` | tel | required, readonly | |
| Address * | `customer-address` / `customer_address` | text | required, readonly | |

**Vehicle**

| Label | id / name | Type | Req | Notes |
|---|---|---|---|---|
| Select Vehicle | `car-select` | text search | – | If no customer is selected, clicking alerts "Please select a customer first before selecting a car." (`:1263-1266`). The list is only the selected customer's cars, shown as `"{make} {model} - {plate_no}"`. Empty states: "No cars found for this customer" or "Please select a customer first" (`:1672-1717`). |
| Registration Number * | `reg-number` / `customer_reg_no` | text | required, readonly | from `car.plate_no` |
| Make/Model * | `made` / `customer_made` | text | required, readonly | `"{make} {model}".trim()` |
| Mileage | `mileage` / `customer_mileage` | text | readonly | |
| VIN | `vin` / `customer_vin` | text | readonly | |
| Color | `color` / `customer_color` | text | readonly | |
| Chassis | `chasis` / `customer_chasis` | text | readonly | from `car.chasis_no` |

- **Picking a car** (`handleCarChange`, `:1740-1788`):
  - Rejects a car whose `customer_id` differs from the selected customer, with the alert "This car does not belong to the selected customer…".
  - Fills the six vehicle fields and shows `#edit-car-btn`.
- **Changing the customer** (`:1432-1500`):
  - Sets `selectedCarId=null` and clears the car search box.
  - Tries to clear vehicle fields using ids that do not exist (`car-reg`, `car-make`, …). The real fields (`reg-number`, `made`, …) are therefore **not cleared** and keep the previous car's data (bug).

**Problem Description:** `problem-description` / `problem_description`, textarea, rows 4, **required** (the only "required" field that is actually enforced, because the others are read-only; see §12).

**Inspection / intake:** there are no checklist, fuel, condition, diagnosis or notes fields in the UI. The backend supports `diagnosis_plan`, `vehicle_condition` and `notes` on PUT (`repair_order_routes.py:517-522`) and returns them, but the UI never sends them.

**Worker assignment (multiple workers):**
- Search input `worker-select` filters options `"{first_name} {last_name} - {position||'Worker'}"` (`:1732`).
- Clicking an option adds the worker id to `selectedWorkerIds` (duplicates ignored) and clears the input (`:1855-1868`).
- Selected workers render as pill badges (light blue, "First Last ×"). Clicking × removes the worker (`:1792-1828`).
- Legacy hidden fields: `worker-id` (`worker_id`) holds the first selected worker's id; `worker-name` (`worker_name`) holds all names joined with ", " (`:1830-1852`).
- Source: `GET /api/repair-orders/assignable-workers` returns `{workers:[{id,first_name,last_name,position}]}`. Only `status=='active'` workers, ordered by first then last name (`repair_order_routes.py:41-71`). It sits under `/api/repair-orders` so it needs the `repair-order` permission, not `hr`.
- In edit mode, ids come from `workers_json[].id`, falling back to the single `worker_id` (`:404-412`).

**Customer modal** (`#customer-form`):
- Fields: Name (`modal-customer-name`), Phone (`tel`, `modal-customer-phone`), Address (textarea). None are required client-side.
- Title is "Add Customer" or "Edit Customer".
- Save calls `CustomerCarUtils.createCustomer(data)` or `updateCustomer(id, data)`, then:
  - updates the local `customers` array;
  - toasts "Customer created/updated successfully!" through `showNotification`, falling back to `alert`;
  - fills the three customer fields;
  - sets the picker text to `"{name} - {phone}"` (no code, inconsistent with the list);
  - re-renders the list;
  - on create, calls `handleCustomerChange(newId)`.
- Closes on ×, Cancel, or a click on the backdrop. Errors are shown with `showNotification(msg,'error')` (`:1503-1639`).

**Car modal** (`#car-form`):
- Fields:
  - Customer `<select>`: all customers, preselected to the current customer.
  - Registration Number * (required)
  - Make * (required, placeholder "e.g., Toyota")
  - Model (placeholder "e.g., Corolla")
  - Mileage
  - VIN * (required, `maxlength=17`, placeholder "17-character VIN")
  - Color
  - Chassis
- Titles set by JS are "Add Car" and "Edit Car". The static HTML title is "Add Vehicle".
- The payload is `{customer_id, plate_no, make, model, mileage, vin, color, chasis_no}`, sent through `CustomerCarUtils.createCar` / `updateCar`.
- After save it fills the vehicle fields and sets the picker text to `"{make}{ model} - {plate}"`. It auto-selects the new car only if `updatedCar.customer_id === selectedCustomerId` (`:1871-2080`).

### 4. Parts and labour rows

**Part row** (`addPartItem`, `:181-256`):
- Element id `part-N`, where N is a counter that never resets or renumbers.
- A × remove button calls `removeItem('part-N')`, which removes the DOM node with no confirmation.
- Heading "Part N".
- **Search Inventory** `part-inventory-search-N` (text), plus hidden `part-inventory-N` (`parts[N][inventory_id]`), plus an options list.
  - Requires at least 2 characters and is debounced by 300 ms.
  - Calls `GET /api/inventory/search?q=<term>` and uses `result.results`. The server caps results at 200.
  - While loading it shows "Searching…". Empty results show "No items found"; errors show "Error searching items".
  - Options are labelled `"{part_number} - {name} (Stock: {quantity})"`.
  - Focusing a box that already holds at least 2 characters re-runs the search.
  - Choosing an item (`selectInventoryItem`, `:1101-1135`):
    - search text becomes `"{pn} - {name}"`;
    - hidden id is set;
    - Description becomes `item.name` and Part Number becomes `item.part_number`;
    - quantity becomes 1 if it was empty or "0".
- **Description *** `part-description-N`: required and **readonly**. It can only be filled from inventory, a quote or the existing RO, so free-text (non-inventory) parts cannot be typed in.
- **Part Number** `part-number-N`: readonly.
- **Quantity *** `part-quantity-N`: number, `min=1`, `step=1`, required.
- **Status** `part-status-N`: select with values `Pending | Ordered | Received | Installed` (capitalised as sent).

**Labour row** (`addLabourItem`, `:258-295`):
- id `labour-N`, × remove, heading "Labour Task N".
- **Description *** (free text, required).
- **Status** select: `Pending | In Progress | Completed`.
- No price or hours.

**Rows on submit:**
- Rows whose description is blank are **silently dropped** (`:561, :581`).
- Part payload: `{inventory_id: hidden||null, description, part_number, quantity: parseFloat||0, status}`.
- Labour payload: `{description, status}`.

**Per-row status:** saved only through the full form PUT. The backend also has `PUT /api/repair-orders/<id>/parts/<partId>/status` and `/labour/<labourId>/status` (`repair_order_routes.py:638-696`, logged as `UPDATE_PART_STATUS` / `UPDATE_LABOUR_STATUS`). **No UI calls them.** Part and labour status values have no effect on stock.

**Stock behaviour** (backend, `repair_order_inventory_utils.py`):
- **Create** (`process_repair_order_parts`, `:86-131`): for each part with a description and `int(quantity) > 0`, inventory is resolved in this order:
  1. explicit `inventory_id`: deduct;
  2. else `part_number`: exact match, deduct; **if not found it is an error**;
  3. else description: exact name match, deduct; if not found the part is silently kept with no deduction.

  Deduction (`deduct_inventory_quantity`, `:15-59`):
  - **allows negative stock**;
  - logs an `issue_out` InventoryTransaction with negative quantity, reference "Issued for Repair Order #X" and notes "Part: {name}";
  - **commits per part**.

  Any error makes the whole create return 400 `{error:'Failed to process parts', details:[...]}`.
- **Edit** (`handle_repair_order_edit_inventory`, `:262-357`): old and new part lists are each **aggregated by inventory identity**. The key is `int(inventory_id)`, else `pn:<part_number>`, else `desc:<description>`, with quantities summed, so duplicate rows of the same part are combined (`:162-190`). Then:
  - **removed** keys: stock restored and logged as `adjustment` (+qty), "Part removed from Repair Order #X", notes "…Returned to stock";
  - **quantity increased**: `deduct_inventory_quantity(delta)` (`issue_out`, which counts as a sale);
  - **quantity decreased**: restored and logged as `adjustment` (+delta), "Part quantity reduced in Repair Order #X";
  - **new keys**: `process_repair_order_parts` (deduct).

  Any error returns 400 `{error:'Failed to process inventory changes', inventory_errors:[...]}`. On success the old part rows are deleted and recreated from the payload.
- **Duplicate parts:** the UI allows the same inventory item on several rows. On create each row is deducted separately; on edit rows are aggregated, so the net effect is the same.
- **Stock warnings in the UI:** none before submit. The only signal is the "(Stock: N)" text in search results. After submit the UI shows `result.inventory_warnings` in an alert, but on success the server never returns any (see §12).

### 5. Status workflow
- Status is **not editable on this page**. It changes only from the management list (§7). For the full workflow, see the management page section.
- Effects visible on this page:
  - a new order starts `current_status='received'` (`repair_order_routes.py:320`);
  - `complete` triggers the edit lock for non-admins (client `:425`, server `:446` with 403 "Completed repair orders can only be edited by administrators").

### 6. Submit / update flows (`handleFormSubmit`, `:493-716`)
1. `form.checkValidity()` / `reportValidity()`. In practice only Problem Description, part quantities and labour descriptions are validated (read-only fields are excluded from constraint validation).
2. Payload:
   ```
   { customer_id: selectedCustomerId||null, car_id: selectedCarId||null,
     customer_name, customer_phone, customer_address, customer_reg_no, customer_made,
     customer_mileage, customer_vin, customer_color, customer_chasis,
     problem_description, worker_id|null, worker_name|null, worker_ids:[int],
     parts:[{inventory_id, description, part_number, quantity, status}],
     labour:[{description, status}] }
   ```
   In edit mode it re-reads the same customer and vehicle values from the DOM, so the result is identical (`:527-554`).
3. **Side effects before saving the RO:**
   - If a customer is selected: `CustomerCarUtils.updateCustomer(selectedCustomerId, {name, phone, address})`.
   - If a car is selected: `CustomerCarUtils.updateCar(selectedCarId, {make: first word of customer_made, model: rest, plate_no, mileage, vin, color, chasis_no, customer_id})`.
   - Failures are logged and ignored (`:594-633`).
   - So **every save writes the form's customer and vehicle text back to the master records.**
4. **Create:** `POST /api/repair-orders`.
   - Server:
     - requires `customer_name` (400 "Customer name is required");
     - resolves workers from `worker_ids` (unknown ids ignored), storing `worker_id` = first, `worker_name` = names joined by ", ", `workers_json=[{id,name}]`;
     - legacy fallback when `worker_ids` is empty: `worker_id` / `worker_name`;
     - `apply_links` (document_links.py) sets `customer_id` / `car_id`. Customer: explicit id, else exact name+phone, else a unique phone match, else a unique name match. Car: explicit id, else VIN, then plate, preferring the customer's own car, else a unique match. An unowned car is **adopted** by the customer;
     - processes parts (stock), adds labour, logs `CREATE` in AppLog ("Created repair order for customer X (Car: made)").
   - Returns 201 `{message, repair_order_id}`.
   - Client: if `inventory_warnings` exist (never, in practice) they are alerted. It stores `sessionStorage.repairOrderData = JSON(payload sent)` and `sessionStorage.repairOrderId = result.repair_order_id`, then redirects to `repair-order-template.html?from=repair-order`. No success alert.
5. **Update:** `PUT /api/repair-orders/<id>`.
   - Server:
     - returns 403 if the order is complete and the user is not admin;
     - updates each `customer_*` field present and non-null;
     - re-runs `apply_links` (an edit can move the order to another customer or car);
     - sets `problem_description`;
     - `worker_ids` is always sent, so workers are recomputed (an empty list clears worker_id, worker_name and workers_json);
     - reconciles inventory, replaces parts, replaces labour, logs `UPDATE`.
   - Returns `{message}`.
   - Client: alert "Repair order updated successfully!" (plus warnings if any), then redirect to `repair-orders-management.html`. It does **not** open the template.
6. **Errors:** `APIHelper` throws on any non-2xx. The `else` branches that read `result.inventory_errors` are dead code. All failures reach `catch`, which alerts "Error: Failed to save repair order. Please try again." APIHelper also shows its own error state with the server message; a create 400 includes the `details` list.

### 7. Management list
Not on this page; see repair-orders-management.html.

### 8. Printable template
After a successful create the page redirects to the template (§ repair-order-template.html).

### 9. Calculations
None. Pricing was removed ("Price-related fields removed - no totals needed", `:590`). Quote prices are passed to `addPartItem` but ignored.

### 10. Keyboard, scanner, autofocus, polling, unsaved changes
- **Part inventory search keys** (`:938-981`):
  - ArrowDown / ArrowUp cycle the `.selected` highlight (wraps around);
  - Enter selects the highlighted option, and calls `preventDefault`, so it does not submit the form;
  - Escape hides the list and blurs.
- Customer, car and worker pickers have no keyboard navigation. Enter in those boxes, or in other text inputs, triggers implicit form submission.
- Barcode scanner: no dedicated handling. A scanner's trailing Enter only selects an option if one is highlighted.
- No autofocus, no polling, no unsaved-changes warning.
- Clicking outside closes all dropdowns; several duplicate document click listeners do this (`:984, :1204, :1390`).
- An open picker adds `.dropdown-active` to its section card (CSS sets z-index 1000) so the list overlays the cards below.

### 11. Persisted state and navigation
- `localStorage.lastPage`:
  - read as a fallback for `from` (default `pending-quotes`);
  - then set to `"repair-order"` (`:20-43`).
- `localStorage.user`: read for the role in the completed lock (`:424`).
- Back-button mapping:

  | `from` value | Back goes to |
  |---|---|
  | `pending-quotes` | `pending-quotes.html` |
  | `admin` | `admin.html` |
  | `invoiceSystem` | `invoiceSystem.html` |
  | `repair-orders-management` | `repair-orders-management.html` |
  | anything else | `repair-orders-management.html` |

- `sessionStorage.repairOrderData` / `repairOrderId`: written on create for the template.
- `window.editingCustomerId` / `window.editingCarId`: globals used by the modals.
- **Quote prefill** (`loadQuoteData`, `:123-179`):
  - `GET /api/invoice/<quoteId>` fills the customer and vehicle **text fields only**. No customer or car is selected, so `customer_id` / `car_id` are null and the server falls back to `apply_links` matching.
  - Each `items[]` entry becomes a part row `{description: product_name, part_number, quantity, status:'Pending'}`.
  - Each `labours[]` entry becomes a labour row `{description, status:'Pending'}`.
  - After 100 ms, `matchQuoteItemsToInventory` sets inventory ids by exact `part_number` match against the preloaded `inventoryItems`.
  - The problem description is not prefilled. The quote id is not sent, so there is no quote-to-RO link and the quote is not marked as converted.
- **Edit load** (`:304-480`):
  - `GET /api/repair-orders/<id>`, then `setEditMode()`, then (100 ms later) `populateFormWithRepairOrderData`.
  - Customer match in the loaded list: exact name+phone, then phone only, then name only. On a match it calls `handleCustomerChange`; after 100 ms it matches the car by `plate_no` among that customer's cars and calls `handleCarChange`.
  - Then it fills the text fields from the RO snapshot, problem description, workers (with the lock check), part rows (inventory search label matched after 200 ms by `inventory_id`, else `part_number`) and labour rows.

### 12. Quirks, bugs, dead code
- **Read-only + required is not enforced.** Browsers exclude `readonly` fields from constraint validation. The form can be submitted with no customer or vehicle; the server only rejects an empty `customer_name`. Parts with an empty description are silently dropped.
- **Customer master gets overwritten in edit mode.** `handleCustomerChange` fills from the master record, then lines 383-396 overwrite with the RO's historical snapshot. On save, `updateCustomer` writes that old name, phone and address **back to the customer master**.
- **Vehicle snapshot gets overwritten in edit mode.** For the vehicle, the 100 ms `handleCarChange` overwrites the RO snapshot with current master data (mileage etc.), so saving rewrites the RO's historical vehicle data. Both behaviours contradict the model's "historical record" intent (`models.py` comment).
- **Edit-mode race conditions.**
  - Customer and car matching only works if `customers` and `cars` (loaded asynchronously in parallel) arrive before the RO fetch plus 100 ms. If not, nothing is selected, and the save sends `customer_id:null, car_id:null` (the server re-resolves through `apply_links` fallbacks).
  - Worker badges render only if `workers` has loaded. Otherwise ids are kept but invisible and cannot be removed. Inactive workers already on an order never render as badges for the same reason.
- **Inventory matching only sees the first 50 items.** `loadInventoryItems()` calls `GET /api/inventory`, which is **paginated (default 50 per page)** (`inventory_routes.py:404-411`). So the part-row search labels in edit mode and quote matching only work for the first 50 items. In edit mode the hidden `inventory_id` is still preserved (`:242-248`). For quotes, an unmatched row is sent with only `part_number`; if that part number is not in inventory, **the whole create fails** ("Inventory item not found for part number").
- **Permission gaps (default role permissions).**
  - **accountant** has no `inventory` permission, so the inventory search and list calls fail and accountants cannot add inventory parts.
  - **inventory_manager** has no `car` permission, so `/api/customers` and `/api/cars` fail and the customer and vehicle pickers and modals are unusable. It also has no `invoice` permission, so quote prefill fails.
- **Customer change does not clear vehicle fields.** It clears non-existent ids (`car-reg`, `car-make`, …, `:1461-1475`), so the previous car's data stays while `selectedCarId=null`.
- **Completed lock is incomplete.** It runs **before** part and labour rows are appended (`:423` vs `:454`), so those rows stay editable and removable. Submit is disabled, so this is harmless. The modals sit outside the form and are not disabled, but the buttons that open them are.
- **Stock changes are not atomic.**
  - `deduct_inventory_quantity` commits per part. A create failure after some deductions leaves the RO row and earlier deductions committed while returning 400.
  - On edit, uncommitted restorations get committed by a later deduct's commit, then the error path's rollback cannot undo them.
- **`inventory_warnings` is effectively never returned.** Any inventory error makes the update fail with 400 under `inventory_errors`, a key APIHelper ignores. Create errors use `details`, which APIHelper appends to its message.
- Server stores part and labour status exactly as sent (capitalised `Pending`, `In Progress`, …). Model comments and server defaults use lowercase `pending`, `in_progress`, `completed`.
- Quantity is `parseFloat` client-side and `int()` server-side, so fractions are truncated.
- **Dead code:**
  - `populateInventoryDropdowns`, `populateInventoryDropdown` (targets `select[id^=part-inventory-]`, which no longer exists), `onInventorySelect` (defined twice; the second definition is a no-op), `populateInventoryDataForPart`, `populateSearchOptions`, `showAllOptions`;
  - unused `quantityInput` (`:253`) and global `selectedWorkerId` (`:9`);
  - all `else` branches after API calls.
- `loadInventoryItems` can run twice in edit mode (`:313-315` and `:1143`).

---

## repair-orders-management.html — Repair Orders Management

### 1. Purpose, URL, access
- **Purpose:** list, filter, search, change status, view, edit, delete, open history, and generate an invoice from a completed RO.
- **URL:** `/repair-orders-management.html` (`app.py:250`).
- **Access:** `auth.requirePageAccess("repair-orders-management")`.
- **Linked from:** app-shell "Repair orders"; `invoiceSystem.html:142` (`?from=invoiceSystem`); `inventory.html:76` (`?from=inventory`); dashboard links; `inventoryHistory.js:238` (`?id=X`, but the page **ignores `id`**).
- **Styles:** `theme.css`, `search.css`, `app-shell.css`. It does not use repair-order.css.
- **Scripts:** notification-utils, auth_jwt, app-shell, api-helper, **xlsx.full.min.js (loaded but unused)**, documentLog, repairOrdersManagement.js.

### 2. Layout
1. Header "Repair Orders Management / View and manage all repair orders and their status" with Back.
2. "Create Repair Order" button, which goes to `repair-order.html?from=repair-orders-management`.
3. Search section:
   - Keyword input `#keyword-search` (placeholder "Customer name, phone, reg number...");
   - ID input `#id-search` (`type=number`, `min=1`, placeholder "Repair Order ID");
   - search icon button;
   - clear (×) button, visible only while either input has text.
4. Status toggle buttons: All Orders (active by default), Received, Diagnosis, Repair, Testing, Complete.
5. Results container `#repair-orders-management-results`.

### 3. List / cards (`loadRepairOrders`, `:63-433`)
- **Request:** `GET /api/repair-orders?status=<s>&keyword=<k>&id=<n>&_t=<Date.now()>`.
  - `status` is omitted for "all"; `_t` is a cache-buster.
  - Loading state: `APIHelper.renderLoading(…,"Loading repair orders...")`.
  - Errors: `APIHelper.renderError(…, retry)`.
- **Server filtering** (`repair_order_routes.py:75-186`):
  - exact `current_status`;
  - `id` must be an integer, otherwise it returns an empty list;
  - `keyword`: `ILIKE %k%` across customer name, phone, address, reg, made, VIN, color, chassis, problem description and worker_name;
  - **sorted by `created_at` desc**; **no pagination**;
  - each row returns the full RO including parts and labour, `customer_code = "CN%03d" % customer_id` (or ""), `status_timeline`, `workers_json`, etc.;
  - when a keyword finds nothing, it adds spelling and nearest-customer `suggestions_for(...)`. **The UI ignores these.**
- **Empty state:** "No {status} repair orders found." (the status word is blank for "all").
- **Heading:** "Repair Orders (N)".
- **Card per RO:**

  | Card element | Content |
  |---|---|
  | Header | "RO #id"; status badge with class `status-{current_status}` and the status in UPPERCASE text |
  | Customer Name | name, plus a `.customer-code` span if a code exists |
  | Phone | |
  | Vehicle | "reg - made" |
  | Created Date | `formatDate` = `toLocaleString('en-PK',{year:'numeric',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'})` |
  | Problem | truncated to 50 characters plus "..." |
  | Assigned Worker | `worker_name`, or "Not assigned" |
  | Last Status Change | "{Status} - {date}". The status is the timeline key with the latest valid `date`; with no timeline it shows "Received - N/A" (`:478-513`) |
  | Timeline preview | 5 steps (Received, Diagnosis, Repair, Testing, Complete); only the current one gets class `current`, no dates |
  | Actions | **View**, **History**, **Edit**, **Generate Invoice** (only when `current_status==='complete'`), **Delete**, and a status `<select>` |

- **Completed + non-admin** (role from `auth.getCurrentUser().role`): Edit and Delete are disabled (opacity 0.5) and the status select is disabled (opacity 0.7).
- No sorting controls, no pagination, no bulk actions, **no Excel export** (xlsx is loaded but never used).

### 4. Actions
Event listeners are attached in a `setTimeout(100)` after render.

- **Status change** (`:235-302`): `PUT /api/repair-orders/<id>/status` with body `{status, timestamp: new Date().toISOString()}`.
  - On success it updates the badge text and class, the timeline preview and Last Status Change from `res.status_timeline`, and toasts "Status updated successfully!".
  - On error it toasts "Error updating status." and **does not revert the select**.
  - The card is not removed from a filtered view it no longer matches, and the completed-lock controls are not applied until reload.
- **View** (`:315-339`): `GET /api/repair-orders/<id>`, then `sessionStorage.repairOrderData` = full JSON and `repairOrderId` = id, then `repair-order-template.html?from=repair-orders-management`. Errors: "Repair order not found" or "Failed to load repair order data".
- **History:** `DocumentLog.open("repair-order", id)` (shared module), which calls `GET /api/repair-orders/<id>/log`. That returns `{kind:'repair-order', document_id, reference:"#id", customer_name, created_at, created_by, current_status, payments:[], entries: document_log_entries('repair-order', id)}` (`repair_order_routes.py:16-38`).
- **Edit:** goes to `repair-order.html?id=<id>&from=repair-orders-management`.
- **Generate Invoice (RO to invoice):**
  - `GET /api/repair-orders/<id>`, then `sessionStorage.repairOrderForInvoice` = JSON, then `invoice.html?from=repair-order` (`:353-385`).
  - `createInvoice.js:47-55, 127-245` consumes it after a 1000 ms delay:
    - fills the customer and vehicle text;
    - picks the customer by exact name+phone (else shows the code·name - phone text) and the car by `plate_no`;
    - clears existing items;
    - adds one item row per part (product name = description, part number, quantity, **price blank**) and one labour row per labour task (description, price blank);
    - removes the session key and alerts "Repair order data loaded successfully!".
  - No RO id is carried over, so the invoice is not linked to the RO and the RO status is not changed.
- **Delete** (`:388-424`): `confirm("Are you sure you want to delete this repair order? This action cannot be undone.")`, then `APIHelper.delete('/api/repair-orders/<id>')`.
  - **That route does not exist.** The backend route is `DELETE /api/repair-orders/<id>/delete` (`repair_order_routes.py:598`). Only GET and PUT exist on `/repair-orders/<id>`, so the UI call gets 405 and toasts "Error occurred while deleting repair order." **Delete is broken in the current UI.**
  - What the backend delete does when reached:
    - 403 for a completed order unless admin;
    - for each part with `inventory_id` and qty > 0, adds the quantity back to stock and logs a `received` transaction "Inventory restored from Repair Order #X deletion". Parts deducted through a part-number or name match (no `inventory_id` stored) are **not** restored, and restore errors are only printed;
    - deletes parts, labour and the RO;
    - logs `DELETE`.

### 5. Status workflow (rules for the whole feature)
- **UI values:** `received`, `diagnosis`, `repair`, `testing`, `complete` (`statusOrder`, `:55-61`). Any value can be chosen from any status, forwards or backwards.
- **Server** (`:374-432`):
  - returns 404 if the order is not found;
  - returns **403 if the current status is `complete` and the user is not admin** (only admins can reopen or move a completed order). Non-admins can set `complete`;
  - requires `status`, but accepts **any string** (no whitelist);
  - stores `timeline[new_status] = {date: <client ISO timestamp>, time: 'HH:MM'}`. The time comes from the parsed timestamp, i.e. UTC from `toISOString`; on parse failure it falls back to server now. Re-entering a status **overwrites** its earlier entry;
  - sets `updated_at` and `updated_by_user`, logs `UPDATE_STATUS` "Status updated from X to Y";
  - returns `{message, current_status, status_timeline}`.
- **Side effects:** no stock effect and no WhatsApp message. `WhatsAppNotifier.send_repair_status_update` exists (`whatsapp_notifications.py:242`) but is **never called**. No automatic invoice.
- **Effects of `complete`:** it enables the "Generate Invoice" button and the non-admin lock (edit, delete and status change, both client and server).

### 6. Search
- Search button, or Enter (`keypress`) in either input, runs `performSearch`.
  - If both inputs are empty: warning toast "Please enter a keyword or ID to search".
  - Otherwise: `loadRepairOrders(activeStatus, {keyword, id})`, combined with the active status tab (read from the `.active` class).
- Clear empties both inputs, hides ×, and reloads the active status.
- Clicking a status tab reloads **without** the search params, even though the inputs still show text (quirk).

### 7. Notifications
- A local `showNotification(message, type)` overrides the shared one. It shows a fixed top-right toast for 3 s with slideIn/slideOut keyframes injected into `<head>`.
- Colours: success `#28a745`, error `#dc3545`, warning `#ffc107` with black text, info `#17a2b8` (`:523-582`).

### 8. Persisted state and navigation
- Back-button mapping, from `from` or `localStorage.lastPage`, default `admin`:

  | Source | Back goes to |
  |---|---|
  | `home` | `home.html` |
  | `invoiceSystem` | `invoiceSystem.html` |
  | `dashboard` | `invoiceSystem.html` |
  | `inventory` | `inventory.html` |
  | `admin` | `home.html` |
  | anything else | `home.html` |

- Sets `localStorage.lastPage="repair-orders-management"`. If a `from` param is present, also stores it as `localStorage.originalFrom` (used by the template's Back).
- `sessionStorage` keys written: `repairOrderData`, `repairOrderId` (View); `repairOrderForInvoice` (Generate Invoice).
- No polling, keyboard shortcuts or unsaved-changes handling, apart from Enter-to-search.

### 9. Calculations
None. `partsTotal`, `labourTotal` and `totalEstimate` are hard-coded to 0 and unused. `formatCurrency` is unused.

### 10. Quirks
- Broken delete route (§4).
- `?id=` from the inventory history link is ignored.
- Server search suggestions are ignored.
- xlsx is loaded but unused.
- Card HTML is built with unescaped interpolation of customer data (XSS risk).
- Dead `else` branch after `APIHelper.put` (`res.text()` on a falsy value).
- The status select keeps the new value after a failed update.

---

## repair-order-template.html — Printable Repair Order

### 1. Purpose, loading, access
- **Purpose:** a printable A4-width job card.
- **URL:** `/repair-order-template.html` (`app.py:245`).
- **No auth check:** auth_jwt is not loaded.
- **Data source:** `sessionStorage.repairOrderData` plus `repairOrderId` only, written by the create flow (the submitted payload) or by the management View button (the full GET response).
  - There is **no fetch by id and no URL id param**.
  - Both keys are **removed after rendering** (`:352-353`), so a refresh shows raw `{PLACEHOLDER}` text.
  - If the data is missing, nothing is filled in and placeholders show.
- **Rendering:** inline script (`:187-358`). `repairOrderTemplateUtils.js` is loaded but its `initializeRepairOrderTemplate` and helpers are **never called** (dead code).

### 2. Printed fields
| Section | Content |
|---|---|
| Header | Logo; "Repair Order"; "RO #{id}"; date = `new Date(created_at || now).toLocaleString()` (browser default locale). The create flow has no `created_at`, so it shows the current time |
| Workshop Information | Hard-coded: "Address: 38-A, Kamahan Lidher Road, Lahore", "Email: service@germanato.com", "Phone#: +92 321 4854641" |
| Customer & Vehicle Information | Customer ID (`customer_code`, "N/A" after create), Customer Name, Address, Phone#, Reg#, Made, Mileage (`"{n}km"`), VIN#, Color, Chassis#. Every missing value shows "N/A" |
| Problem Description | text |
| Parts Required table | Part Description, Part Number ("N/A" if empty), Quantity, Status (default "Pending"). Empty list leaves an empty body |
| Labour Tasks table | Task Description, Status |
| Work Status | 5 circles (Received, Diagnosis, Repair, Testing, Complete). Only `current_status` gets `.current` (blue), defaulting to received. No dates |
| Assigned Worker | `worker_name`, or "Not assigned" (comma-joined for multiple workers) |
| Repair Order History Logs | Columns Timestamp, User, Action, Details. Loaded with `fetch('/api/repair-orders/{id}/logs', {Authorization: 'Bearer ' + localStorage.token})`. The server returns `AppLog` rows for module `repair_orders`, newest first, each `{created_at 'YYYY-MM-DD HH:MM:SS', username, action, details, …}` (`repair_order_routes.py:698-708`). Missing username shows "system"; the action appears as a maroon badge. Empty result: "No edit history logs found for this repair order."; network error: "Failed to load history logs." (red) |
| Footer | "Thank you for choosing GermanATO!" plus a thank-you paragraph |

- **Logs are effectively broken:** auth stores the token as `accessToken`, not `token` (`auth_jwt.js:22,86`). The request is therefore unauthenticated; the error JSON has no `length`, so the page shows the "No edit history logs found" message.
- All values are inserted with `innerHTML` in table rows, unescaped.

### 3. Print and layout behaviour
- **No print button, no auto-print, and no `@media print` rules.** Printing relies on the browser's own print. The fixed Back button will appear on the printout.
- `* { print-color-adjust: exact }` keeps background colours when printing (`repair-order-template.css:7-8`).
- The container is `max-width: 210mm` (A4 width), centred.
- `≤768px`: header stacks, info boxes stack, the status timeline becomes a vertical list of rounded rows (connector line hidden), and cells are centred.
- `≤480px`: smaller Back button and smaller table fonts.
- An inline `≤600px` rule hides `.download-button`, which does not exist (leftover).
- The CSS still contains unused `.estimate-*` styles from the removed pricing.

### 4. Back button
- Source: the URL `from` param, else `localStorage.lastPage`, else `repair-orders-management`.

  | Source | Back goes to |
  |---|---|
  | `repair-order` | `repair-order.html` (a blank new form) |
  | `repair-orders-management` | `repair-orders-management.html?from={localStorage.originalFrom || 'admin'}` |
  | `admin` | `admin.html` |
  | `home` | `home.html` |
  | anything else | `repair-orders-management.html` |

- Sets `localStorage.lastPage="repair-order-template"`, but only when data was present.

### 5. repairOrderTemplateUtils.js (dead library)
- Exposes `window.RepairOrderUtils`: formatCurrency, formatDate, updateStatusTimeline (writes `#{status}-date`, ids that do not exist), calculateTotals (always 0), populatePartsTable / populateLabourTable (with "No parts required" / "No labour tasks" rows and `.status-badge` classes), updateEstimate (no-op), validateRepairOrderData (requires name, phone, reg), generateRepairOrderNumber (`RO{timestamp}{rand}`), save/load/clearRepairOrderData (the same sessionStorage keys), updateVehicleCondition (`fuel-level`, `exterior-condition`, `interior-condition`, `personal-items`), updateProblemAndDiagnosis (`diagnosis-plan`), updateNotes (`repair-notes`), initializeRepairOrderTemplate.
- None are called. The element ids they target (vehicle condition, diagnosis plan, notes, status dates) are not in the HTML. They are **remnants of earlier intake, diagnosis, notes and pricing features**, so check with the business whether those should come back in the rewrite.

---

### Endpoints used

| METHOD | path | page/action |
|---|---|---|
| GET | /api/repair-orders?status&keyword&id&_t | management: list, filter, search |
| GET | /api/repair-orders/<id> | form: edit load; management: View, Generate Invoice |
| POST | /api/repair-orders | form: create |
| PUT | /api/repair-orders/<id> | form: update |
| PUT | /api/repair-orders/<id>/status | management: status select |
| DELETE | /api/repair-orders/<id> | management: Delete. **Route does not exist; the real one is DELETE /api/repair-orders/<id>/delete** |
| GET | /api/repair-orders/<id>/log | management: History (DocumentLog) |
| GET | /api/repair-orders/<id>/logs | template: history logs table (sends the wrong token key) |
| GET | /api/repair-orders/assignable-workers | form: worker picker |
| PUT | /api/repair-orders/<id>/parts/<partId>/status | backend only, unused by UI |
| PUT | /api/repair-orders/<id>/labour/<labourId>/status | backend only, unused by UI |
| DELETE | /api/repair-orders/<id>/delete | backend only; restores stock; not reachable from UI |
| GET | /api/inventory | form: preload inventory for matching (first page of 50 only) |
| GET | /api/inventory/search?q= | form: part row search |
| GET | /api/invoice/<quoteId> | form: prefill from quote |
| (via CustomerCarUtils) customers/cars list, create, update | /api/customers…, /api/cars… | form: pickers, modals, write-back of customer and car on every save |
| — | invoice.html?from=repair-order (sessionStorage `repairOrderForInvoice`) | management: Generate Invoice handoff |

### Files read
| File | Lines |
|---|---|
| frontend/repair-order.html | 568 |
| frontend/repair-orders-management.html | 149 |
| frontend/repair-order-template.html | 361 |
| static/js/repairOrder.js | 2095 |
| static/js/repairOrdersManagement.js | 711 |
| static/js/repairOrderTemplateUtils.js | 324 |
| static/css/repair-order.css | 965 (behavioural rules read: dropdown/z-index, modal, readonly, grids, responsive 768/480; purely cosmetic rules not read line by line) |
| static/css/repair-order-template.css | 448 |
| repair_order_routes.py | 707 |
| repair_order_inventory_utils.py | 397 |
| inventory_transaction_utils.py | 272 |
| document_links.py | 115 |
| hr_routes.py | 1085 (lines 1-260, worker routes, as scoped; workers actually come from `/api/repair-orders/assignable-workers`) |
| Cross-checks (excerpts) | jwt_auth.py (role permissions, PATH_PERMISSIONS), models.py (RepairOrder, Part, Labour), api-helper.js (412-540: throws on non-2xx), auth_jwt.js (token keys, requirePageAccess), createInvoice.js (40-60, 120-245: RO-to-invoice), inventory_routes.py (pagination and search limits), documentLog.js, pendingQuotes.js, inventoryHistory.js, app.py routes, whatsapp_notifications.py:242 |
