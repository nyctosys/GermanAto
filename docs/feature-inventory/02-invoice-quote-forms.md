# Feature inventory: creating and editing invoices and quotes

Scope: `frontend/invoice.html`, `frontend/quote.html`, and the JS they load: `createInvoice.js`, `createQuote.js`, `editInvoice.js`, `invoiceShared.js`, `customer-car-utils.js` (also used by repair-order.html). It also covers the backend rules these pages rely on.

**Summary of the most important findings (full list in §11):**
- **Price autofill is broken.** The inventory API never returns `price`, so picking a part leaves the Price box blank (`inventory_routes.py:307-333`).
- **"Check & Deduct Inventory" fails for most users and most rows.**
  - Accountants are always refused.
  - Any row without a part number makes the server crash.
  - It is not tied to the invoice and can be run twice.
- **The balance on screen and the saved balance differ when tax is on.** The screen leaves tax out; the server adds it.
- **Every save overwrites the customer and car master records with the form's text.** In edit mode that is the invoice's old text. It can also move a car to a different owner.
- **Bringing in a repair order with several labour rows puts only the last description in, and only in the last row.**

---

## invoice.html — "GermanATO - Invoice/Quote Generator"

### 1. Purpose, URL, modes, access

- **Purpose:** create a new Invoice, or edit an existing Invoice or Quote.
- **Served at** `/invoice.html` by `app.py:148-151`, with no server-side auth on the HTML.
- **How the mode is chosen** (`invoice.html:575-586`): an inline `<script type="module">` reads `?id`.
  - `id` present → `import("/static/js/editInvoice.js")` (edit mode).
  - Otherwise → `import("/static/js/createInvoice.js")` (create mode).
- **Edit mode retitles the page** (inline script `invoice.html:559-565`):
  - h1 → "Edit Invoice/Quote"
  - subtitle → "Edit existing invoice or quote"
  - document title → "GermanATO - Edit Invoice/Quote"
- **Repair-order mode:** create mode with `?from=repair-order` pre-fills the form from `sessionStorage.repairOrderForInvoice` (see §9).
- **There is no "view" mode.**
- **Document type in edit mode** comes from the record (`data.type_of`), not from the page. A quote opened at `invoice.html?id=N` stays a quote, but it shows the Advance field and that value is sent.
- **Who can access:**
  - Neither page calls `auth.requirePageAccess(...)`. Any signed-in user can open them.
  - A user with no or expired token is sent to `login.html` on the first API 401 that cannot be refreshed (api-helper).
  - Sidebar entries "New invoice" (`/invoice.html`) and "New quote" (`/quote.html`) need the `invoice` permission (`app-shell.js:55-56`). That only controls visibility.
  - Server rules:
    - `POST /api/add` → roles admin or accountant.
    - `GET /api/invoice/<id>` → any logged-in user.
    - `PUT /api/invoice/<id>/update` → `can_edit_invoice` (`routes.py:117-153`): any active user. Admin and accountant always. Other roles only within 1 day of `created_at`, and only for type invoice; quotes have no time limit.
  - **The client is stricter than the server in edit mode** (`editInvoice.js:132-145`): only `role === "admin" || "accountant"` (read from `localStorage.user`) may edit. Anyone else sees "You cannot edit invoices older than 1 day. Please contact an administrator." (a misleading message) and is sent back with `window.history.back()`. `isInvoiceOlderThanOneDay()` (`editInvoice.js:124-129`) is dead code.
- **Inbound links:**

  | From | URL |
  |---|---|
  | invoiceSystem.html | `invoice.html?from=invoiceSystem` |
  | app-shell sidebar | `/invoice.html` |
  | invoiceManagement.js:334 (Edit) | `invoice.html?id=<id>` |
  | repairOrdersManagement.js:371 ("Generate Invoice") | `invoice.html?from=repair-order` |

  Before the repair-order link navigates, `GET /api/repair-orders/<id>` is called and stored in `sessionStorage.repairOrderForInvoice`.
- **`?new=1`** is handled by app-shell (`handleNewParam`, app-shell.js:361-380): it focuses the first form input, which is `#customer-select`.

### 2. Layout / sections (in order)

1. **Header** (`.top-header`): logo, h1 "Invoice/Quote Generator", subtitle "Create invoices and quotes for customers", Back link `#back-btn`. app-shell may slim the header.
2. **`<form id="invoice-form" method="post">`** containing these `.section-card`s:
   1. **Customer Information**
      - `#customer-select` searchable input, its dropdown `#customer-dropdown-options`, and "Add Customer" `#add-customer-btn`.
      - Hidden `#customer-details` panel with an "Edit" button `#edit-customer-btn`.
      - Readonly fields: `#customer_name`, `#customer_address`, `#customer_phone` (type tel).
   2. **Vehicle Information**
      - `#car-select` with `#car-dropdown-options` and "Add Car" `#add-car-btn`.
      - Hidden `#car-details` panel with "Edit" `#edit-car-btn`.
      - Readonly fields: `#customer_reg` (Registration Number), `#customer_made` (Make & Model), `#customer_mileage`, `#customer_vin` (VIN), `#customer_color`, `#customer_chasis` (Chassis Number).
   3. **Invoice Items:** `#items-container` (dynamic rows) and buttons "Add Item" `#add-item` and "Add Labour" `#add-labour`.
   4. **Financial Summary**
      - Tax toggle `#tax-toggle`, label "Include Tax (GST/PST 17%)".
      - `#tax-amount-display` (hidden) showing "Tax Amount: `#tax-amount`".
      - "Advance Payment" `#advance` (class `advance`).
      - "Discount" `#discount`.
      - Summary lines `#total-amount` ("Net Total: 0.00 PKR") and `#total-balance` ("Balance: 0.00 PKR").
   5. **Actions**
      - `.inventory-deduction-section`: button "Check & Deduct Inventory" `#deduct-inventory-btn`, with the info text "This will check stock availability and deduct items from inventory. You'll be warned about insufficient stock."
      - `.btns-submit` containing submit button "Generate Invoice".
3. **Footer:** "© 2025 GermanATO."
4. **Customer Modal `#customer-modal`**, title `#customer-modal-title`, `<form id="customer-form">`:
   - `#modal-customer-name` (text)
   - `#modal-customer-phone` (tel)
   - `#modal-customer-address` (textarea)
   - Cancel `#cancel-customer`, Save (submit), close X `#close-customer-modal`.
