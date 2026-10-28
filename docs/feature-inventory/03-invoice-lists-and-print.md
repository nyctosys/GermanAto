# Feature inventory: invoice/quote lists, pending quotes, document history log, printable invoice template

All three pages are plain HTML served by Flask at the root: `/invoice-management.html` (app.py:171), `/pending-quotes.html` (app.py:228) and `/invoice-template.html` (app.py:165). Each is styled with `theme.css` and `search.css` (the template uses `invoice-template.css` instead of `search.css`). Every API call goes through `APIHelper` (api-helper.js), which adds the Bearer JWT, refreshes once on a 401, throws on any non-2xx response, and fires an `api:saved` event after successful non-GET calls.

**Access (applies to all three pages).** None of the three pages calls `auth.requirePageAccess(...)`. The only page-level gating is that app-shell's nav lists "Invoices" and "Quotes" under the `invoice` permission (app-shell.js:63-64). The real protection is on the API:
- `GET /api/search` and `GET /api/invoice/<id>`: any logged-in user (`@login_required`).
- delete, convert, status, log and update-balance: `admin` or `accountant` only (`@role_required`).

---

## invoice-management.html — Invoice Management

### 1. Purpose, URL, access
- **Purpose:** list, search and filter every document with `type_of = invoice`, and record payments against them.
- **URL:** `/invoice-management.html?from=<home|invoiceSystem>`.
  - Linked from invoiceSystem.html:121 (`?from=invoiceSystem`), the app-shell nav, and dashboard.js:85/145/148.
  - The dashboard links to `/invoice-management.html?id=<id>`, but the page ignores `id`. Parity gap: a deep link to one invoice does not filter the list.
- **Access:** see the note at the top. "Edit" is locked in the UI for any role other than admin or accountant.

### 2. Layout
1. Header: logo, H1 "Invoice Management", subtitle "View and manage all invoices and their payment statuses", and a Back link.
   - Back goes to `home.html` if `from` (or `localStorage.lastPage`) is `home`; otherwise to `invoiceSystem.html` (invoiceManagement.js:3-19).
2. Search section:
   - "Keyword Search" text input, placeholder "Customer name, phone, reg number...".
   - "ID Search" number input (min 1), placeholder "Invoice ID".
   - A search icon button, and a clear (X) button that starts hidden.
3. Date filter: Today / This Week / This Month / This Year / Custom Range / "Clear Date" (hidden until a range is set). Custom Range opens a From/To `<input type=date>` pair with an Apply button.
4. Status toggle: All (active by default) / Paid / Partially Paid / Unpaid.
5. A results container `#invoice-management-results`.
6. The Update Payment Balance modal (inline-styled, z-index 1000).
7. Footer "© 2025 GermanATO. All rights reserved."

Scripts loaded: auth_jwt, app-shell, api-helper, xlsx.full.min.js (used only by DocumentLog), documentLog.js, invoiceManagement.js.

### 3. List
- **Data:** `GET /api/search?type=invoice[&q=][&id=][&status=][&date_from=][&date_to=]` (invoiceManagement.js:131-159). The page reads `data.invoices`.
- **Server behaviour** (routes.py:579-716):
  - All criteria are combined with AND.
  - `q` (max 100 chars, otherwise 400 "Search query too long") is an ILIKE `%q%` match on customer_name, customer_phone, customer_reg_no, type_of, or id cast to string.
  - `id` is an exact int match; a non-integer is silently ignored.
  - `status` is an exact match. The value "partially paid" matches both `partially paid` and `partially_paid`.
  - `type` is an ILIKE match.
  - `date_from` means `created_at >= date`. `date_to` means `created_at < date + 1 day`. Both are `YYYY-MM-DD`; invalid dates are ignored.
  - Order is `created_at DESC`. No limit, no pagination.
  - If no criteria are given, it returns empty lists.
  - When a keyword search matches nothing, the response also carries `did_you_mean`/`closest` suggestions (routes.py:707-709). **This page ignores them**, even though `APIHelper.renderNoMatches` exists for this.
- **Fields per row in the search response:** id, customer_name, customer_phone, customer_reg_no, type_of, created_at ("YYYY-MM-DD HH:MM:SS", UTC), balance, advance, total, net_total, discount, include_tax, tax_amount, paid_amount, status, created_by_user, updated_by_user, updated_at, payments_history[].
  - **There is no `customer_code`**, so the card's customer-code chip (invoiceManagement.js:259) never renders. Bug.
- **Rendering:** cards, not a table. The heading is "🧾 Invoices (N)". Each card (`#invoice-card-<id>`) shows:
  - Header: `type_of` (capitalised by CSS) in maroon #8b1538, plus "ID: #<id> • Created: <created_at raw>", plus a status badge.
  - **Customer** block: name (bold), customer_code chip (never present, see above), phone, "Reg: <reg_no>". Null values render as the text "null".
  - **Summary** block:
    - "Net Total: <net_total or total>.toFixed(2)".
    - If discount > 0: "Discount: -x" in red #e53e3e.
    - If advance > 0: "Advance: -x".
    - If include_tax and tax_amount > 0: "Tax (GST): +x".
  - **Outstanding** block: `invoice.balance` (the stored DB column) followed by " PKR", in orange #dd6b20, and "Paid: <paid_amount> PKR".
  - **Payment Proofs** row, shown only if any `payments_history` entry has `proof_path`. Each proof is a blue badge linking to `/static/<proof_path>` (opens a new tab), labelled "Proof #n (<amount> PKR)" and titled "Paid on <timestamp> by <person>". The number n counts only payments that have a proof.
  - Action buttons: View, Edit (or "Edit (Locked)", disabled), Update Balance, Payments, Delete.
