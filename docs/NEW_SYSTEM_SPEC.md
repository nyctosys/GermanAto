# GermanATO: new system specification (Next.js + FastAPI + PostgreSQL)

Status: draft for review, 2026-10-28. It builds on [feature-inventory/](feature-inventory/README.md), which describes what the current app does. This document describes what the new one must do. The numbers in brackets, such as [R5], refer to the 17 owner requirements.

**Guiding rule: money is the source of truth.** Every rupee that comes in or goes out is a record, linked to the document that caused it, carrying evidence, and locked once its month is closed. Every number on every report can be clicked through to those records and their proofs.

---

## 1. Decisions (✅ = confirmed by the owner; the rest are recommended defaults)

| # | Decision | Recommendation | Why |
|---|---|---|---|
| D1 | What ties a car's stay together | A **Visit** record (entry → exit). Every document belongs to one visit | Gives the entry-to-exit dossier [R1] and car history [R2] for free |
| D2 | Pricing of parts | Separate **cost price** (from purchase orders) and **sale price** (set by hand per item; ✅ owner decision, no automatic markup). Cost uses the weighted average | P&L needs cost of parts sold [R3, R16] |
| D3 | How money is recorded | One **Payment** table, direction in or out, always tied to an account (Cash / Bank / JazzCash…) and a source document. Underneath, an automatic double-entry journal that users never see | Central money-in and money-out pages [R12, R13]. Books that always balance make month and year closing provable [R15] |
| D4 | Stock | Stock is the **sum of movements**, never an editable number. Every movement (PO receipt, part issued to a repair order, return, adjustment) is a row | No dirty data [R8]. Merges cleanly during offline sync [R10] |
| D5 | Deletes | Financial and stock records are never deleted. A mistake is corrected with a reversal or a void that keeps the original visible | Transparency [R11] |
| D6 | Offline | Each workshop runs a **local server** (FastAPI + Postgres on one PC) that all workshop devices use over the LAN, and it syncs to the cloud when internet is available | See §6 for why this beats browser-only offline [R10] |
| D7 | IDs | UUIDv7 primary keys everywhere. A human number per branch and type, e.g. `JC-A1F3-000123` | Records can be created offline without clashes; ready for multiple branches [R9, R10] |
| D8 | Tax | ✅ Owner decision: **one 17% rate on parts and labour, with an "Include tax" toggle per invoice/quotation** (as today). The rate is a branch setting. No FBR/PRA integration for now | The current app hard-codes 17% in several places with different formulas |
| D9 | WhatsApp | ✅ Owner decision: **Twilio** (third-party provider) behind a swappable sender interface, with approved templates and a send queue | Twilio works too; Meta direct is cheaper for template messages [R14] |
| D10 | When stock leaves | **Automatic, never a separate button.** Workshop jobs: when a part is issued on the repair order. Counter sales: when the invoice is issued. A part is never deducted twice: a workshop invoice bills parts that were already issued | ✅ Decided by the owner, 2026-10-28 |
| D11 | Counter sales | A **Counter Sale** invoice with no visit, for a walk-in who only buys parts (e.g. a headlight) | ✅ Decided by the owner, 2026-10-28 (see §2.1) |
| D12 | Quote approval | Quotations have a real **Approved** status, recorded with who, when, how and proof | ✅ Decided by the owner, 2026-10-28 (see §2.2) |
| D13 | Tracking work on the car | Each repair order has an **activity trail** of notes, findings, photos and status changes | ✅ Decided by the owner, 2026-10-28 (see §2.3) |
| D14 | Vehicle inspection report | The owner's **Germanato Vehicle Inspection Report** (pre-purchase / workshop / delivery) becomes a digital form on the visit, with the same printed layout | ✅ Requested by the owner, 2026-10-28 (see §2.4) |

---

## 2. The document chain [R1, R5]

```
 Car arrives
     │
     ▼
 VISIT opened (check-in: odometer, fuel, photos, customer complaint, signature)
     │
     ▼
 JOB CARD (rough work list) ──► QUOTATION ──► REPAIR ORDER ──► INVOICE ──► GATE PASS (exit)
  labour + parts,              prices,        actual work,      final prices,  visit closed
  inventory parts only,        advance        parts issued      advances
  or create item inline        payment        (stock out),      applied,
                                              status timeline   payments
```

Everything hangs off the visit. Each document is created **from** the previous one (copy forward, then edit) and keeps a link back to it.