5. **Car Modal `#car-modal`**, title `#car-car-modal-title` → actually `#car-modal-title`, `<form id="car-form">`:
   - `#modal-car-customer` (`<select>`, first option "Select Customer")
   - `#modal-car-make`, `#modal-car-model`, `#modal-car-plate` ("Plate Number"), `#modal-car-mileage` (all text)
   - `#modal-car-vin` ("VIN *", `required`, `maxlength=17`, placeholder "17-character VIN")
   - `#modal-car-color` (placeholder "e.g. White, Black, Red")
   - `#modal-car-chasis` (placeholder "Chassis #")
   - Cancel `#cancel-car`, Save, X `#close-car-modal`.

**Scripts, in load order:** theme.js (head), inline back-button script, notification-utils.js, auth_jwt.js, `../static/js/app-shell.js`, api-helper.js, phone-formatter.js, customer-car-utils.js, then the module loader.

### 3. User actions and fields

#### Back button (inline, `invoice.html:532-557`)
- `fromPage = ?from || localStorage.lastPage || "invoiceSystem"`.
- Mapping: `invoiceSystem` → invoiceSystem.html; `admin` → admin.html; `home` → home.html; `invoice-management` → invoice-management.html; anything else, including `repair-order` and `invoice`, → invoiceSystem.html.
- It then writes `localStorage.lastPage = "invoice"`. So `lastPage` read here is always whatever the previous page wrote.

#### Customer selection (`invoiceShared.js:138-198`, `325-381`)
- **Load:** `loadCustomers()` → `CustomerCarUtils.loadCustomers()` → `GET /api/customers`. The result goes into `state.customers` and `window.customers`.
- **Options:** the dropdown holds every customer as a `.dropdown-option` with `data-value=id`. Text is `"{code} · {name} - {phone}"`; the code part is omitted if there is no code. The code is `CN%03d` from the id (`models.py:214-224`).
- **Opening:** clicking the input shows the dropdown, removes readonly, focuses (and re-focuses after 100 ms) and adds `.dropdown-active` to the card (raises its z-index). `touchstart` also removes readonly and focuses, so the mobile keyboard opens.
- **Search:** on `input`, a case-insensitive substring filter on the option text (code, name or phone) hides non-matching options. It is client-side only and there is no server search. Typing does not open a closed dropdown.
- **Select:** click an option → input text set to the option text, dropdown hidden → `handleCustomerChange(parseInt(id))`.
- **`handleCustomerChange(id)`:**
  - Sets `state.selectedCustomerId` and clears `state.selectedCarId`.
  - Fills `#customer_name`, `#customer_address`, `#customer_phone` from the record and shows `#customer-details`.
  - Clears `#car-select`, hides `#car-details` and blanks all six vehicle fields.
  - Rebuilds the car dropdown with only this customer's cars.
  - With a falsy id it clears everything.
- **Close:** a click anywhere outside the input or dropdown closes both dropdowns (document listener).
- **Free text:** typing a name without picking an option sets no id and fills no detail fields. Validation then fails (§5). In practice a customer must be picked from the list.

#### Car selection (`invoiceShared.js:89-133`, `201-294`, `384-410`)
- **Load:** `loadCars()` → `GET /api/cars` → `state.cars` and `window.cars`.
- **Server caveat:** `GET /api/cars` uses `Car.query.join(Customer)`, an inner join (`car_routes.py:270`). **Cars with no owner are never returned.**
- **Clicking or touching `#car-select` with no customer selected** shows `alert("Please select a customer first before selecting a car.")`.
- **Otherwise** the dropdown is rebuilt with only cars where `car.customer_id === state.selectedCustomerId`:
  - Option text: `"{make} {model} - {plate_no}"`, `data-value=car.id`.
  - If there are none: an italic grey option "No cars found for this customer".
  - With no customer: "Please select a customer first", and `#car-select` is cleared.
- **Search:** `input` rebuilds the list, then filters by substring, and opens the dropdown if any option is visible.
- **`handleCarChange(id)`:** fills `#customer_reg=plate_no`, `#customer_made="{make} {model}"`, `#customer_mileage=mileage`, `#customer_vin=vin||""`, `#customer_color=color||""`, `#customer_chasis=chasis_no||""`, then shows `#car-details`.
- **Quirk:** the placeholder options ("No cars found…", "Please select a customer first") are clickable `.dropdown-option`s with no `data-value`. Clicking one puts that message text into `#car-select`, and `handleCarChange(NaN)` clears the car. The "car selected" check then passes, but the detail-field check fails.

#### N/A handling
- `CustomerCarUtils.createCustomer` and `updateCustomer` send `"N/A"` for any blank name, phone or address.
- `createCar` and `updateCar` send `"N/A"` for blank make, model, plate_no, mileage, color and chasis_no.
- The server treats `"N/A"` as "not provided": validation skips it and phone validation is skipped for `"N/A"`.

#### Add / Edit Customer modal (`invoiceShared.js:825-935`)
- **"Add Customer":**
  - Sets `window.editingCustomerId = null` and the title to "Add Customer".
  - Resets the form and opens the modal (`style.display="block"` plus class `active`; CSS makes it `display:flex`).
- **"Edit" (customer):**
  - Needs a selected customer; otherwise `alert("Please select a customer first.")`, or "Customer not found." if the id is not in the list.
  - Title becomes "Edit Customer CN00X" (or "Edit Customer" with no code), and the three fields are pre-filled.
- **Fields:** none are required and there is no validation. Phone is auto-formatted by phone-formatter (`modal-customer-phone` is in its id list): `0xxx xxxxxxx`, `+92 xxx xxxxxxx`, a leading 0 added to bare numbers, and length capped.
- **Save:**
  - Edit → `PUT /api/customers/{id}` with `{name, phone, address}`, blanks becoming "N/A".
  - Create → `POST /api/customers` with the same shape.
  - The server returns 409 "Customer already exists" when name, phone and address all match exactly. Its `details` string is not shown because api-helper only appends array details.
  - Success: `showNotification` is not defined on this page, so an `alert("Customer created/updated successfully!")` appears. The modal closes, `loadCustomers()` re-runs, the three detail fields are filled from the returned record and `#customer-select` text is set.
  - A new customer is then selected with `handleCustomerChange(newId)`, which clears the car.
  - Editing intends to call `handleCustomerChange` too, but `closeCustomerModal()` nulls `window.editingCustomerId` before the comparison at `invoiceShared.js:920`. **That branch never runs.** The fields are updated directly and the car selection survives.
  - Error: `alert("Error: " + message)`.
- **Closing:** X, Cancel, or a click on the modal backdrop (`window` click where `target === modal`). Closing resets the form.