- **Status badge colours** (invoiceManagement.js:226-244). The text is the raw `status`, or "N/A", uppercased by CSS.

  | Status | Background | Text |
  |---|---|---|
  | `paid` | #c6f6d5 | #22543d |
  | `partially paid` or `partial` | #feebc8 | #744210 |
  | `unpaid` | #fed7d7 | #742a2a |
  | anything else | #e2e8f0 | #4a5568 |

  Bug: the server writes **`partially_paid`** (invoice_math.py:49), which matches no rule, so partially paid invoices get the grey badge.
- **Filters:**
  - Status buttons set `currentStatus` to `all`, `paid`, `partially paid` or `unpaid` and reload, keeping the keyword, id and date filters.
  - Date presets are computed client-side (lines 53-87), formatted as `toISOString().split('T')[0]`, which is a **UTC date**. In Pakistan (UTC+5), "Today" between 00:00 and 05:00 local resolves to yesterday.
    - Today: from = to = today.
    - This Week: Monday to Sunday (if today is Sunday, go back 6 days).
    - This Month: the 1st to the last day.
    - This Year: Jan 1 to Dec 31.
  - Custom: the button marks itself active and toggles the From/To panel, pre-filling it from the current range. Apply needs at least one date ("Please select at least one date."). There is no from ≤ to check. An open-ended range is allowed.
  - "Clear Date" resets the range, the inputs and the active button, then reloads.
- **Search:** clicking the button or pressing Enter in either input runs it. The clear X shows (`display:block`) when either field has text. Clearing resets both fields and reloads, keeping status and date.
- **Totals/summary:** only the count in the heading. No totals row.
- **States:**
  - Loading: `APIHelper.renderLoading(resultsDiv, "Loading invoices...")`.
  - Empty: `<p>No {status} invoices found{ for keyword "x"}{ and ID "y"}.</p>`.
  - Error: `APIHelper.renderError(resultsDiv, err, retry)`. The retry calls `loadInvoices(status)` only, **dropping the keyword, id and date filters** (line 395).
- **Initial load:** `loadInvoices("all")`.

### 4. Actions
| Action | Behaviour |
|---|---|
| **View** | `GET /api/invoice/<id>`. On success it stores `invoiceData` (full JSON), `invoiceId` and `documentType` (= type_of) in sessionStorage, then navigates to `invoice-template.html?from=invoice-management&id=<id>`. A falsy response alerts "Document not found"; an exception alerts "Failed to load document data". |
| **Edit** | Navigates to `invoice.html?id=<id>` (no `from` param). Disabled with the label "Edit (Locked)" when `localStorage.user.role` is not admin or accountant (lines 115-129). The handler's alert "You cannot edit invoices older than 1 day…" can never fire because the button is `disabled`. The lock is **role-only, not age-based**; `isInvoiceOlderThanOneDay` (line 107) is dead code. Server-side, `can_edit_invoice` (routes.py:117) applies the real rule: admin/accountant always; other roles only invoices under 1 day old (quotes are exempt). |
| **Update Balance** | Opens the modal (see below). |
| **Payments** | `DocumentLog.open("invoice", id)`. |
| **Delete** | Confirm "Are you sure you want to delete this document?", then `DELETE /api/invoice/<id>/delete`. On success the card is removed from the DOM; the heading count is **not** updated. Falsy result alerts "Failed to delete document."; an exception alerts "Error occurred while deleting document." See the delete note below. |

**Delete on the server** (routes.py:422-455, admin/accountant):
- Deletes the items and labours, then the invoice.
- `log_action(DELETE, module 'invoices' or 'quotes', id, "Deleted {type} ID {id} for customer {name}")`.
- Returns `{message}`, 404 if not found, 500 "Database error occurred".
- There is no guard for invoices that have payments. A linked `CashReceived.invoice_id` (models.py:320, FK with no cascade) is set to NULL by SQLAlchemy's default relationship behaviour, so the receipts survive but lose their link.

**Update Payment Balance modal** (HTML lines 137-174; JS 344-366 and 588-656):
- Read-only summary: Invoice ID, Total Due, Amount Paid, Remaining Balance (maroon, bold).
- Client calculation (lines 350-362):
  `total = (net_total ?? total ?? 0) + (include_tax && tax_amount ? tax_amount : 0) − discount − advance`
  `remaining = total − paid_amount`
  This matches the server's `invoice_amount_remaining`.