| Stage | Purpose | What can be edited | Money | Stock |
|---|---|---|---|---|
| **Visit / check-in** | Who brought which car, when, in what condition | Odometer, fuel level, body-condition checklist with photos, customer complaint, items left in the car, customer signature (on tablet or paper) | — | — |
| **Job card** | Rough work list for estimating | Labour lines (picked from Labour Codes [R4], free text not allowed) and part lines (picked from Inventory only; "+ New item" opens the item form inline, **barcode/MPN required** [R6]). No prices shown, or indicative list prices only | — | none (stock is only *checked*, with shortages flagged) |
| **Quotation** | What the customer agrees to | Created from the job card. Proposed prices are **editable** per line; discount; tax toggle. Versions: v1, v2… (a revision keeps the old one). Statuses Draft → Sent → **Approved** / Rejected / Expired → Converted (§2.2) | **Advance payment** can be taken: a Money-In record linked to the visit, with method and evidence | none (optionally *reserve* stock) |
| **Repair order** | What was actually done | Created from the approved quote. Lines are marked done or not done; extra work is added (lines added after approval are flagged "not in quote"); technicians assigned per line; status timeline and **activity trail** of notes, findings and photos (§2.3) | — | **Parts are issued here.** Issuing a part creates a stock movement (out) at **cost price**; returning an unused part reverses it |
| **Invoice** | Final bill | Created from the repair order. Final prices are editable until the invoice is **issued**; after that it is locked and can only be corrected by a credit note | Advances are applied automatically. Payments are recorded (each with evidence). Status: Unpaid / Partially paid / Paid / Written off | None. The parts were already issued on the repair order. (Counter-sale invoices take stock out on issue; see §2.1) |
| **Gate pass / exit** | The car leaves | Exit odometer and handed-over-by. Blocked if the invoice has a balance, unless an admin overrides with a reason | — | — |

**Rules**
- A stage can't be skipped. Admins may create a quotation directly for a phone estimate; such a visit has no check-in until the car arrives.
- **One visit can produce only one issued invoice.** Extra work after the invoice goes on a new visit, or on a supplementary invoice linked to the same visit.
- Cancelling at any stage needs a reason. Cancelled documents stay visible.
- **The Visit Dossier (printable) [R1]** is one PDF for the whole visit:
  - check-in sheet with photos;
  - job card;
  - every quotation version;
  - repair order with its timeline;
  - invoice;
  - every payment receipt with its proof attached;
  - gate pass;
  - the audit trail (who did what, when).

  It is printable from the visit page and also sendable on WhatsApp.

### 2.1 Counter sale (parts only, no car) [D10, D11]
Example: a walk-in customer buys a headlight and nothing else.

- **New → Counter sale** opens a short invoice form:
  - **Customer:** optional. Pick an existing customer or leave it as "Walk-in". The name and phone are optional but encouraged, so the customer can get a WhatsApp receipt and onboarding.
  - **Car:** optional. If one is picked, the sale also appears in that car's history ("parts bought over the counter").
  - **Lines:** scan the barcode or search inventory. **Parts only.** Labour lines aren't allowed (any work on a car goes through a visit).
  - **Prices:** each line uses the item's sale price. Editing it is allowed, but going below cost needs the `discount-approve` permission.
  - **Stock:** each line shows the stock available. An item can't be sold below zero stock unless an admin overrides with a reason.
- **Issue** does all of the following in one transaction:
  - takes the stock out (a movement for each line, at cost);
  - posts the revenue and cost of goods sold;
  - takes payment straight away: cash, card, transfer or split, each recorded on Money In with its proof;
  - prints an 80mm thermal receipt or A4.
- **Returns:** a credit note against the counter sale puts the stock back and refunds through Money Out with proof. The original invoice is never edited.
- **Numbering:** counter sales have their own series, e.g. `CS-A1F3-000045`.
- **Reports:** they show up in reports as their own channel ("Counter sales" vs "Workshop") in revenue, margin and top-selling items.

**Stock rules for both kinds of invoice:**

| Event | Stock effect |
|---|---|
| Job card / quotation | None. Shortages are shown, and stock can optionally be reserved |
| Part issued on a repair order (scan) | **Out**, at cost, linked to the repair order line |
| Part returned from a repair order | **In** (reverses the issue) |
| Workshop invoice issued | None. It bills what was issued; the system checks that every invoiced part line matches an issued quantity |
| Counter-sale invoice issued | **Out**, at cost |
| Credit note (return) | **In** |

There is no "Check & Deduct" button and no way to issue the same part twice.

### 2.2 Quotation statuses and approval [D12]
```
Draft ──send──► Sent ──► Approved ──► (repair order created) ──► Converted
                  │  ╲
                  │   ╲──► Rejected (reason required)
                  └──► Expired (after the validity period, default 7 days; can be revived as a new version)
```