#### Add / Edit Car modal (`invoiceShared.js:938-1100`)
- **"Add Car":**
  - Title "Add Car".
  - `#modal-car-customer` is filled with every customer (same option text format) and pre-set to the selected customer.
  - The form is reset and the owner re-applied after the reset. The button works even with no customer selected.
- **"Edit" (car):**
  - Needs `state.selectedCarId`; otherwise "Please select a car first." or "Car not found."
  - Title "Edit Car"; every field is pre-filled from the car, including the owner.
- **Validation on save:**
  1. Owner is required. With none: "Choose which customer this car belongs to. Without it the car will not appear when you pick that customer later." and focus moves to the select (`invoiceShared.js:1024-1033`).
  2. VIN is required natively (`required`) and again in `createCar`/`updateCar` ("VIN is a required field"). Max 17 characters (input `maxlength`; DB `String(17)`).
- **Payload:** `{customer_id, make, model, plate_no, mileage, vin, color, chasis_no}`, all trimmed. Blanks become "N/A"; `customer_id` is parsed to int and omitted if falsy.
- **Endpoints:**
  - Edit → `PUT /api/cars/{id}`.
  - Create → `POST /api/cars`. The server returns 409 "Car with this VIN already exists" for a duplicate VIN on create only; duplicate plates are allowed. Update does not check VIN uniqueness.
- **Success:**
  - alert "Car created/updated successfully!", modal closes, `loadCars()` re-runs.
  - The six vehicle fields are filled from the returned car (make and model joined with a space).
  - If a customer is selected, the car dropdown is rebuilt. A new car whose `customer_id === selectedCustomerId` has its `#car-select` text set to `"{make} {model} - {plate}"` and is selected with `handleCarChange`.
  - The edit branch has the same null-before-compare bug as the customer modal, so `#car-select` text is not refreshed after an edit.

#### Line items (`invoiceShared.js:419-570`)
- **"Add Item"** appends a `.item` div:
  - Label `<p><i>{counter}:</i></p>`.
  - `.searchable-dropdown` containing `input.product-name` (placeholder "Search Part/Lubricant...", `required readonly`) and an options box, initially "Type to search for items...".
  - `input.part-number` ("Part Number", readonly, only ever set from a picked result).
  - `input.quantity` (number, `min=1`, required).
  - `input.price` (number, `min=0`, `step=0.01`, required).
  - "Delete" button.
- **"Add Labour"** appends a `.item` with `input.labour-description` ("Labour Description", required), `input.price` (`min 0`, `step 0.01`, required) and "Delete".
- **No rows exist by default.**
- **Native validation** (the form has no `novalidate`) blocks submit for empty quantity or price, quantity < 1, negative price, or empty labour description. Readonly inputs are not validated, so `required` on a readonly `product-name` has no effect.
- **Inventory search per item row:**
  - Clicking `.product-name` opens the box and makes the input editable.
  - On `focus`, if there are already 2 or more characters, it searches immediately.
  - On `input`: an empty value hides the box; under 2 characters does nothing; otherwise a 300 ms debounce then `GET /api/inventory/search?q=<term>`. The server default `limit` is 200 and the maximum 500; it matches part_number, barcode and manufacturer_part_number, plus a hyphen/space-insensitive code match, name, description, location and category, sorted by name.
  - While searching the box shows "Searching..."; then "No items found" or "Error searching items" as appropriate.
  - **Option label** (`inventoryOptionLabel`, `invoiceShared.js:650-658`): `name · manufacturer_part_number · PKR price`, with the price only shown if > 0. Attributes: `data-value=item.name`, `data-price=item.price`, `data-part-number=item.part_number` (the internal PN, e.g. PN001).
  - **Picking an option** sets `product-name = name`, `price = data-price`, `part-number = data-part-number`, hides the box, makes the input readonly again, and calls `updateTotal()`.
  - **BUG: price is never filled.** `inventory_item_to_dict` (`inventory_routes.py:307-333`) has no `price` key, so `data-price="undefined"`, the number input rejects it, and Price is left blank. The PKR part of the label never shows. Staff must type every price.
  - **Free text:** after clicking, the user can type a product name that is not in inventory and click away. The input goes back to readonly but keeps the text, so custom part names are allowed. `part-number` is not cleared when the name is retyped, so a stale part number can remain.
  - Clicking an informational option ("Type to search…", "Searching...", "No items found") sets the name and price to empty.
  - Each item row adds its own `document` click listener that closes its box (the listeners pile up).
- **Quantity** is read with `parseInt` (1.5 becomes 1); **price** with `parseFloat`.
- **Recalculation:** quantity and price `input` events on item rows, and price `input` on labour rows, call `updateTotal()`.
- **Delete** removes the row, calls `updateTotal()` and `updateBalance()`, then `state.counter--`. Row labels are fixed text, so after deleting a middle row the next row added repeats an existing number.
- **Tab key** (`invoiceShared.js:463-473`): Tab without Shift in the last `<input>` of any row (its Price) is blocked by `preventDefault`. A new row of the same type is added at the end and its first input is focused. You cannot Tab out of a row's price box to the next field.
- **Duplicates:** no duplicate-row detection; the same part can be added several times.
- **Stock:** nothing is checked while adding rows. Stock is only checked via the deduct button.
- **Unused data:** `loadInventory()` fetches `GET /api/inventory` (first page, 50 items). `refreshDropdownOptions` is only called for rows that already exist when the load finishes, and none do, so that fetch does nothing useful apart from setting `window.inventoryItems`.

#### Financial fields
- **Tax toggle** `#tax-toggle` (checkbox, default off). On `change` it only calls `updateTaxDisplay()`.
- **Advance** `#advance` (number, no min, no step, empty default, placeholder "Advance"). On `input` → `updateBalance()`. A negative value passes the client, then the server returns 400 "Advance amount cannot be negative".
- **Discount** `#discount` (number, default 0, `min=0`, `step=0.01`). On `input` → `updateBalance()`. Negative values are blocked by native validation; the server does not validate discount.

#### Check & Deduct Inventory (`invoiceShared.js:706-820`) — invoice page, create mode only

1. **Collect rows:** every row with a product name, quantity > 0 and price ≥ 0 becomes `{product_name, part_number|null, quantity, price}`. If there are none: "No items found to deduct from inventory."
2. **Check:** `POST /api/inventory/check-stock` with `{items}` (any logged-in user). For each row the server looks up `Inventory.part_number == part_number`, then name `ILIKE %name%` (first hit), then description `ILIKE` (first hit). It returns `{insufficient_items: [not found], available_items: [{..., inventory_id, available_quantity, inventory_part_number, insufficient_stock}]}`.
3. **Confirm:** if any row is short or not found, a `confirm()` lists:
   - "Items with insufficient stock: • name (PN): Required q, Available a"
   - "Items not found in inventory: • name (PN): Required q"
   - "Items with sufficient stock: • name (PN): q units"
   - then "WARNING: Proceeding will attempt to deduct ALL items. Items with insufficient stock will go negative, and items not found will be skipped. Do you want to proceed?"

   Cancel stops. If everything is in stock, there is no confirmation.