- "Additional Paid Amount (PKR) *": number input, step 0.01, min 0, `max = remaining.toFixed(2)`, with the remaining value kept in `data-remaining`.
- "Payment Proof Attachment (Optional)": file input accepting `image/*,application/pdf`.
- Cancel button, X, or a click on the backdrop closes it. There is no Escape key handling.
- Submit runs these checks:
  - Amount empty, NaN or ≤ 0: alert "Enter a payment amount greater than zero."
  - `round(amount*100) > round(remaining*100)`: alert "Payment of X PKR exceeds the Y PKR still owed on this invoice."
  - Then it sends `PUT /api/invoice/<id>/update-balance` as multipart FormData: `paid_amount`, plus optional `proof` file.
  - Success: alert the server `message` (or "Balance updated successfully!"), close the modal, call `window.refreshInvoiceList()`, which reloads with the current filters (line 574).
  - Error: alert `error.message`.
- Server side (routes.py:827-935):
  - Accepts multipart or JSON `{paid_amount}`.
  - Returns 400 in these cases: missing; non-numeric; ≤ 0; not an invoice ("Payments can only be recorded against an invoice. Convert this quote to an invoice first."); remaining ≤ 0 ("This invoice is already fully paid."); over-payment (with `remaining` in the body).
  - Saves the proof to `static/uploads/<unix_ts>_<secure_name>` (log_utils.py:14-33). Proof URLs are `/static/uploads/...`.
  - Writes: `paid_amount += amount`; `balance = remaining`; `status = calculate_invoice_status`; `updated_by_user`; `updated_at = utcnow`.
  - Appends `{amount, timestamp (UTC), person: username, proof_path}` to the `payments_history` JSON.
  - `log_action(UPDATE_BALANCE, 'invoices', id, "Added payment of X PKR. Total paid: Y PKR. Balance: Z PKR")`.
  - Returns `{message, paid_amount, balance, status, payments_history}`.
  - **It does not create a CashReceived record.** The link only runs the other way: a cash receipt with `invoice_id` posts into the invoice via `cash_received_routes.apply_receipt_to_invoice`, which appends `{source:'cash_received', payment_method, cash_received_id, proof_path:null}`.

### 5. Exports
- No list Excel export and no PDF on this page.
- The only Excel export is the per-document history (DocumentLog, see below).
- No WhatsApp action.

### 8. Client calculations
- **Card:** displays `net_total` and the stored `balance`. The variables `totalWithTax`, `taxDisplay` and `statusDisplay` are computed but never used (lines 181-193), so they are dead code.
- **Modal:** the formula above.

### 9. Persisted state
- **Writes `localStorage.lastPage`** = `"invoice-management"`.
- **Reads `localStorage.user`** to get the role.
- **Writes sessionStorage keys** `invoiceData`, `invoiceId` and `documentType` before View.
- **Reads URL parameter `from`.**
- Filters are not persisted; they reset on reload.

### 10. Shortcuts, timers
Enter in either search input runs the search. There is no polling.

---

## pending-quotes.html — Quotes Management

### 1. Purpose, URL, access
- **Purpose:** list, search and filter quotes; approve a quote into a repair order; view, edit, delete; see history.
- **URL:** `/pending-quotes.html?from=<admin|home|invoiceSystem>`.
  - Linked from invoiceSystem.html:101 (`?from=invoiceSystem`), the nav, dashboard.js:97, and the Back link on repairOrder.js:30.
  - Back goes to admin.html, home.html, or invoiceSystem.html (the default) (pendingQuotes.js:3-21).
- **Access:** same as the invoice list. Approve and Delete need admin or accountant on the server.

### 2. Layout
Identical to invoice-management, with these differences:
- H1 "Quotes Management", subtitle "View and manage quotes by status".
- ID placeholder "Quote ID".
- Status toggle: "All Quotes" (active) / "Pending Quotes" / "Approved Quotes".
- Results container `#pending-quotes-results`.
- No modal.

### 3. List
- **Data:** `GET /api/search?type=quote[&status=][&q=][&id=][&date_from=][&date_to=]`. The page reads `data.quotes`.
- Server, date presets, Custom range, Clear Date, search, Enter key, clear X, loading/empty/error states and the retry bug are all identical to the invoice list.
  - Loading text: "Loading quotes...".
  - Empty text: "No {status} quotes found…".
- **Heading:** `<Status capitalised> Quotes (N)`, e.g. "All Quotes (12)" or "Pending Quotes (3)".
- **Card** (`#invoice-card-<id>`):
  - Header: type_of, "ID: #id • Created: created_at", status badge.
  - Customer block: same as invoices, including the customer_code chip that never shows.
  - Summary block: Net Total, plus Discount, Advance and Tax lines (same rules as invoices).
  - **"Total Quotation"** block: `(totalWithTax − discount).toFixed(2) PKR`, where `totalWithTax = net + tax (if include_tax && tax_amount>0)`. **Advance is not subtracted here, but the template does subtract it** (the template balance is net + tax − discount − advance − paid), so the two figures differ when an advance exists.
  - Buttons: View, Edit, History, Delete, and Approve (only when the **Pending** tab is active; the check is `status === "pending"` on the filter, not on the quote, so Approve never appears on the "All" tab).