| Action | Rules |
|---|---|
| **Send** | Locks the version. Sends the PDF on WhatsApp and/or prints it |
| **Approve** | Records who approved it, when, and **how**: in person (customer signs on a tablet or a signed paper photo), WhatsApp reply (screenshot), or phone call (the staff member's note). Proof is required unless the user has `quote-approve-without-proof` |
| **Partial approval** | The customer approves some lines only; rejected lines are kept on the quote but marked declined |
| **Revise** | After sending or approval, a revision creates v2 and returns it to Draft. The earlier approval stays in history but no longer counts; v2 needs its own approval |
| **Create repair order** | Only from an **Approved** version. It carries the approved lines and the agreed prices |
| **Advance** | Can be taken at Sent or Approved. It is held as a customer advance (a liability, not income) until the invoice uses it |

- **Quotes list:** tabs for Draft, Sent, Approved, Rejected, Expired and Converted, with conversion-rate figures in the Operations report.
- **Follow-up:** a quote stuck in Sent for 3 days gets an automatic WhatsApp follow-up (configurable).

### 2.3 Repair-order activity trail [D13]
Every repair order has an **Activity** panel: a single timeline of everything that happened to the car, written as it happens.

| Entry type | Who adds it | Content |
|---|---|---|
| **Status change** | Automatic | from → to, user, time. **A note is required** when moving back a stage (e.g. Testing → Repair) or putting the job On hold |
| **Diagnosis finding** | Technician | what was found, linked to the job-card or repair-order line it affects, optional photos. Findings can add a line ("found worn brake pads"), which goes back to the customer for approval as a **supplementary quote** |
| **Work note** | Technician / supervisor | free text per line or for the whole job ("waiting for paint to cure") |
| **Photo / video** | Anyone | before, during and after photos, tagged with the stage. Before/after pairs go into the visit record |
| **Parts event** | Automatic | issued / returned, item, quantity, by whom |
| **Customer update** | Front office | a note marked **customer-visible**, which can also be sent on WhatsApp ("Your car is in testing, ready by 5pm") |
| **Hold / resume** | Supervisor | reason (waiting for parts, customer approval, payment). Hold time is excluded from turnaround figures |

- **Visibility:** entries are **internal** by default; only those marked customer-visible go into the customer's copy of the visit record and WhatsApp updates.
- **Statuses:** Received → Diagnosis → Awaiting approval → In repair → Testing → Ready → Delivered, plus On hold (from any stage). Each change is timestamped, which gives time-in-stage figures for the Operations report.
- **Vehicle condition:** captured at the visit check-in (§2: photos, odometer, fuel, body-damage marks, items left in the car), not on the repair order. The repair order shows it read-only at the top.
- **Delivery:** the condition at exit (photos, odometer) is captured on the gate pass. Check-in and exit are shown side by side in the visit record.

### 2.4 Vehicle inspection report [D14]
The owner's two-page paper form ([docs/reference/Germanato_Vehicle_Inspection_Report.pdf](reference/Germanato_Vehicle_Inspection_Report.pdf)) becomes a digital inspection, filled in on a tablet or phone at the car and printed in the same layout.

**Three kinds**, chosen when the inspection is started:

| Kind | When | Linked to | Billing |
|---|---|---|---|
| **Workshop** | At check-in, or during diagnosis | The visit (§2) | Usually free; its findings feed the job card |
| **Delivery** | At the gate pass, before the car leaves | The visit; shown next to the check-in | Free |
| **Pre-purchase** | A buyer brings a car they are thinking of buying | Its own visit. The car may belong to the **seller**; buyer and seller are both recorded | Billed: a labour code such as `INSP-PRE`, invoiced like any other work, or as a counter sale |

**Sections** (same order and wording as the paper form):

| # | Section | Captured as |
|---|---|---|
| 1 | Vehicle & customer details | Pre-filled from the car and customer. Adds: year, engine no., fuel (Petrol / Diesel / Hybrid / EV); for pre-purchase, buyer and seller with phones |
| 2 | Exterior / body / paint | 16 items (bumpers, bonnet, roof, boot, each fender, door and quarter, glass, lamps, mirrors, panel gaps), each with a rating |
| 3 | Paint / accident check | Paint-meter findings per panel (Original / Repaint / Filler / Replaced), accident finding (no obvious structural repair / repair signs found), notes on chassis, apron, pillars and floor |
| 4 | Tyres & wheels | Tread in mm and % for FL, FR, RL, RR, the spare, and whether the wheels are damaged |
| 5 | Engine / transmission / mechanical | 16 items, each rated |
| 6 | Suspension / steering / brakes | 10 checks |
| 7 | Electrical / interior | 10 checks, plus notes |
| 8 | Diagnostic scan | Tool, scan date, 12V battery (rest / running), warning lights, modules not communicating, and a **fault-code table**: module, DTC, description / status, priority |
| 9 | Hybrid / EV (only if the fuel is Hybrid or EV) | HV battery SOC %, SOH % / kWh, pack voltage, cell imbalance mV, isolation MΩ, AC / DC charging OK or issue, cooling OK or issue, notes |
| 10 | Road test | 12 items, each rated |
| 11 | Repairs / estimated work required | Rows of priority, repair or part, remarks, estimated cost |
| 12 | Overall assessment | Condition (Excellent / Good / Average / Poor), recommendation (Recommended / Recommended after repairs / Not recommended), immediate repair budget (PKR), inspector summary, inspector name and signature, customer/buyer acknowledgement and signature, inspection time, odometer |

**Ratings and the "N/A" problem.** The paper form uses G = Good, A = Average, N/A = Needs Attention and N/C = Not Checked. Everyone reads "N/A" as "not applicable", so a customer could take a car that needs attention to mean "this item doesn't apply".
- **On screen:** the ratings are shown as full words, with colour: Good, Average, **Needs attention**, Not checked.
- **On the printed form:** the code becomes **NA = Needs attention**, with the legend printed on every page. ✅ Owner confirmed, 2026-10-28.
- **Unrated items:** an item nobody rated is saved and printed as Not checked, never as Good.

**Working on a tablet:**
- Each item is a row of four large rating buttons (at least 44px), plus a note and a photo or video from the camera.
- **"Mark section Good"** fills a section in one tap. The inspector then changes only the exceptions, and the activity trail records that the bulk action was used.
- The form saves as you go, so a lost signal or a closed tab loses nothing, and it works offline on the branch server (§6).
- Sections can be skipped. Hybrid / EV is hidden unless the fuel is Hybrid or EV.
- **Signatures:** the inspector and the customer or buyer sign on the screen, stored as proof attachments. The inspector field is the signed-in user.

**What it feeds:**
- **Section 11 → job card:** each repair row can be sent to the visit's job card in one tap (§2), as a labour code or an inventory part. The estimated cost becomes the proposed price on the quotation. The customer can see the finding, its photo and the price side by side.
- **Delivery inspection:** compared item by item against the check-in. Anything that got worse while the car was in the workshop is flagged before the gate pass.
- **Car history (R2):** every inspection is listed with its date, odometer and overall condition; tyre tread and battery health show their trend across visits.
- **Reports:** inspections done per inspector, pre-purchase inspections billed, and the most common "Needs attention" items.

**Output:**
- **The printed report** follows the paper layout: two A4 pages, the logo, numbered as `INS-A1F3-000123`. Photos go in an appendix, and the disclaimer is printed word for word: "Condition is recorded as observed at inspection time; this is not a warranty…"
- **Sharing:** the report can be sent as a PDF on WhatsApp and is included in the visit record (§2, R1).
- **Locking:** once signed by the inspector and customer, the inspection is **locked**. A correction creates a new version, and the signed one is kept.

**Template:**
- The sections and items are stored as a **versioned template**, so the owner can add or rename an item later without a code change.
- Each saved inspection keeps the template version it was filled in on, so old reports print exactly as they were signed.

---

## 3. Requirement by requirement

### [R2] Car history
- **Car page:** a timeline of every visit, newest first. Each visit shows its dates, odometer readings, complaint, work done (labour codes), parts installed (with part numbers), technicians, invoice total, paid amount, and links to every document.
- **Search:** by plate, VIN, chassis, customer code or phone.
- **Extras:** an odometer chart across visits, and "parts installed on this car" (useful for warranty and repeat-failure checks).
- **Owners:** history stays with the **car**, not the owner. Each visit shows the owner at that time.

### [R3] Purchase orders drive stock and cost
| Step | What happens |
|---|---|
| PO | Vendor and lines of existing inventory items (by barcode/MPN; "+ New item" inline) with quantity and agreed cost. Status: Draft → Sent → Partly received → Received → Closed / Cancelled |
| **Goods receipt (GRN)** | Records quantities actually received (partial deliveries allowed). Each line creates a stock movement (in), updates the item's **weighted average cost**, and optionally its sale price (shown with the current margin) |
| Vendor bill | Created from the GRN and posted to the vendor payable |
| **Vendor payment** | A Money-Out record with evidence, which reduces the payable |

- The vendor ledger is **derived** from bills and payments. It is never typed by hand, so no running-balance bugs.
- Partial payments are allowed.

### [R4] Labour codes
✅ Owner decision: **codes only, prices stay manual for now.**
- **Fields:**
  - code, e.g. `PNT-DOOR`;
  - name;
  - category: Mechanical, Electrical, Denting, Painting, AC, Diagnostics, Detailing…;
  - optional description;
  - active flag.
- **No rate on the code yet.** On the quotation, each labour line is a labour code plus a **manually entered price** (required, > 0) and an optional quantity (e.g. 3 panels). The price is editable again on the invoice, until it is issued.
- **Editing:** any user with the `labour-codes` permission can add or edit codes from Settings, or inline from the job card ("+ New labour code").
- **Later (no data migration needed):** a `default_rate` column and rate history can be added to make the price pre-fill. The reports already show average charged price per labour code, which gives the owner the numbers to set default rates.

### [R6] Inventory by manufacturer code / barcode
- **Identity:** barcode, or manufacturer part number (MPN) when there is no barcode, is **required and unique** per branch. It is stored normalised (spaces, dashes and dots stripped; upper-case) next to the code as printed.
- **Scanning:** scanning a code anywhere (inventory, job card, PO, GRN) finds the item. An unknown code offers "Create item with this code".
- **Item fields:** name, brand, category, vehicle fitment (make/model/years, optional), unit, cost price (read-only, from GRNs), sale price, reorder level, reorder quantity, bin location, image.
- **Sale price is set by hand per item** (✅ owner decision, no automatic markup). The item screen shows the current margin, (sale − avg cost) ÷ sale, and warns when a GRN pushes the cost above the sale price or the margin below a configurable minimum. The report "Items selling below cost / low margin" lists them.

### [R7] Car transfer
- The car's owner changes through a **Transfer** action, which records:
  - from and to customer;
  - date;
  - reason;
  - odometer;
  - document proof (optional);
  - who did it.
- The ownership-periods table answers "who owned this car on date X".
- Past visits keep their original owner. Open visits are blocked from transfer until they are closed.

### [R8] No dirty data: error prevention at three layers
1. **Database**
   - foreign keys everywhere;
   - unique constraints (plate per branch, VIN, barcode/MPN, labour code, document numbers);
   - CHECK constraints (amounts > 0, quantity ≠ 0, a status from its enum);
   - `NUMERIC(14,2)` for money, never float.
2. **API (Pydantic)**
   - strict types;
   - normalisers:
     - phone → `+92XXXXXXXXXX`;
     - CNIC → `XXXXX-XXXXXXX-X`;
     - plate upper-case without spaces;
     - VIN 17 characters with no I, O or Q;
   - state-machine checks (an invoice can't be paid before it is issued, etc.);
   - period-lock checks;
   - idempotency key on every create, so a double click or an offline retry never creates duplicates.
3. **UI**
   - the same rules are shared as Zod schemas generated from the API's OpenAPI;
   - pickers instead of free text (customer, car, item, labour code, account);
   - duplicate warnings ("a customer with this phone already exists").
- **Audit:** every create, update, void and print is logged with user, time, branch and device, plus before/after values for edits.

### [R9] Branch id
- Every table has `branch_id` (a short hex id, e.g. `A1F3`, behind a UUID).
- Users belong to one or more branches. Every query is filtered by the active branch.
- Document numbers include the branch code.
- **Shared across branches:** customers and cars (the same car can visit any branch). **Per branch:** stock, cash accounts and documents.
- A later **admin panel** (cloud only) can see across branches.

### [R10] Hybrid cloud / offline: see §6.

### [R11] Finance transparency and SOPs: see §8.

### [R12] Money In page (one place)
Every incoming payment, whatever the source:

| Source | Examples |
|---|---|
| Invoice payment | customer pays the invoice in full or in part |
| Advance | taken on a quotation or repair order |
| Other income | scrap sale, rent, commission |
| Petty-cash top-up | transfer from bank or owner into the cash till (an internal transfer, not income) |
| Owner capital | money put in by the owner |

- **Columns:** date, number, source document link, customer, account (Cash / Bank / Wallet), method, reference (cheque number, transaction id), amount, received by, **proof** (thumbnail), status (Posted / Voided).
- **Filters:** date range, source, account, customer, has-proof / missing-proof, user.
- **Totals** by account and by source. Export to Excel and to a PDF evidence pack.

### [R13] Money Out page (one place)
Every outgoing payment:

| Source | Examples |
|---|---|
| Daily (petty) expense | tea, fuel, utilities |
| Major expense | equipment, rent, renovation |
| Vendor payment | against PO bills |
| Salary | payroll run |
| Employee advance | advance against salary |
| Refund | to a customer |
| Owner drawings | money taken out by the owner |
| Bank-to-cash transfer | internal transfer |

- Same columns, filters and evidence rules as Money In.
- **Expense categories** are a managed list (Settings), so there is no free-text category drift.

### [R14] WhatsApp
- **Provider:** ✅ owner decision: through a **third-party provider (Twilio WhatsApp API)**. The code sits behind a small `MessageSender` interface, so a later switch (Meta Cloud API, 360dialog) only changes one adapter. Twilio needs a WhatsApp-enabled sender number and Meta-approved templates for business-initiated messages; free-form replies are allowed within 24 hours of the customer's last message.
- **Template messages:** invoice issued (with the PDF), quotation sent (with the PDF), car ready for pickup, payment received (receipt), **payment reminder** (automatic at +3, +7 and +15 days on the unpaid balance, configurable), **service reminder** (date-based or mileage-based from the last visit), **welcome/onboarding** after a customer's first visit.
- **Delivery:** a send queue with retries. Delivery and read status come back by webhook. A per-customer opt-out is honoured. Every message is logged on the customer and the visit.
- **No placeholders:** templates are filled only from settings (workshop phone, address); sending is blocked if a placeholder is unfilled.

### [R15] Monthly and yearly closing
**Month-end close wizard** (accountant prepares, admin approves). Checklist:
1. Every Money In/Out record in the month has its proof (or an explicit "no proof" reason signed by an admin).
2. Cash count matches the system for each cash account. The difference is posted as a *cash over/short* with a reason.
3. Bank balance matches the statement (upload the statement PDF).
4. No draft or unissued documents dated in the month.
5. Stock count, at least for the cycle-count list. Differences are posted as adjustments with a reason.
6. Payroll has been run.

**On approval:**
- The period is **locked**.
- A **Closing Pack** is generated: a PDF report plus a ZIP of every proof file, indexed by record number, and stored with the period.

**Reopening** needs an admin and a reason. It is audit-logged and the closing pack is regenerated.

**Year-end close:** requires all 12 months closed. It produces the annual P&L, balance summary, receivables and payables at year end, stock valuation, and carries balances forward.

### [R16, R17] Reports with drill-down: see §7.

---

## 4. Data model (core tables)

All tables have: `id uuid (v7)`, `branch_id` (except global tables), `created_at`, `created_by`, `updated_at`, `updated_by`, `version` (for sync), `deleted_at` (only for non-financial master data).

| Area | Tables |
|---|---|
| Org | `branches`, `users`, `user_branches`, `roles`, `role_permissions`, `settings` (per branch: tax rate, numbering, workshop details, WhatsApp config) |
| Customers & cars | `customers` (global), `cars` (global), `car_ownerships` (car, customer, from, to, transfer reason, proof) |
| Workshop | `visits`, `visit_checkins` (+ `visit_photos`), `inspection_templates` (versioned JSON: sections, items, field types), `inspections` (kind workshop / delivery / pre-purchase, visit, car, buyer, seller, template version, status draft / signed, overall condition, recommendation, budget, signatures) + `inspection_items` (item key, rating good / average / needs-attention / not-checked, note, photos) + `inspection_tyres` + `inspection_dtcs` + `inspection_repairs` (priority, repair, remarks, estimated cost, sent-to-job-card link), `job_cards` + `job_card_lines`, `quotations` (versioned) + `quotation_lines` + `quotation_approvals` (who, when, method, proof, approved lines), `repair_orders` + `repair_order_lines` + `repair_order_activity` (status changes, findings, notes, photos, parts events, customer updates, holds; with an internal/customer-visible flag), `invoices` (kind: workshop / counter sale; visit optional for counter sales) + `invoice_lines`, `credit_notes`, `gate_passes` |
| Catalogue | `labour_codes` (no rate yet; see §3 R4), `inventory_items`, `item_codes` (barcode/MPN aliases), `item_price_history` |
| Stock | `stock_movements` (item, qty ±, unit cost, type: grn / issue / return / adjustment / transfer, source doc), view `stock_levels` |
| Purchasing | `vendors`, `purchase_orders` + lines, `goods_receipts` + lines, `vendor_bills` |
| Money | `accounts` (Cash till, Bank X, JazzCash…), `payments` (direction in/out, account, amount, method, reference, source doc type+id, party, status, voided_by/reason), `payment_allocations` (one payment against several invoices or bills), `expense_categories`, `journal_entries` + `journal_lines` (auto-posted) |
| Evidence | `attachments` (file hash, mime, size, storage key, linked record type+id, uploaded_by). Stored in S3-compatible storage in the cloud, on local disk in the branch, synced |
| HR | `employees`, `attendance` (punches + daily summary), `devices` (ZKTeco; push accepted only from registered serials, optional shared secret), `salary_advances`, `payroll_runs` + lines |
| Periods | `periods` (month, status open/closing/closed, closed_by, pack attachment), `period_checklist_items` |
| Messaging | `message_templates`, `messages` (queue + status), `customer_optouts` |
| Audit & sync | `audit_log`, `sync_outbox`, `sync_cursor` |

**Accounting under the hood (D3).** Each business event posts a balanced journal automatically:

| Event | Debit | Credit |
|---|---|---|
| Invoice issued | Receivables | Revenue-Labour / Revenue-Parts / Tax payable |
| Part issued on a repair order | Cost of parts sold | Inventory |
| GRN | Inventory | Goods received not billed |
| Vendor bill | Goods received not billed | Payables |
| Payment in | Cash/Bank | Receivables (or Customer advances) |
| Payment out | Expense / Payables / Salaries | Cash/Bank |

Users only ever see documents and payments. The journal gives a trial balance that must be zero, a provable P&L and a provable balance sheet, which is what makes the month-end close trustworthy.

---

## 5. Permissions
- The current model is kept: roles hold permissions, and each permission gates both pages and API routes.
- **Checking:** permissions are checked on the server **only**; the UI hides what the user can't use. The current app's split between "role fallback" and "permission table" goes away: one table, seeded with the defaults.
- **New permissions:** `visits`, `job-cards`, `quotations`, `repair-orders`, `invoices`, `invoice-issue`, `payments-in`, `payments-out`, `labour-codes`, `inventory`, `purchasing`, `goods-receipt`, `vendors`, `hr`, `payroll`, `reports-finance`, `reports-ops`, `period-close`, `period-approve`, `settings`, `users`, `audit`.
- **Approval limits** (optional): discount above X% needs `discount-approve`; voiding a payment needs `payments-void`.

---

## 6. Offline-first hybrid [R10]

### Options considered
| Option | How it works | Verdict |
|---|---|---|
| A. Browser-only offline (PWA + IndexedDB per device) | Each tablet/PC keeps its own copy and syncs to the cloud | ✗ Several devices in one workshop would be offline from each other. ZKTeco devices and printers need a LAN server anyway. Hard to make financial records consistent |
| **B. Branch server + cloud (recommended)** | A small PC (or mini-PC) in the workshop runs the same FastAPI + Postgres + Next.js. All workshop devices use it over Wi-Fi/LAN, so they work fully without internet. A sync worker pushes and pulls changes to the cloud when online | ✓ Every device sees the same data instantly. ZKTeco pushes to the local server. Cloud gives owner access from anywhere plus backups |
| C. Cloud only | — | ✗ Fails the requirement |

### Sync design (option B)
- **Who writes what**
  - Every record has a UUIDv7 id and is owned by the branch that created it. Only that branch's server writes its documents, payments and stock movements. The cloud receives them read-only, so financial records never conflict.
  - **Shared master data** (customers, cars, labour codes, items): either side can edit. Field-level last-writer-wins by `updated_at`, plus a conflict log an admin can review. Unique-key clashes (the same phone created in two places) are flagged for merge, not silently overwritten.
- **Transport:** an outbox table records every change, and the sync worker sends batches with idempotency keys. The cloud acknowledges, then the worker pulls changes from other branches and the admin panel using a cursor.
- **Stock and money merge safely:** both are append-only ledgers of movements and payments, so syncing never needs to merge a number.
- **Files:** attachments sync separately (content-hash dedupe) and are queued while offline.
- **Owner's view:** the owner (cloud) sees "last synced at" per branch. Reports in the cloud show data as of that sync.
- **Phasing:** build the app first with all of the above built in (UUIDs, branch_id, outbox written on every change). Turn the sync worker on in a later phase. Doing the data design now avoids a rewrite later.

---

## 7. Reports: numbers with proofs [R16, R17]

**The rule:** every figure is a link. Clicking it opens the filtered list of the records that make it up. Each record opens the document, and each document shows its attached proofs.

Examples:
- Receivables → unpaid and partly paid invoices (with aging buckets) → invoice → payments → receipt images.
- Expenses → expense list → receipt.
- Stock value → item list → movement ledger → GRN or repair order.

| Dashboard | Figures (each one drills down) |
|---|---|
| **Owner overview** | Net profit/loss (month, YTD, custom); revenue by channel (workshop vs counter sales); cash in hand per account; money in vs out; receivables total + aging (0–30, 31–60, 61–90, 90+); payables to vendors; stock value at cost; cars in the workshop now; alerts (missing proofs, overdue invoices, low stock, unclosed months) |
| **Finance** | P&L: revenue split labour/parts, cost of parts sold, gross margin, expenses by category, salaries, net profit. Cash flow by account. Money In/Out by source. Advances held (customer money not yet earned). Discounts given (by user). Voids and reversals. Missing-evidence list |
| **Receivables** | Every unpaid or partly paid invoice: customer, car, issued date, days overdue, last reminder sent, payments so far with proofs; one-click WhatsApp reminder |
| **Inventory** | Stock value, low stock / out of stock, slow-moving (no movement in N days), fast-moving, margin per item, stock adjustments (shrinkage) with reasons, PO pipeline (ordered, not received) |
| **Operations** | Visits by status; average turnaround (check-in → gate pass) and per stage; revenue per visit; top labour codes; repeat visits / comebacks within 30 days; quotation conversion rate; open repair orders aging |
| **HR** | Attendance summary, late/absent days, payroll cost by month, advances outstanding, technician productivity (labour hours billed per technician from repair-order lines) |
| **Customers & cars** | New vs returning customers, top customers by revenue, cars due for service, customer lifetime value |

All reports export to Excel and to PDF. For finance reports, the PDF export includes the proof index.

---

## 8. SOPs: how to use the software to get clean, provable books [R11]

1. **Car in.** Open a visit and do the check-in at the gate: photos of all four sides, odometer, fuel, complaint, valuables. The customer signs. *Outcome: no "the scratch was already there" disputes.*
2. **Estimate.** The technician fills the job card from labour codes and inventory only. A missing part is created by scanning its barcode, never typed as free text.
3. **Quote and advance.** Front office prices the quotation and sends it on WhatsApp. Any advance is recorded **at once** as a payment, with a photo of the cash or a screenshot of the transfer.
4. **Repair.** Parts are issued to the repair order **at the moment they leave the store**, by scanning. Unused parts are returned the same day. Status is updated at each stage.
5. **Invoice and exit.** The invoice is issued from the repair order. No gate pass while there is a balance, unless an admin approves credit with a reason.
6. **Every rupee out** is entered on Money Out the same day, **with a receipt photo**. With no receipt, a signed voucher photo plus the reason. Petty cash comes only from the "Cash till" account.
7. **Every rupee in** is entered on Money In against its document. No cash is kept outside the till.
8. **Daily close (5 minutes):** count the cash till; the system shows the expected amount; post the difference with a reason. Attach the day's bank screenshots.
9. **Purchases:** every vendor purchase is a PO → GRN (count on arrival) → bill → payment. Prices update only through the GRN.
10. **Monthly close:** run the close wizard by the 5th of the next month. The admin reviews the checklist and the closing pack, then approves. The month is then locked.
11. **Corrections:** never delete. Void with a reason, or issue a credit note or adjustment. Both the original and the correction stay on the record.
12. **Access:** each person has their own login (no sharing). Roles follow job duties: the cashier can't approve discounts, the technician can't see finance.

---

## 9. Delivery phases (replaces Phase 1–2 of MIGRATION_PLAN.md)

There is no production data to carry over, so this is a **new build** that uses [feature-inventory](feature-inventory/README.md) as the checklist of behaviour to keep, minus the bugs listed there.

| Phase | Scope | Est. |
|---|---|---|
| **0** (done) | Feature inventory; Postgres; Alembic; contract tests of the old app (reference only) | — |
| **1. Foundation** | Monorepo (`api/` FastAPI, `web/` Next.js), auth with httpOnly cookies, users/roles/permissions, branches, settings, audit log, attachments, UUIDv7 + outbox written from day 1, CI | 2 wk |
| **2. Catalogue & people** | Customers, cars, ownership transfer [R7], car history page [R2], labour codes [R4], inventory items with barcode/MPN [R6], stock movements | 2–3 wk |
| **3. Workshop chain** | Visit/check-in → **vehicle inspection** (workshop / delivery / pre-purchase, printable, findings → job card) [D14] → job card → quotation (versions, approval, advance) → repair order (issue parts, activity trail) → invoice → gate pass, plus the Visit Dossier PDF [R1, R5]; **counter sales** with receipt printing [D11] | 6–7 wk |
| **4. Purchasing** | Vendors, PO → GRN → bill → payment, weighted average cost, vendor ledger [R3] | 2 wk |
| **5. Money** | Accounts, Money In / Money Out pages [R12, R13], expense categories, journal posting, daily cash close, evidence rules [R11] | 2–3 wk |
| **6. HR** | Employees, attendance (ZKTeco push secured), advances, payroll posting to Money Out | 2 wk |
| **7. Closing & reports** | Month and year close wizard with closing pack [R15], dashboards with drill-down [R16, R17] | 3 wk |
| **8. WhatsApp** | Templates, queue, webhooks, reminders, onboarding [R14] | 1–2 wk |
| **9. Offline sync** | Branch server packaging (Docker on the workshop PC), nightly backups, sync worker to the cloud, conflict review screen [R10]. Cloud admin panel and inter-branch stock transfers are deferred until the 2nd branch [R9] | 2–3 wk |

Total ≈ **23–29 weeks** for one developer, or about half that with two working in parallel after Phase 1. Each phase ends usable on its own; the workshop can start on the new system after Phase 5.

---

## 10. Owner decisions (answered 2026-10-28)

| # | Question | Decision | Effect on the spec |
|---|---|---|---|
| 1 | Tax | **17% on parts and labour, toggled per invoice/quotation** (rate in settings) | D8. Tax is computed per line with one rate; no FBR/PRA integration |
| 2 | Advances | **Optional; refundable only with admin approval** | An advance is held as a customer advance (a liability). If a job is cancelled, the refund is a Money Out with proof plus an admin approval (`advance-refund`). Otherwise the advance is applied to the invoice |
| 3 | Credit (unpaid balance at exit) | **Only with admin approval per visit** | The gate pass is blocked while there is a balance, unless an admin approves with a reason. The approval is logged, and the invoice shows "Released on credit by X". No standing credit limits |
| 4 | Proof rule | **Always, with a "no proof" reason as fallback** | Every money record asks for an attachment. Saving without one requires a reason, and the record is flagged "missing proof": it appears on the Missing Evidence report and blocks month-end close until an admin signs off each one |
| 5 | Parts pricing | **Manual sale price per item** | D2; margin warnings only (§3 R6) |
| 6 | Labour | **Codes only; prices manual for now** | §3 R4. A price is entered per line on the quotation; default rates can come later |
| 7 | Branches | **One now, more later** | `branch_id` on every table from day one; one branch seeded. Inter-branch stock transfers and the cloud admin panel are built when the 2nd branch opens (Phase 9 scope shrinks to sync + backup) |
| 8 | Hardware | **Have:** 1 PC (local server), 1 laptop (inventory manager), 1 printer. Rest per our suggestion | See §11 |
| 9 | WhatsApp | **Third-party provider (Twilio)** | D9; §3 R14 |
| 10 | Existing `nyctosys/GermanAto` rewrite | **Build new here, push to a `dev` branch** | Fresh build from this spec. ⚠️ `nyctosys/GermanAto` already has a `dev` branch with the other rewrite's commits and unrelated history. Pushing there needs either a **new branch name** (e.g. `dev-next`) or an explicit OK to replace that `dev` (after backing it up). Confirm before the first push |

## 11. Hardware recommendation (one workshop)

| Item | Status | Recommendation | Why |
|---|---|---|---|
| Local server PC | ✅ have | Runs Postgres + API + web app (Docker), on wired Ethernet with a **static LAN IP**, set to restart automatically after a power cut. **Needs:** an SSD and at least 8 GB RAM; Windows or Linux are both fine | Every device in the workshop uses it, even with no internet |
| UPS for the server + router | **buy** | 650–1000 VA line-interactive UPS | Load-shedding must not corrupt the database. The app also takes nightly local backups and syncs to the cloud when online |
| Wi-Fi router | check | Any decent router; the server on a cable, other devices on Wi-Fi | — |
| Inventory laptop | ✅ have | Browser only (Chrome/Edge) pointed at the server | — |
| Barcode scanner | **buy 1–2** | USB or Bluetooth **keyboard-mode (HID)** 1D/2D scanner that sends the code + Enter (e.g. Zebra DS2208, Honeywell 1470g, or a budget 2D scanner) | Scanning drives stock in (GRN), parts issue and counter sales. HID mode needs no driver |
| Printer | ✅ have 1 | Used for A4 documents: quotations, repair orders, invoices, the visit record, closing reports | — |
| 80mm thermal printer | **optional, recommended** | Epson TM-T82/T20 class (USB/LAN) | Fast counter-sale receipts and payment slips; A4 still works without it |
| Phone or tablet for check-in | **use a staff phone now; tablet later** | Any Android phone/tablet with a camera, using the app in the browser (installable as a PWA) | Check-in photos, damage marks, customer signature on screen |
| Label printer | later | 2-inch thermal label printer | Only needed for items without a manufacturer barcode (print an internal barcode) |
| Cloud | — | Small VPS or managed Postgres + object storage for proof files; daily encrypted backups | Off-site copy, owner access from outside, multi-branch later |