4. **Deduct:** `POST /api/inventory/deduct-items` with `{items}`. The client does not send `inventory_id`, so the server repeats the same fuzzy lookup plus an exact-name fallback. It subtracts the quantity (negative stock allowed) and logs `log_issue_out` with reference "Manual deduction - {name}".
5. **Report:** an alert with "Inventory deduction completed!", "Successfully deducted: • name (PN): q units (New stock: n)" and "Could not deduct: • name: reason".

**Problems with this action:**
- `deduct-items` is limited to **admin and inventory_manager** (`inventory_routes.py:1146`). **Accountants, who can create invoices, always get 403.**
- **Server crash on rows with no part number:** both endpoints call `item_data.get('part_number','').strip()`, but the client sends `part_number: null` for rows without one. `None.strip()` raises, giving **500 "Internal server error"** for any row without a part number (free-text or repair-order parts).
- **Not linked to the invoice:** it runs on unsaved form data, is not recorded against the invoice, and can be clicked repeatedly, deducting each time.
- **Fuzzy matching:** `ILIKE %name%` can pick the wrong item when names repeat (the code itself notes thirteen items named "BMW OIL FILTER").
- **Stock is otherwise untouched:** the server no longer deducts stock on invoice create or on quote→invoice convert (code commented out, `routes.py:256-267`, `744-755`). This button is the only path.

### 4. Client-side calculations (exact)

**`updateTotal()`** (`invoiceShared.js:578-596`):
```
total = Σ over .item rows:
          if row has .quantity: (parseInt(quantity)||0) * (parseFloat(price)||0)
          else (labour):        (parseFloat(price)||0)
#total-amount = "Net Total: " + total.toFixed(2) + " PKR"
then updateBalance(); updateTaxDisplay();
```

**`updateBalance()`** (`invoiceShared.js:599-610`):
```
total   = parseFloat(#total-amount text stripped to [\d.-])
advance = parseFloat(.advance) || 0      (0 if no .advance element, i.e. quote page)
discount= parseFloat(#discount) || 0
balance = total - advance - discount     ← TAX NOT INCLUDED
#total-balance = "Balance: " + balance.toFixed(2) + " PKR"
```
Balance can go negative; nothing warns.

**`updateTaxDisplay()`** (`invoiceShared.js:613-628`): if the toggle is checked, `tax = total * 0.17` (on items plus labour, before discount), shown as `"{tax.toFixed(2)} PKR"` in `#tax-amount`. Otherwise the display is hidden. The 17% rate is hard-coded.

**Values sent** (`collectFormData`, `invoiceShared.js:1156-1233`), all re-read from the rendered text:
- `net_total` = Net Total text
- `balance` = Balance text
- `tax_amount` = `#tax-amount` text if `include_tax`, else 0

`#tax-amount` is only refreshed by `updateTotal` or by toggling, so it reflects the last recalculation.

**Server recalculation** — the client's `net_total` and `balance` are ignored:
- `POST /api/add` (`routes.py:183-194`):
  - `total = round(Σ price*int(qty) + Σ labour.price, 2)`; `net_total = total`.
  - `balance = round(total + (include_tax ? tax_amount : 0) - discount - advance, 2)`.
  - `tax_amount` is taken as sent by the client.
- **The balance shown on the page differs from the saved balance by the tax amount when tax is on.**
- `PUT update` (`routes.py:538-548`): the same, minus `paid_amount` already recorded, and tax is only added if `include_tax and tax_amount > 0`.
- **Status** (`invoice_math.calculate_invoice_status`):

  | Condition | Status |
  |---|---|
  | Quote | `pending` |
  | Invoice, paid (`advance + paid_amount`) ≤ 0 | `unpaid` |
  | Invoice, paid ≥ due (`net_total + tax if include_tax - discount`) or balance ≤ 0 | `paid` |
  | Otherwise | `partially_paid` |

- **Rounding:** the client uses `toFixed(2)` for display only; the server uses `round(...,2)`.

### 5. Submit / save flows

**Validation** (`validateFormData`, `invoiceShared.js:1236-1266`), shown with `alert`. It runs after native HTML validation (which needs `#customer-select` and `#car-select` non-empty, plus the row constraints):
- `#customer-select` empty → "Please select a customer."
- `#car-select` empty → "Please select a car."
- Any of `customer_name`, `customer_address`, `customer_phone`, `customer_reg_no`, `customer_made`, `customer_mileage` empty, or no valid items and no labour → "Please ensure all customer and car details are filled, and add at least one valid item or labour."
- VIN, color and chassis are optional.
- **Note:** `"N/A"` counts as filled. A blank master address is stored as "N/A", so the check passes.

**Which rows are sent:** a row is an item if `productName && qty>0 && price>=0`. Otherwise it is labour if `labourDescription && price>=0`. Other rows are silently dropped.

**Payload**, used for both create and update:
```
{ customer_id: state.selectedCustomerId|null, car_id: state.selectedCarId|null,
  customer_name, customer_address, customer_phone, customer_reg_no, customer_made,
  customer_mileage, customer_vin, customer_color, customer_chasis,
  balance, advance, discount,
  items:[{product_name, part_number|null, quantity:int, price:float}],
  labours:[{description, price}],
  include_tax: bool, tax_amount: number, net_total: number,
  type_of: "Invoice" | "Quote" }
```

**Create invoice** (`createInvoice.js:81-124`):
1. `updateCustomerAndCarRecords(formData)` runs first (see below).
2. `POST /api/add` with `type_of: "Invoice"`.
3. **Success** (201, `{invoice_id, total, balance, whatsapp_sent, ...}`):
   - `sessionStorage.invoiceData = JSON(payload)`, `sessionStorage.invoiceId = id`, `sessionStorage.documentType = "invoice"`.
   - Navigate to `invoice-template.html?from=invoice&id=<id>`, then `resetForm()`.
4. **Errors:** `alert(error.message)`, which includes "Validation failed" plus a list of server details. api-helper also shows its own error state. There is no double-submit lock in this module apart from the api-helper ones (in-flight de-duplication and button lock).