- **Badge colours:**

  | Status | Background | Text |
  |---|---|---|
  | default / `pending` | #feebc8 | #744210 |
  | `approved` | #c6f6d5 | #22543d |
  | `rejected` | #fed7d7 | #742a2a |

  An empty status displays as "pending".

### 4. Actions
| Action | Behaviour |
|---|---|
| **View** | Same as invoices; navigates to `invoice-template.html?from=pending-quotes&id=<id>`. |
| **Edit** | Navigates to `quote.html?id=<id>`. Never locked. |
| **History** | `DocumentLog.open("quote", id)`. |
| **Delete** | Same as invoices (`DELETE /api/invoice/<id>/delete`); logged under module `quotes`. |
| **Approve** | Confirm "Approve this quote and create repair order?", then `PUT /api/invoice/<id>/status` with JSON `{"status":"approved"}`. On success navigates to `repair-order.html?quoteId=<id>&from=pending-quotes`. Falsy result alerts "Failed to approve quote."; an exception alerts "Error approving quote." |

**Approve bug:** the server **ignores the body**. It recalculates the status with `calculate_invoice_status`, which always returns `'pending'` for quotes (invoice_math.py:39-40), and only logs `UPDATE_STATUS` when the status changes (routes.py:765-785). No `.py` file ever writes `'approved'`, so **the "Approved Quotes" tab can only show legacy rows**, and an approved quote stays "pending". repair-order.html then loads the quote via `GET /api/invoice/<quoteId>` (repairOrder.js:123-125; that page is documented elsewhere).

### 5. Exports
History Excel only, via DocumentLog.

### 9. State
- **Writes `localStorage.lastPage`** = `"pending-quotes"`.
- **Writes sessionStorage keys** `invoiceData`, `invoiceId` and `documentType` before View.
- **Reads URL parameter `from`.**

### 11. Quirks
- Same dead `totalWithTax`/`taxDisplay` code; the comment "View/Edit/Delete event listeners can be added as needed" is stale.
- Card ids reuse the `invoice-card-` prefix.

---

## invoice-template.html — Printable Invoice / Quote

### 1. Purpose, URL, access
- **Purpose:** an A4 document view of one invoice or quote, with Print, Share PDF, and (for quotes) Convert to Invoice.
- **URL:** `/invoice-template.html?from=<invoice|invoice-management|pending-quotes|...>&id=<id>`.
- **Callers:**
  - invoiceManagement.js:313 (`from=invoice-management`).
  - pendingQuotes.js:281 (`from=pending-quotes`).
  - createInvoice.js:115 and editInvoice.js:453 (`from=invoice`).
  - createQuote.js:73 (`from=quote`). This falls through to the default Back target, `invoiceSystem.html`.
- **Access:** any logged-in user can view (`GET /api/invoice/<id>` is `@login_required`). Convert needs admin or accountant.
- Scripts: auth_jwt, api-helper, invoiceTemplateUtils.js?v=2.6, html2canvas, jspdf.umd. **No app-shell.** `theme.js` and `theme.css` are loaded, but `invoice-template.css:48-151` forces the document to light colours even in dark mode.

### 2. Layout (in DOM order)
1. Fixed "← BACK" link at the top left (`#back-btn`, `::before` content "←").
   - `from=invoice` → invoice.html; `invoice-management` → invoice-management.html; `pending-quotes` → pending-quotes.html; anything else → invoiceSystem.html.
   - `from` falls back to `localStorage.lastPage`, then to "search" (lines 359-375).