**`updateCustomerAndCarRecords`** (`invoiceShared.js:1269-1308`) runs before every create or update:
- **Customer:** if a customer is selected, `PUT /api/customers/{id}` with the form's name, phone and address (blanks → "N/A").
- **Car:** if a car is selected, `PUT /api/cars/{id}` with:
  - `make` = first word of `customer_made`, `model` = the rest (e.g. "Mercedes Benz C200" → make "Mercedes", model "Benz C200")
  - `plate_no`, `mileage`, `vin`, `color`, `chasis_no`
  - `customer_id` = the selected customer
- **Failures are only logged to the console.** A car with no VIN fails "VIN is a required field" before any request is sent, so that car record is silently never updated.
- **These updates commit even if the invoice save then fails.**

**Server-side rules for POST /api/add** (`routes.py:155-341`):
- **Validation** (`validate_invoice_data`, `routes.py:55-114`):
  - Phone must match `^(\+92\s?\d{3}\s?\d{7}|0\d{9}|0\d{3}\s?\d{6}|0\d{3}\s?\d{7}|\d{11}|\d{4}\s?\d{7})$` unless it is `"N/A"`. **A customer phone stored as e.g. `0300-1234567` blocks saving.** `#customer_phone` is filled programmatically, so phone-formatter does not reformat it.
  - `advance` ≥ 0.
  - At least one item or labour.
  - Item: name required, quantity > 0, price ≥ 0. Labour: description required, price ≥ 0.