2. `.invoice-iframe-wrapper`: a 210×297mm box, bordered and shadowed, `overflow:auto`. It contains:
   - `.invoice-container`:
     - **Header:** logo `/static/images/logo-without-background.png` (alt "Auto Trader Logo", hidden if it fails to load), with a skewed translucent trapezoid (`.header::before`) on the right. Right-aligned: title (`.invoice-title`, "Invoice" or "Quote", uppercased), `#invoice-id` ("INVOICE #<id>" or "QUOTE #<id>"), `#invoice-date`.
     - **OUR INFORMATION** (hard-coded): "Address: 38-A, Kamahan Lidher Road, Lahore", "Email: service@germanato.com", "Phone#: +92 321 4854641".
     - **BILLING INFORMATION:** Customer ID (`customer_code`, "CN%03d" from customer_id), Customer Name, Address, Phone#, Reg#, Made, Mileage (with "km" appended unless missing or "N/A"), VIN#, Color, Chassis#. Each missing value shows "N/A".
     - **Parts table** `#parts-table`: columns "Part Desc./Lubricants | Price | Quantity | [GST (17%)] | Subtotal".
     - **Labour table** `#labour-table`: columns "Labour | Price | [PST (17%)] | Subtotal".
     - **Totals** `.total-section` (grey #f0f0f0):
       - Net Total.
       - Tax (GST/PST), hidden unless there is tax.
       - Discount, hidden unless > 0.
       - Advance.
       - Paid Amount.
       - Last row: **"Balance"**, bold, uppercased, 18px. For quotes the label is replaced with **"Total Quotation"**.
     - Empty `.footer` div.
     - **Notes:** "**Thank you for choosing GermanATO!** We appreciate your business and trust in our services. For any queries or concerns, please don't hesitate to contact us."
   - `.terms-container.page-break`: "TERMS & CONDITIONS", 15 numbered uppercase clauses (CSS counter, 11px font). Shown only for quotes.
     - The clauses cover: 60% deposit; balance due before work; written confirmation needed before work; parts delivery (air 15–20 working days, sea 8–10 weeks); price basis (duties, FX PKR→€); estimates exclude hidden damage; diagnosis costs remain payable if the customer declines; no liability for supplier delays; supplementary estimates; 5 free parking days, then PKR 1,000/day; salvage parts collected within 7 days; customer keeps insurance; remove personal items; test-drive authorisation; genuine parts only, customer-supplied parts not accepted.
     - The full text is in HTML lines 162-240; copy it verbatim.
3. `.button-container`:
   - "Print" (`printInvoice()`).
   - "Share PDF" (green #25d366, `shareInvoice()`).
   - "Convert to Invoice" (green #28a745, hidden; `convertToInvoice()`).

### 6. Data loading (lines 355-597)
- **Priority order:**
  1. If both sessionStorage `invoiceData` and `invoiceId` exist, use them.
  2. Otherwise, if URL `?id=` exists, `GET /api/invoice/<id>` and set `invoiceId = data.id`.
- If neither, or the fetch fails (only logged to the console), the page shows raw placeholders such as `{CUSTOMER_NAME}` and `{NET_TOTAL}`. **No error message.**
- **Document type:** `data.type_of.toLowerCase()`, falling back to sessionStorage `documentType`.
- **Date:** `new Date(created_at).toLocaleString()`. The server string is UTC "YYYY-MM-DD HH:MM:SS" with no zone, so it is parsed as local time: **the printed time is UTC shown as local time** (about 5 hours behind PKT). The format depends on the browser locale.
- **`GET /api/invoice/<id>` response** (routes.py:344-420): id, customer_* (name, address, phone, reg_no, made, mileage, vin, color, chasis), customer_id, customer_code, car_id, created_at, balance, advance, net_total, total, discount, type_of, include_tax, tax_amount, paid_amount, status, created_by_user, updated_by_user, updated_at, payments_history, `items[{id, product_name, part_number, quantity, price}]`, `labours[{id, description, price}]`.
  - If color or chassis is blank, they are filled from the Car table, matched by VIN and then by plate.
  - `part_number` is returned but not printed.
- **After rendering:** removes the three sessionStorage keys and sets `localStorage.lastPage = "invoice-template"`.
- **Rows:**
  - Parts rows are rendered only when `item.quantity` is truthy.
  - The parts Subtotal is `qty × price` and excludes tax.
  - The tax cells (both tables), shown only when `include_tax && tax_amount > 0`, are a hard-coded **17% of each line's subtotal**. That can differ from the stored `tax_amount`.
  - Labour Subtotal = price.
  - Values are inserted with `innerHTML` and no escaping.
- **Totals** (lines 462-567):
  - Net Total = `data.net_total || 0`. This is the server value, not recomputed from the rows.
  - Tax row: shown as flex with `tax_amount` when `include_tax && tax_amount > 0`.
  - Discount row: shown when discount > 0 (the code also checks for the legacy "N/A" string).
  - Advance: the value, or the text "N/A" when it is 0. The row is always visible.
  - Paid Amount: `paid_amount || 0`. Always visible, even for quotes.
  - **Balance** = `net_total + (tax if shown) − discount (if >0) − advance (if >0) − paid_amount (if >0)`. The same formula is used for quotes under the "Total Quotation" label.
  - All amounts are `toFixed(2) + " PKR"`. There is no thousands separator.
- **Quote vs invoice:**
  - Title and ID prefix differ (QUOTE / INVOICE).
  - The label "Total Quotation" replaces "Balance" via `.total-row:last-of-type` `innerHTML.replace`.
  - Terms are shown for quotes and hidden for invoices.
  - The Convert button is shown only for quotes, with `data-invoice-id`.
- **Not present:** no amount in words, no Urdu or RTL, no auto-print, no signature block, no status shown, no payment history on the document.

### 4. Actions
- **Convert to Invoice** (lines 600-657):
  - Confirm "Are you sure you want to convert this quote to an invoice? This will deduct inventory and cannot be undone."
  - Then `POST /api/invoice/<id>/convert` (no body).
  - Success: alert "Quote successfully converted to invoice!". The DOM is patched in place: title "Invoice", "INVOICE #id", Convert button hidden, label back to "Balance", terms hidden. No reload.
  - Errors: alert "Failed to convert quote to invoice", or "Error: Failed to convert quote to invoice. Please try again."
  - Server (routes.py:730-763): 404 if not found; 400 "Already an invoice"; sets `type_of='invoice'` and `status='unpaid'`. Returns `{message, invoice_id}`, same id.
  - Server quirks:
    - Inventory deduction is commented out, so the confirm text is wrong.
    - There is **no `log_action`**, so conversions do not appear in the document history.
    - Status is forced to `unpaid` even when an advance makes it partly paid, and `balance` is not recalculated.
- **Print** (`printInvoice`, lines 660-852):
  - Adds `body.pdf-capture-mode` (12px base font, h1 1.6rem, h2 1.2rem, h3 1rem).
  - Sets inline sizes: wrapper 200mm wide with auto height and min-height 287mm; container 200mm wide with auto height. Forces the header into a flex row.
  - Injects a `<style>` with `@media print { @page { size: A4; margin: 5mm } … }`, which forces colour printing, sets break rules and hides `.back-btn` and `.button-container`.
  - After 100ms calls `window.print()`. After another 1000ms it removes the style and class, resets inline styles, and reruns `updateResponsiveScale()`.
  - Bug: if the logo has not finished loading, it also binds `logo.onload` and `onerror` to another `window.print()`, which can open **two print dialogs**.
  - The Print button is hidden on screens ≤ 480px (CSS 537-539).
- **Share PDF** (`shareInvoice`, lines 1330-1440):
  - The button shows "Generating PDF..." and is disabled while running.
  - Builds the PDF with `generatePDFBlob()`.
  - **Filename:** `${titleText}_${idText}.pdf` with whitespace replaced by `_`, e.g. `Invoice_INVOICE_#123.pdf` or `Quote_QUOTE_#45.pdf`. The filename contains `#`.
  - If `navigator.share` and `canShare({files})` both work, it shares the File with title `"<Title> - <ID text>"` and text `"Please find attached <title lowercase> <ID text>"`.
  - If the user cancels (AbortError/NotAllowedError), it simply resets the button.
  - Otherwise it downloads through a hidden `<a download>` and an object URL revoked after 100ms. The download path for `canShare` = false goes through a pointless FileReader detour.
  - Errors whose message contains "Failed to execute" alert "Sharing is not supported in this browser. The PDF will be downloaded instead." and regenerate the PDF to download it. Other errors alert "Error generating PDF. Please try again."
  - There is **no direct WhatsApp integration**; the green WhatsApp-coloured button relies on the OS share sheet.
- `downloadPDF()` (line 855) has no button calling it. Dead code.

### 5. PDF generation (`generatePDFBlob`, lines 925-1327)
1. Add `pdf-capture-mode`. Set the wrapper to 210×297mm and the container to 210mm wide with min-height 297mm. Inject `#pdf-capture-header-fix` to keep the header trapezoid on the right.
2. Terms are included if visible (quotes). They are given 210mm width and min-height 180mm.
3. `waitForImages` waits on every `<img>`, with a 5-second cap, then waits another 500ms.
4. `new jspdf.jsPDF({orientation:"portrait", unit:"mm", format:"a4"})`.
5. `html2canvas(invoiceContainer, {scale:1.5, useCORS:true, allowTaint:false, backgroundColor:"#FFFFFF", windowWidth:794, windowHeight:1123, onclone: force images visible and the header layout})`, then `toDataURL("image/jpeg", 0.92)`, then `addImage` at 0,0 with width 210mm and proportional height.
   - **The image is a single page, not sliced.** Content taller than A4 is cut off.
   - Up to 2 retries, 500ms apart.
6. For quotes, `pdf.addPage()` and the terms are captured the same way (`height: scrollHeight`). Any failure in the terms step falls back to a PDF without the terms page.
7. Output `pdf.output("blob")`, then remove the capture class and style.
   - The inline 210mm/297mm sizes on the wrapper and container are **not reset** and the responsive scale is not reapplied, so on mobile the page stays unscaled after sharing.

### Print CSS behaviour (invoice-template.css)
- `@page { size: A4; margin: 5mm }`. It is defined three times: lines 987 and 1097 (mobile print) and the injected style.
- Wrapper and container print at 200mm wide with auto height. Colours are forced with `print-color-adjust: exact`. Body and background are white; base font is 12px.
- Break rules:
  - `.total-section`: avoid breaking inside and after.
  - `.notes-section`: avoid breaking before and inside.
  - `.header`: avoid breaking inside.
  - `.content` and `.tables-section`: breaking inside is allowed.
  - The two later blocks (lines 949-961 vs 1038-1048) contradict each other; the later one wins.
- **The `.page-break` class on the terms container has no CSS rule.** The comment at line 1195 promises a forced break but defines nothing, so in printed quotes the terms are not guaranteed to start on a new page (the PDF does put them on their own page).
- **Hidden in print:** `.back-btn`, `.button-container`, `.convert-button`, `.tax-toggle-section` (the last is a dead class; no such element exists).
- **Responsive on screen** (`updateResponsiveScale`, lines 283-352; runs on load, resize, and orientationchange after 100ms):
  - Only applies at viewport width ≤ 768px.
  - `scale = clamp(min((vw−2p)/794, (vh−topMargin−100)/1123), 0.25, 1)`.
    - vw ≤ 480: padding p = 10, topMargin = 60, transform `translateX(-50%) scale(s)`, wrapper left 50%, back button scaled to `min(s×1.2, 1)`.
    - vw ≤ 768: p = 20, topMargin = 70, transform `scale(s)`.
  - `marginBottom = 20/s` px.
  - Above 768px all of this is reset.
- `invoiceSystem.css` is **not loaded** by any page in this area (only invoiceSystem.html uses it). It has no print, `@page` or page-break rules; its only media queries are screen breakpoints at 768px and 480px plus `prefers-reduced-motion`.

### invoiceTemplateUtils.js (175 lines): legacy, dead code
- Defines `window.openInvoiceTemplate(win, id, data, type)`. It fetches `invoice-template.html`, `document.write`s it into a popup, and fills the fields.
- Its formulas differ from the page: `netTotal = Σ qty×price + Σ labour` computed client-side, and `balance = netTotal − advance`, ignoring tax, discount and paid.
- It writes the element `#customer-vin`, which does not exist in the template (the template's id is `vin`), so the call would throw.
- It is loaded by the template, but the only caller is `script.js.backup`. Do not port it.

### 9. State
- **Reads sessionStorage keys** `invoiceData`, `invoiceId` and `documentType`, then removes all three.
- **Reads `localStorage.lastPage`** as the fallback for `from`.
- **Writes `localStorage.lastPage`** = `"invoice-template"`.
- **Reads URL parameters `from` and `id`.**
- Risk: sessionStorage takes priority over `?id`, so if stale keys are left behind (a previous render failed before clearing them), the page shows the wrong document regardless of the URL.

### 10. Timers
- Print: 100ms delay before printing, cleanup after 1000ms.
- PDF: image wait capped at 5 seconds, then a 500ms render delay; retries 500ms apart.
- Responsive rescale 100ms after an orientation change.
- No polling, no keyboard shortcuts.

### 11. Other quirks
- Stray `</div>` at line 243. The "End invoice-container" comment at line 241 actually closes the wrapper.
- Empty inline `<style>` block ("Mobile responsive styles").
- `<link rel=preload>` for the logo, plus a `window.load` preloader that sets the logo to `display:block`.
- invoice-template.css duplicates its base, back-button and header rules (lines 1-450 vs 557-970); the later rules win.

---

## documentLog.js — Per-document history modal (shared)

**Used by:** invoice-management (`"invoice"`), pending-quotes (`"quote"`) and repair-orders-management (`"repair-order"`, repairOrdersManagement.js:311). The global API is `window.DocumentLog.open(kind, id)`. It needs `APIHelper` and the `XLSX` global.

### Opening
- Endpoints (lines 265-269):
  - `invoice` and `quote` → `GET /api/invoice/<id>/log` (admin/accountant).
  - `repair-order` → `GET /api/repair-orders/<id>/log` (admin/accountant/inventory_manager; repair_order_routes.py:16-38).
  - An unknown kind does nothing.
- On error it shows `error.message` (or "Could not load the history for this document."). It uses `showError()` if defined (notification-utils.js, which repair-orders-management loads); the invoice and quote pages don't load notification-utils, so they fall back to `alert()`.
- The modal `#document-log-modal` is created lazily (z-index 1200, max-width 820px). It closes via the X, the "Close" button, or a click on the backdrop. Footer buttons: "Close" and "Export Excel".

### Response shapes
- **Invoice or quote log** (routes.py:787-824):
  `{kind: type_of lowercased, document_id, reference: "#id", customer_name, created_at, created_by, advance, amount_due (net+tax−discount, rounded), amount_paid (advance+paid_amount), amount_remaining, payments: payments_history[], entries}`.
- **Repair-order log:**
  `{kind: 'repair-order', document_id, reference, customer_name, created_at, created_by, current_status, payments: [], entries}`.
- **`entries`** come from `log_utils.document_log_entries`: AppLog rows where `module IN aliases AND reference_id = id`, oldest first. Each entry is `{when, action, details, user (default 'system'), ip_address}`.
  - Aliases for invoices: `invoice`, `invoices`, `quote`, `quotes`.
  - Aliases for repair orders: `repair_order`, `repair_orders`.

### What it shows
- **Title:** `"<Invoice|Quote|Repair order> #<id> — <customer_name or —>"`.
- **Money section** (only when `kind === 'invoice'` and `amount_due` is defined):
  - Three cards:
    - "Invoice total" = PKR `amount_due`.
    - "Received" = the final running total, including the advance, computed client-side.
    - "Still owed" = PKR `amount_remaining` (from the server, maroon).
  - **Payments table** with columns When | What | Recorded by | Amount (green) | Owed after | Proof ("View" link to `/static/<proof_path>`, or "—").
  - Empty state: "Nothing received against this invoice yet."
- **Activity table** (every kind): When | Action (bold) | By | Details.
  - Empty state: "Nothing recorded. Actions taken from now on will appear here."
- Money formatting: `toLocaleString("en-PK", 2 decimals)`. All text is HTML-escaped.
- `payment_method` and `source` on cash-receipt-sourced payments are **not displayed**. They show as a plain "Payment received" row.

### Payment rows (lines 44-76)
1. If `advance > 0`, an opening row: `{when: created_at, what: "Advance taken with the invoice", amount: advance, who: created_by || "—"}`.
2. One row per payment: `{when: timestamp, what: "Payment received", amount, who: person, proof: proof_path}`.
3. Rows are sorted by the `when` string (lexical order works for "YYYY-MM-DD HH:MM:SS"; all of these timestamps are UTC).
4. Running totals: `paidToDate = round2(Σ amount)` and `owedAfter = round2(amount_due − paidToDate)`.

### Excel export ("Export Excel", lines 223-263)
- One sheet named **"History"**, built with `XLSX.utils.aoa_to_sheet`.
- **Filename:** `<kind>_<document_id>_history.xlsx`, e.g. `invoice_12_history.xlsx`, `quote_12_history.xlsx`, `repair-order_5_history.xlsx`.
- Numbers are written raw, unformatted.
- Rows, in order:
  1. `[<Label>, "#id"]`, `["Customer", name]`, `["Created", created_at]`, `["Created by", created_by]`.
  2. For invoices only:
     - a blank row;
     - `["Invoice total (PKR)", amount_due]`, `["Received (PKR)", paid]`, `["Still owed (PKR)", amount_remaining]`;
     - a blank row;
     - `["PAYMENTS"]`;
     - the header `["When","What","Recorded by","Amount (PKR)","Received to date (PKR)","Owed after (PKR)","Proof"]`;
     - one row per payment. Proof is an absolute URL `${origin}/static/<path>`, or empty.
  3. Then:
     - a blank row;
     - `["ACTIVITY"]`;
     - the header `["When","Action","By","Details","IP"]`;
     - one row per entry. The IP column appears only in the export, not on screen.

### Quirks
- `data.entries.length` is read without a guard; a missing `entries` would throw.
- "Received" (client sum of `payments_history` plus advance) can disagree with "Still owed" (server `paid_amount`) on legacy invoices whose `paid_amount` was set without history entries.
- Conversions (convert has no log) and quote "approvals" that change nothing do not appear in the activity list.

---

### Endpoints used
| METHOD | Path | Page / action |
|---|---|---|
| GET | `/api/search?type=invoice&q=&id=&status=&date_from=&date_to=` | invoice-management: list, search, filters |
| GET | `/api/search?type=quote&status=&q=&id=&date_from=&date_to=` | pending-quotes: list, search, filters |
| GET | `/api/invoice/<id>` | View on both lists (fills sessionStorage); invoice-template fallback load by `?id` |
| DELETE | `/api/invoice/<id>/delete` | Delete on both lists |
| PUT | `/api/invoice/<id>/update-balance` (multipart: `paid_amount`, optional `proof`) | invoice-management: Update Balance modal |
| PUT | `/api/invoice/<id>/status` (body `{"status":"approved"}`, ignored by the server) | pending-quotes: Approve |
| POST | `/api/invoice/<id>/convert` | invoice-template: Convert to Invoice |
| GET | `/api/invoice/<id>/log` | DocumentLog for invoices (Payments button) and quotes (History button) |
| GET | `/api/repair-orders/<id>/log` | DocumentLog for repair-orders-management |
| GET | `/static/uploads/<file>` (static file) | Payment proof links (cards and log) |

No endpoint called from these pages is missing on the server.

**Cross-page navigation out:**
- `invoice.html?id=<id>` (edit invoice).
- `quote.html?id=<id>` (edit quote).
- `repair-order.html?quoteId=<id>&from=pending-quotes`.
- `invoice-template.html?from=<page>&id=<id>`.
- Back links: home.html, admin.html, invoiceSystem.html, invoice.html, invoice-management.html, pending-quotes.html.

### Files read
| File | Lines | Coverage |
|---|---|---|
| frontend/invoice-management.html | 187 | full |
| frontend/pending-quotes.html | 151 | full |
| frontend/invoice-template.html | 1460 | full |
| static/js/invoiceManagement.js | 656 | full |
| static/js/pendingQuotes.js | 488 | full |
| static/js/documentLog.js | 288 | full |
| static/js/invoiceTemplateUtils.js | 175 | full |
| static/css/invoice-template.css | 1287 | lines 1-650 in full; 650-1287 via a filtered grep plus targeted reads of the print, terms and pdf-capture rules |
| routes.py | 992 | lines 1-155, 344-460, 579-992 (the create/update bodies belong to the other agent) |
| invoice_math.py | 49 | full |
| document_links.py | 115 | full |
| log_utils.py | 102 | full |
| static/css/invoiceSystem.css | 496 | selector and media-query scan only (behaviour check) |
| cash_received_routes.py | 432 | lines 1-75 and 110-135, plus a grep (invoice linkage) |
| static/js/api-helper.js | 578 | request, renderNoMatches, renderLoading/renderError |
| static/js/auth_jwt.js | 315 | page-access logic |
| app.py | 371 | page routes |
| models.py | 875 | Invoice status and CashReceived.invoice_id |
| repair_order_routes.py | 707 | the `/log` endpoint |
| static/js/dashboard.js | 255 | links into these pages |
| static/js/app-shell.js | 459 | nav entries |
| static/js/repairOrder.js | 2095 | quoteId handling |
| createQuote.js (89), createInvoice.js (246), editInvoice.js (459) | | template links only, via grep |
| static/css/search.css | 1500 | filter and toggle selectors only, via grep |