- **Storage:** `type_of` is stored lower-case.
- **Initial status:** `unpaid` for an invoice, `pending` for a quote, then recalculated.
- **Linking:** `apply_links` (`document_links.py`) sets `customer_id` (explicit id → exact name+phone → unique phone → unique name) and `car_id` (explicit id → VIN → plate, preferring this customer's car; must be unique). A car with no owner is adopted by the customer.
- **Audit:** `log_action(CREATE, 'invoices'|'quotes', ...)`.
- **WhatsApp:** a notification is sent automatically to the customer for **both invoices and quotes** (`whatsapp_notifier.send_invoice_notification`) and recorded in `WhatsAppNotification`, success or failure. A failure does not fail the save. The client ignores `whatsapp_sent`.

**Update** (`editInvoice.js:418-459`):
1. `type_of` comes from `window.editingDocumentType`, then `sessionStorage.documentType`, then "invoice".
2. `updateCustomerAndCarRecords`, then `PUT /api/invoice/{id}/update` with the same payload.
3. **Server** (`routes.py:457-576`):
   - Same validation.
   - Every field present in the payload is overwritten.
   - `apply_links` runs again.
   - **All items and labour rows are deleted and recreated.** The hidden `.item-id` / `.labour-id` inputs the client adds are never sent.
   - Totals and balance recalculated (minus `paid_amount`), `updated_by_user` and `updated_at` set, status recalculated, `log_action(UPDATE)`.
   - Returns `{invoice_id, total, balance}`.
   - No WhatsApp message on update.
4. **Success:** sessionStorage set as for create, then navigate to `invoice-template.html?from=invoice&id=<editId>`. It always uses `from=invoice`, even for quotes. No `resetForm`.
5. **Errors:** `alert(error.message)`.

### 6. Payments, status, convert, log
- **Payments:** none on these pages. Only the advance is captured, at create or edit.
- **Changing the advance during an edit** changes `advance` directly with no payment-history entry. Payments recorded later through `PUT /api/invoice/<id>/update-balance` (management page) are kept, because the update subtracts `paid_amount`.
- **Status** is never shown or edited here; the server calculates it on every save.
- **Not called from these pages:** quote→invoice conversion (`POST /api/invoice/<id>/convert`), `PUT /api/invoice/<id>/status`, `GET /api/invoice/<id>/log` and `PUT .../update-balance`. They belong to the management and pending-quotes pages.
  - Note for parity: convert hard-sets `status='unpaid'` without recalculating (`routes.py:741`) and does not touch stock.
- **`/api/search`** (with did-you-mean suggestions from `search_suggestions.py`) is not used by these pages either.

### 7. Print / PDF / WhatsApp / share
- No print, PDF or share buttons on these pages.
- After saving, the user lands on `invoice-template.html?from=invoice|quote&id=N`, which reads and then clears `sessionStorage.invoiceData`, `invoiceId` and `documentType`. That page is covered separately.
- WhatsApp: only the automatic server-side message on create (§5).
- invoice.css has **no `@media print` rules**.

### 8. Keyboard, scanner, focus, Enter, unsaved changes
- **Tab** on any row's Price adds a new row (§3).
- **Enter** in any text input of the main form submits it the browser's default way, running native validation and then the submit handler. There is no custom Enter handling.
- **No barcode-scanner support** is built in. A scanner typing into an item search box (after clicking it) will search, because the search matches barcodes. The scanner's trailing Enter will try to submit the form.
- **No autofocus**, except `?new=1` via app-shell.
- Clicking or touching the customer, car and product search inputs force-focuses them so the mobile keyboard opens.
- **Unsaved-changes warning** (app-shell `guardUnsavedChanges`): any user `input` inside a form marks the page dirty, except fields whose id or name contains "search" or "filter". `beforeunload` then prompts. The flag is cleared by form submit, reset, or any successful non-GET API call (`api:saved`). For example, saving a customer in the modal clears it.
- **Cmd/Ctrl+K** opens the app-shell command palette (shared).

### 9. Persisted state and navigation

| Key / param | Read / write | Purpose |
|---|---|---|
| `?id` | read | Edit mode (both pages) |
| `?from` | read | Back-button target; `repair-order` triggers the pre-fill |
| `?new=1` | read (app-shell) | Focus first field |
| `localStorage.lastPage` | read, then set to `"invoice"` (both pages) | Back-button fallback |
| `localStorage.user` | read | Client edit permission (role) |
| `sessionStorage.repairOrderForInvoice` | read, then removed | Repair-order pre-fill (invoice create only) |
| `sessionStorage.invoiceData` / `invoiceId` / `documentType` | written on save; `documentType` read as a fallback in edit | Hand-off to invoice-template |
| `window.customers`, `window.cars`, `window.inventoryItems`, `window.editingInvoiceId`, `window.editingDocumentType`, `window.editingCustomerId`, `window.editingCarId` | globals | Shared state between modules |

**Globals exported** by invoiceShared: `handleCustomerChange`, `handleCarChange`, `addItem`, `updateTotal`, `updateBalance`, `updateTaxDisplay`.

**Repair-order pre-fill** (`createInvoice.js:126-246`), which runs 1 s after init (`setTimeout`):
1. The customer and vehicle text fields are filled from `customer_name`, `customer_address`, `customer_phone`, `customer_reg_no`, `customer_made`, `customer_mileage`, `customer_vin`, `customer_color`, `customer_chasis`.
2. **Customer:** matched in `state.customers` by exact name and phone.
   - If found: `#customer-select` text is set and `handleCustomerChange(id)` runs. **That overwrites the details with the master record and clears all six vehicle fields that were just filled.**
   - If not found: only the `#customer-select` text is set (`customer_code` used if present) and no id. Validation then fails on whatever is empty.
3. **Car:** matched by `plate_no === customer_reg_no` (exact, with no owner check).
   - If found: `#car-select = "{make} - {plate}"` (a different format from the dropdown) and `handleCarChange(id)`.
   - If not found: the text is set but the vehicle fields stay **blank**, because step 2 cleared them, and `#car-details` stays hidden. The form cannot be submitted.
4. **Rows:** `#items-container` is cleared and the counter reset.
   - Each `parts[]` entry becomes an item row with `product_name = description`, `part_number`, `quantity`, and price blank. The user must enter prices, and native validation enforces it.
   - Each `labour[]` entry adds a labour row, filled in a 100 ms `setTimeout` that targets "the last `.item`". **BUG:** every labour row is created before any timeout fires, so all the timeouts write into the last row. Only the last labour description ends up in the last row, and the earlier labour rows stay empty.
5. Session key removed; `alert("Repair order data loaded successfully!")`. On an exception: "Error loading repair order data."

### 10. Edit-mode loading (`editInvoice.js:149-333`), shared by both pages
1. No `id` → alert "No invoice ID provided. Redirecting to invoice management." and redirect to `invoice-management.html` (unreachable from these pages, which only load editInvoice when `id` is present).
2. `loadCustomers()` and `loadCars()` without waiting, `await loadInventory()`, then `GET /api/invoice/{id}`.
   - The server also fills a missing color or chassis from the Car table by VIN, then plate.
   - Returns `customer_id`, `customer_code`, `car_id`, `created_at`, `paid_amount`, `status`, `payments_history`, and `items`/`labours` with ids.
   - A null response → "Failed to fetch invoice for editing."
3. Role check (§1).
4. `waitForData()`: polls every 50 ms until both customers and cars are loaded, for up to 4 s.
5. `fillDocumentFields(data)` paints the document's own stored text into the nine detail fields.
6. **Customer match order:** `data.customer_id`, then exact name and phone, then phone only, then name only. If matched: `#customer-select` text set and `handleCustomerChange`. After 100 ms:
   - `resolveCarForDocument` (`editInvoice.js:39-63`): `car_id`, then VIN (trimmed, upper-case, owner not checked), then plate with non-alphanumerics stripped and upper-cased, preferring the customer's car and then an ownerless car. **The ownerless fallback can never match**, because `/api/cars` excludes them.
   - If a car is found: `#car-select = "{make} {model} - {plate}"` and `handleCarChange`.
   - `fillDocumentFields(data)` runs again so the historical values win, and `#car-details` is shown.
7. **If no customer matches,** `#customer-select` and `#car-select` stay empty and the detail panels stay hidden even though their fields have values. Saving is blocked ("Please select a customer.") until the user picks one, which overwrites the historical text. If the customer matches but no car does, `#car-select` stays empty and saving is blocked with "Please select a car."
8. **Financial fields and rows:**
   - `.advance = data.advance || 0` (if the field exists), `#discount = data.discount || 0`.
   - `#tax-toggle.checked = include_tax`, then `updateTaxDisplay`.
   - Rows rebuilt from `items` (name, part_number, quantity, price, plus a hidden `.item-id`) and `labours` (description, price, plus a hidden `.labour-id`).
9. **Buttons and sections:** `.btns-submit` is replaced by one submit button, "Update Invoice" or "Update Quote".
   - The `.document-type-toggle` "Editing: Invoice/Quote" badge code is **dead**, because no such element exists.
   - `.inventory-deduction-section` is hidden.
10. `updateTotal()`. Tax is recalculated at 17% of the current total on save, replacing the stored `tax_amount`.
11. **Saving an edit writes the document's historical text back into the master records** (`updateCustomerAndCarRecords`): the customer's name, address and phone, and the car's plate, mileage, make/model, VIN, colour and chassis. **It can roll the customer and car back to how they were on the invoice date.**
12. **If the car was matched by VIN but belongs to another customer,** the car `PUT` sets `customer_id` to this invoice's customer. **The car is silently moved to that customer.**

### 11. Quirks, bugs, dead code (invoice.html scope)

**Bugs:**
- **Price autofill broken:** the inventory API returns no `price` (`inventory_routes.py:307-333`).
- **check-stock / deduct-items return 500 for rows without a part number** (`part_number: null` → `.strip()`; `inventory_routes.py:1092`, `1160`).
- **deduct-items forbidden for accountants** (403), although accountants can create invoices.
- **The balance shown leaves out tax; the server's balance includes it.**
- **Master customer and car records are overwritten on every save,** including with historical edit-mode values and "N/A"s. The make/model split on the first space corrupts multi-word makes. A car with no VIN is silently skipped.
- **A car matched by VIN in edit mode is moved to the invoice's customer.**
- **Repair-order labour pre-fill:** only the last description lands, in the last row.
- **Repair-order customer match:** wipes the pre-filled vehicle fields, and a car not found leaves the form blocked.
- **Row numbering:** the counter is decremented on delete, so numbers repeat.
- **Placeholder options in the car and item dropdowns are clickable** and write junk or empty values.
- **Modal edit branches** (customer and car) compare against an id that was already nulled, so they never run (`invoiceShared.js:920`, `1085`).
- **Car modal sends `customer_id`, so an edit can move a car to another owner.** The code then re-selects it on this form even if it now belongs to someone else (the branch is dead anyway).
- **The client edit check** blocks every role except admin and accountant, with a message about "older than 1 day". The server allows other roles for quotes, and for invoices less than 1 day old.
- **A customer phone in a format other than those the regex allows blocks saving** with a 400 error.

**Dead or wasted code and calls:**
- `isInvoiceOlderThanOneDay`, the `.document-type-toggle` code and the hidden `item-id` / `labour-id` inputs (never sent).
- The `loadInventory` → `/api/inventory` call is effectively useless.
- In `customer-car-utils.js`, `setupCustomerModal`, `setupCarModal` and the `loadCars(customerId)` branch (`/api/cars/customer/<id>`) are dead; see the customer-car-utils section.
- CSS `.wide-btn-submit[data-type="invoice"]{display:none}` and the `.document-type-toggle`/`.toggle-*` styles are left over from an earlier invoice/quote mode toggle.
- **`showNotification` is not defined** on these pages (notification-utils defines `showSuccess`, `showError`, `showInfo`, `showWarning`), so every modal message is an `alert`.
- `updateTaxDisplay` runs before `#tax-amount` is read only through `updateTotal`. If the toggle is ticked after the last edit, toggling recalculates it, so the value is consistent.

**Endpoint check:** every endpoint called by this page exists.

---

## quote.html — "GermanATO - Invoice/Quote Generator"

### 1. Purpose, URL, modes, access
- **Purpose:** create a new Quote, or edit an existing quote. Served at `/quote.html` (`app.py:157-160`).
- **Mode:**
  - `?id` → `editInvoice.js`, which takes the type from the record (comment at `quote.html:545-547`).
  - Otherwise → `createQuote.js`.
- **Inbound links:** invoiceSystem.html `quote.html?from=invoiceSystem`; sidebar `/quote.html`; pendingQuotes.js:303 Edit → `quote.html?id=<id>`.
- **Access:** same as invoice.html. The server requires admin or accountant for `/api/add`. Quotes have no 1-day edit limit on the server, but the client still blocks every role except admin and accountant.

### 2. Layout
Identical to invoice.html (same ids, modals, scripts and inline back-button script, which also writes `lastPage="invoice"`), with these differences:
- The form id is `quote-form`.
- The items card heading is "Quoted Items".
- **No Advance field.**
- **No Check & Deduct Inventory section.**
- The submit button reads "Generate Quote".
- The Balance line `#total-balance` is still shown and equals Net Total − Discount.

### 3–4. Fields and calculations
- Fields, customer and car flow, modals, line items, search, Tab behaviour and the tax toggle are all identical to invoice.html, through `invoiceShared.js`.
- **Calculation:** the same as invoice.html with advance = 0: `balance = total - discount`.
- `#quote-form` has no CSS rule; only `#invoice-form` is styled as a flex column. The visual effect is minor.

### 5. Submit (`createQuote.js:45-83`)
1. `collectFormData()` then `validateFormData()`, the same as invoice.
2. **Payload:** `{...formData, type_of:"Quote", advance:0, balance: formData.net_total}`. The server recomputes the balance anyway, as `total + tax - discount`.
3. **The submit button** (`event.submitter`) is disabled during the request and re-enabled in `finally`.
4. `updateCustomerAndCarRecords` (the same master-record overwrite), then `POST /api/add`.
5. **Success:**
   - `sessionStorage.invoiceData`, `invoiceId` and `documentType="quote"` are set.
   - Navigate to `invoice-template.html?from=quote&id=<id>`, then `resetForm()`.
   - **BUG:** `resetForm()` calls `document.getElementById("invoice-form").reset()`, which is null on this page. It throws a TypeError, the catch shows `showError("Cannot read properties of null…")` while the page navigates away, and the `finally` re-enables the button.
6. **Errors:** `showError(message)` if defined (it is, from notification-utils), otherwise `alert`.
7. **Server:** status is always `pending`. `log_action` uses module `quotes`. **A WhatsApp quote message is sent automatically** (`_create_quote_message`).

### 6. Edit mode on quote.html
- Uses the same `editInvoice.js` (§10 above).
- Looks for `#invoice-form || #quote-form` (`editInvoice.js:66-70`). Earlier code only looked for `#invoice-form` and retried forever.
- Advance is skipped because there is no `.advance` element.
- The button reads "Update Quote". The deduction section does not exist.
- The payload `advance` is 0, so **saving a quote resets any advance on it to 0**.
- `type_of` stays "Quote".
- **After saving it redirects to `invoice-template.html?from=invoice&id=N`,** not `from=quote`. The template's Back then goes to invoice.html.

### 7–9. Print, keyboard, state
- Same as invoice.html.
- There is no repair-order pre-fill on quote.html.
- `documentType` is set to "quote".

### 10. Invoice vs quote — differences

| Aspect | invoice.html | quote.html |
|---|---|---|
| Form id | `invoice-form` | `quote-form` |
| Create module | createInvoice.js | createQuote.js |
| Advance field | Yes (`#advance`) | No; advance always sent as 0 |
| Balance sent | Client balance (ignored by server) | `net_total` (ignored by server) |
| Inventory deduct button | Yes (create mode only) | No |
| Repair-order pre-fill | `?from=repair-order` | No |
| Submit text | "Generate Invoice" / "Update Invoice" | "Generate Quote" / "Update Quote" |
| `type_of` | "Invoice" (stored as `invoice`) | "Quote" (stored as `quote`) |
| Server status | unpaid / partially_paid / paid, calculated | always `pending` |
| Template redirect (create) | `?from=invoice&id=` | `?from=quote&id=` |
| Error display on create | `alert` | `showError`, falling back to `alert` |
| Submit button disabled during save | No (only the api-helper lock) | Yes |
| `resetForm` after save | Works | Throws (null form) |
| Server edit time limit for non-admin/accountant roles | 1 day | None |
| WhatsApp on create | Invoice message | Quote message |
| Payments (`update-balance`) | Allowed (management page) | Server rejects: "Convert this quote to an invoice first." |

---

## customer-car-utils.js — shared `window.CustomerCarUtils` (invoice.html, quote.html, repair-order.html)

A classic script (not a module) that attaches a global object (`customer-car-utils.js:11-472`). It also sets `module.exports` when `module` exists, which is never the case in the browser.

| Method | Behaviour |
|---|---|
| `loadCustomers()` | `GET /api/customers` → array or `[]`; rethrows errors. Each item: `{id, code, name, phone, address, created_at, updated_at}`, ordered by id. |
| `createCustomer({name, phone, address})` | No validation; each blank (after trim) becomes "N/A". `POST /api/customers` (roles admin, accountant, inventory_manager). Returns `result.customer`, or throws "Failed to create customer". Server: 409 if name, phone and address all match exactly. |
| `updateCustomer(id, data)` | Throws "Customer ID is required" with no id. Same N/A filling. `PUT /api/customers/{id}` → `result.customer`. |
| `loadCars(customerId=null)` | `GET /api/cars`, or `GET /api/cars/customer/{id}` when an id is given (never passed by any caller). Accepts an array or `{cars}`, else `[]`. Server: `/api/cars` inner-joins customers, so **ownerless cars are excluded**. Each item: `{id, make, model, plate_no, mileage, vin, color, chasis_no, customer_id, customer_name, customer_code, customer_phone, created_at, updated_at}`. |
| `createCar(data)` | VIN required ("VIN is a required field"). make, model, plate_no, mileage, color and chasis_no default to "N/A"; `customer_id` parsed to int and removed if falsy. `POST /api/cars` (admin, accountant, inventory_manager). 409 on duplicate VIN; 404 if the customer is not found. |
| `updateCar(id, data)` | Needs an id and a VIN; same normalisation. `PUT /api/cars/{id}`. Server overwrites every field. **If `customer_id` is missing it sets `customer_id = None`, orphaning the car.** Unlike create, there is no VIN-uniqueness check. |
| `setupCustomerModal(opts)` / `setupCarModal(opts)` | **Dead:** no page calls them. repairOrder.js defines its own local functions with the same names. `setupCarModal` also wraps `window.openCarModal` and splits a combined Make/Model on the first space. |
| `openCustomerModal(id)` / `openCarModal(id)` | `style.display="block"` plus class `active`. |
| `closeCustomerModal(id, formId)` / `closeCarModal(id, formId)` | Hide, remove `active`, `form.reset()`. |

- **Error handling:** each method checks `error.response.data.details|error`. **This never applies,** because api-helper throws plain `Error`s whose message already has the server `error` text and, when it is an array, the `details` list.
- **Repair-order usage** (repairOrder.js): `loadCustomers` (1154), `loadCars` (1646), `createCustomer` / `updateCustomer` (1581, 1596, and 601 on save), `createCar` / `updateCar` (2022, 2037, and 627 on save). This is the same "update master records on document save" pattern.

---

## editInvoiceUtils.js — confirmed dead
- 16 lines: a deprecation comment and a `console.warn`, with no exports.
- The only reference is `static/js/script.js.backup:1` (a backup file that is never loaded). No HTML page or module imports it.
- Safe to drop.

## invoice.css — behaviour only
- **No print rules** (no `@media print` or `@page`).
- **Responsive breakpoints:**
  - `max-width: 1024px`: smaller padding.
  - `max-width: 768px`:
    - Back-button text hidden.
    - Customer/car search and Add button stack vertically; Add button full width.
    - Add Item/Labour and submit buttons stack, full width.
    - **Item rows switch to a single column** with Delete aligned right.
    - Modal 95% wide; modal Save and Cancel stack.
    - Inputs at least 44px tall.
  - `max-width: 480px`: header subtitle hidden, tighter padding, modal 98% wide.
- **Accessibility:** `prefers-reduced-motion` turns off card and row animations; there is also a `prefers-contrast: high` block.
- **Visual behaviours:**
  - `.section-card.dropdown-active { z-index:10 }` lifts the card with an open dropdown above the cards below.
  - `.dropdown-options` is absolutely positioned, max-height 200px, scrollable, z-index 100.
  - `.modal.active` and `.modal[style*="display: block"]` become `display:flex !important`, z-index 2000.
  - `input[readonly]` is greyed with a not-allowed cursor.
  - Cards and rows fade up on entry.

---

### Endpoints used

| METHOD | path | page / action |
|---|---|---|
| GET | `/api/customers` | both pages: load the customer list; reloaded after modal save |
| POST | `/api/customers` | both: Add Customer modal |
| PUT | `/api/customers/{id}` | both: Edit Customer modal; also automatically on every document save (`updateCustomerAndCarRecords`) |
| GET | `/api/cars` | both: load the car list; reloaded after modal save |
| POST | `/api/cars` | both: Add Car modal |
| PUT | `/api/cars/{id}` | both: Edit Car modal; also automatically on every document save |
| GET | `/api/cars/customer/{id}` | not called (dead branch in `CustomerCarUtils.loadCars`) |
| GET | `/api/inventory` | both: `loadInventory()` on init (first 50 items; result effectively unused) |
| GET | `/api/inventory/search?q=` | both: per-row part/lubricant search (300 ms debounce, ≥ 2 chars) |
| POST | `/api/inventory/check-stock` | invoice.html create mode: Check & Deduct Inventory (step 1) |
| POST | `/api/inventory/deduct-items` | invoice.html create mode: Check & Deduct Inventory (step 2; admin and inventory_manager only) |
| POST | `/api/add` | invoice.html create (`type_of` Invoice); quote.html create (`type_of` Quote) |
| GET | `/api/invoice/{id}` | both: edit-mode load |
| PUT | `/api/invoice/{id}/update` | both: edit-mode save |
| GET | `/api/repair-orders/{id}` | not on these pages; called by repairOrdersManagement.js before linking to `invoice.html?from=repair-order` |
| GET | `/api/auth/verify`, `/api/auth/permissions/my` | shared auth_jwt on page load |
| — | `/api/search`, `/api/invoice/{id}/convert`, `/api/invoice/{id}/status`, `/api/invoice/{id}/log`, `/api/invoice/{id}/update-balance`, `/api/inventory/lookup` | **not called** by these pages; they belong to the management, pending-quotes and inventory pages |

**Outbound navigation:**
- `invoice-template.html?from=invoice&id=N` (invoice create, and every edit)
- `invoice-template.html?from=quote&id=N` (quote create)
- Back → invoiceSystem.html, admin.html, home.html or invoice-management.html
- `window.history.back()` when an edit is refused
- `invoice-management.html` when `id` is missing (unreachable)

### Files read

| File | Lines |
|---|---|
| frontend/invoice.html | 588 |
| frontend/quote.html | 554 |
| static/js/createInvoice.js | 246 |
| static/js/createQuote.js | 89 |
| static/js/editInvoice.js | 459 |
| static/js/editInvoiceUtils.js | 16 |
| static/js/invoiceShared.js | 1322 |
| static/js/customer-car-utils.js | 472 |
| static/css/invoice.css | 1614 (behaviour sections and layout rules read; purely cosmetic declarations skimmed) |
| routes.py | 992 |
| invoice_math.py | 49 |
| document_links.py | 115 |
| search_suggestions.py | 98 |
| car_routes.py | 698 |
| inventory_routes.py | 1469 (read: 285-470 helpers and GET /inventory, 800-860 search, 995-1020 lookup, 1075-1250 check-stock and deduct-items) |
| static/js/phone-formatter.js | 167 (page-specific use only) |
| static/js/api-helper.js (380-600), auth_jwt.js (1-60, 200-290), app-shell.js (55-64, 361-456), app.py (145-165), models.py (Inventory, Customer, Car columns) | partial, for context |
| invoiceManagement.js:320-345, pendingQuotes.js:290-310, repairOrdersManagement.js:340-380, invoice-template.html:354-375, 569-572 | partial, inbound/outbound links |
