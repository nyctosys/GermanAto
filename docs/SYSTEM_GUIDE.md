# GermanATO: system guide

This guide describes the software **as it is built today**, module by module: what each part is for, how to use it, the rules the system enforces, and where it lives. It is updated in the same commit as every change, so it always matches the code. The plan for what comes next is in [NEW_SYSTEM_SPEC.md](NEW_SYSTEM_SPEC.md).

Last updated: 28 Oct 2026, Phase 4 (purchasing: vendors, purchase orders, goods received, bills, vendor payments).

## Contents

1. [What is built](#1-what-is-built)
2. [The life of a car in the workshop](#2-the-life-of-a-car-in-the-workshop)
3. [Signing in, roles and permissions](#3-signing-in-roles-and-permissions)
4. [Customers and cars](#4-customers-and-cars)
5. [Labour codes and inventory](#5-labour-codes-and-inventory)
6. [Check-in (the visit)](#6-check-in-the-visit)
7. [Vehicle inspection report](#7-vehicle-inspection-report)
8. [Job card](#8-job-card)
9. [Quotation](#9-quotation)
10. [Advances and payments (money in)](#10-advances-and-payments-money-in)
11. [Repair order](#11-repair-order)
12. [Invoice](#12-invoice)
13. [Counter sale](#13-counter-sale)
14. [Gate pass](#14-gate-pass)
15. [Visit record and printed documents](#15-visit-record-and-printed-documents)
16. [Administration](#16-administration)
17. [Rules that protect the data](#17-rules-that-protect-the-data)
18. [Not built yet](#18-not-built-yet)
19. [For developers](#19-for-developers)

Purchasing is [section 20](#20-purchasing). Money (accounts, money in and out, journal, cash close) is [section 21](#21-money).

---

## 1. What is built

| Area | Status | Screens |
|---|---|---|
| Sign-in, users, roles, audit log, branch settings | Built | Login, Users, Roles and permissions, Audit log, Branch settings |
| Customers and cars (one central record each) | Built | Customers, Cars, customer page, car page with history |
| Car ownership transfer | Built | Car page |
| Labour codes | Built | Labour codes |
| Inventory (barcode / part number, stock movements) | Built | Inventory, item page |
| Check-in | Built | Cars in the workshop, Check in a car, visit page |
| Vehicle inspection report (workshop, delivery, pre-purchase) | Built | Inspection page, printed report |
| Job card | Built | Job card page |
| Quotation with versions, approval, rejection | Built | Quotations, quotation page, printed quotation |
| Advances | Built | Quotation page |
| Repair order with parts issue and activity trail | Built | Repair orders, repair order page |
| Workshop invoice and payments | Built | Invoices, invoice page, printed invoice |
| Counter sale (parts over the counter) | Built | New counter sale, printed A4 invoice |
| Gate pass, with release on credit | Built | Visit page, printed gate pass |
| Visit record (the whole visit on paper) | Built | Printed visit record |
| Vendors, purchase orders, goods received, vendor bills, vendor payments, vendor account | Built | Vendors, Purchase orders, Bills and payments, printed purchase order |
| Money out pages, expenses, accounts, closing, reports, HR, WhatsApp, offline sync | Not yet | See [section 18](#18-not-built-yet) |

---

## 2. The life of a car in the workshop

```
Check in ─► Inspection (optional) ─► Job card ─► Quotation ─► Approval ─► Repair order ─► Invoice ─► Payment ─► Gate pass
              findings                 work list     prices       proof        parts out       final bill   proof     car leaves
                                                     advance ◄───────────────────────────────────────────── applied
```

Everything hangs off the **visit**. Each document is made **from** the one before it and links back to it, so a visit can always be followed from entry to exit. A stage can't be skipped: there is no quotation without a job card, no repair order without an approved quotation, and no invoice without a repair order that is Ready.

The visit page shows where the job stands in its **The job** panel: job card, quotation (with its status), advance received, repair order (with its stage) and invoice. Each row opens that document.

---

## 3. Signing in, roles and permissions

- Each person has their own username and password. After **5 wrong passwords** the account is locked for **15 minutes**.
- A session lasts until sign-out. The browser keeps only a secure cookie; nothing about the session is readable by page scripts.
- Every screen and every API call checks a **permission**. A role is a named set of permissions; an Admin role has them all.

| Permission | Allows |
|---|---|
| `dashboard` | See the dashboard and labour codes |
| `settings` | Edit branch settings (name, contact details, tax rate) |
| `users` | Manage users and roles |
| `audit` | Read the audit log |
| `attachments` | Upload and view proof files |
| `customers` | See and edit customers and cars |
| `car-transfer` | Transfer a car to another owner |
| `labour-codes` | Add and edit labour codes |
| `inventory` | See stock and add or edit items |
| `stock-adjust` | Correct stock levels (opening stock, counts, write-offs) |
| `visits` | Check cars in and out, run inspections, release cars at the gate |
| `job-cards` | Write job cards |
| `quotations` | Price and send quotations, record approvals |
| `repair-orders` | Work repair orders and issue parts |
| `invoices` | Prepare invoices and counter sales |
| `invoice-issue` | Issue invoices (locks the prices) |
| `payments-in` | Record money received |
| `release-on-credit` | Let a car leave with an unpaid balance |
| `vendors` | Add and edit vendors, see what is owed to them |
| `purchasing` | Write and send purchase orders, record and void vendor bills |
| `goods-receipt` | Count stock in against a purchase order |
| `payments-out` | Pay vendors (and void a vendor payment) |
| `expenses` | Record daily and major expenses |

Roles set up at the start: **Admin** (everything), **Accountant** (including vendors and paying them), **Inventory manager** (including vendors, purchase orders and receiving stock). More roles (front desk, technician, cashier) are made under Roles and permissions. A role that already exists keeps the permissions it had: tick the four purchasing permissions on it under Roles and permissions to use purchasing.

Purchasing deliberately splits the work: the person who orders and counts the goods in cannot pay the bill, and the person who pays cannot receive stock.

---

## 4. Customers and cars

**One record per customer and per car, used everywhere.** Check-in, inspections, quotations, repair orders and invoices all read the same customer and car records, and the **Vehicle and people** panel on each of those pages has **Edit** buttons that change the central record. A correction made in one place shows everywhere.

### Customers
- Name, type (individual or company), mobile (required), other phone, email, CNIC, address, notes, "Don't send WhatsApp messages".
- Phones are stored as `+92…` whatever the format typed (`0300-1234567`, `92300…`). CNIC is stored as `35202-1234567-1`.
- **Duplicate phone:** saving a customer whose phone is already on file shows the existing record first. A second record is only made if you confirm it really is someone else (for example, family sharing a phone).
- Inactive customers are hidden from searches but keep their history.
- Numbers: `CUS-A1F3-000001`.

### Cars
- Number plate, make, model, year, fuel, colour, **VIN / chassis number** (one field; it takes a 17-character VIN or a local chassis number like `NZE141-6012345`), engine number, odometer, notes.
- The same plate or the same VIN / chassis can't belong to two cars. Matching ignores spaces and dashes.
- A car has exactly one current owner.
- **Transfer** (permission `car-transfer`): moves the car to another customer with a date, reason and odometer. The previous owner stays in the car's history.

### Car history
The car page lists, newest first: owners, visits, signed inspections, issued invoices and counter sales for that car, and edits to the car's details (who changed which fields).

---

## 5. Labour codes and inventory

### Labour codes
- A code (`SRV-OIL`), a name, a category and a description. Codes are letters, digits and dashes, unique per branch.
- **No price on the code.** The price is entered on each quotation (owner decision 6).

### Inventory
- Each item has an internal number (`ITM-A1F3-000001`), name, brand, category, unit, fitment, shelf location, **sale price** (set by hand), reorder level and quantity, and any number of **barcodes and manufacturer part numbers**. A scanned code finds its item wherever there is a search box.
- **Stock is never typed in.** The quantity on hand is the sum of stock movements: opening stock, adjustments, goods received, parts issued and returned on repair orders, counter sales.
- Stock can't go below zero. Two people taking the last unit at once can't both succeed.
- Parts leave stock at **average cost**; the average is recalculated when stock comes in.
- The item page shows every movement with who made it and why. Adjustments need `stock-adjust` and a reason.

---

## 6. Check-in (the visit)

**Where:** Cars in the workshop → Check in a car.

1. Find the car by plate, VIN / chassis or owner's name. (A new car is added from its owner's page first.)
2. Check the **Vehicle and people** panel; edit anything wrong there.
3. Choose the visit type: **Repair or service**, or **Pre-purchase inspection**. A pre-purchase visit needs the **buyer** (a customer on file; the car's owner is the seller).
4. Record what the customer says, the odometer, the fuel level (tap the gauge), photos of all four sides, existing damage and valuables left in the car.
5. The customer signs on the screen. **Check in.**

Rules:
- A car can be checked in only once at a time. Trying again opens the visit already open.
- The odometer can't be lower than the last reading on file.
- Visit numbers: `VIS-A1F3-000001`.
- **Cancelling a visit** needs a reason, and is refused once money has been taken, parts have been issued or an invoice has been issued.

---

## 7. Vehicle inspection report

Three kinds: **Workshop** (at check-in or during diagnosis), **Delivery** (before the car leaves) and **Pre-purchase** (for a buyer).

- 64 checks in five rated sections (exterior, mechanical, suspension and brakes, electrical and interior, road test), rated **G** Good, **A** Average, **NA** Needs attention, **NC** Not checked, each with an optional note and photos.
- Paint and accident check per panel, tyre tread and condition, diagnostic scan (fault codes), hybrid / EV battery checks (shown only for hybrid and electric cars), recommended repairs with estimated cost, and the overall verdict.
- Vehicle and people details come from the central records, not typed again.
- The form saves itself as you work. Two devices editing the same draft are caught: the second one is asked to reload.
- **Signing** needs the overall condition and recommendation. Anything left unrated is recorded as Not checked, never as Good. The vehicle and people details are **frozen** at signing, so later edits to the car don't change a signed report.
- A signed report can't be edited. **Revise** makes a new draft that replaces it and keeps the old one.
- Prints as the A4 report from the owner's paper form.

---

## 8. Job card

**Where:** visit page → The job → Start the job card.

- The work to quote: **labour codes and stock items only**, never free text, so every job is priced and costed the same way.
- Add lines by typing a name or code, or by **scanning a part's barcode**.
- Each part shows how many are in stock; a shortage is flagged in red. Shortages don't stop the quotation.
- Each line has a quantity and an optional note.
- **Make the quotation** saves the job card and creates the quotation from it.
- One job card per visit. Numbers: `JC-A1F3-000001`.

---

## 9. Quotation

**Where:** job card → Make the quotation; or Quotations.

### Pricing (Draft)
- Parts start at the item's sale price. **Labour prices are typed per line.**
- Lines can be added or removed (codes and items only), quantities changed.
- Discount (can't be more than the lines), **sales tax at the branch rate (17%) with an on/off switch**, validity date (7 days by default), notes for the customer.
- Totals: labour, parts, discount, tax on the amount after discount, total.

### Statuses

| Status | Meaning | What you can do |
|---|---|---|
| Draft | Being priced | Edit; **Send** (every line needs a price) |
| Sent | Locked, with the customer | Record approval; Customer said no; Take an advance; Revise |
| Expired | Sent and past its validity date (automatic) | Revise |
| Approved | The customer agreed | Make the repair order; Take an advance; Revise |
| Rejected | The customer said no (reason kept) | Revise |
| Repair order made | Converted | Take an advance |
| Replaced by a revision | An older version | View only |

### Approval
- **How:** in person, WhatsApp reply or phone call.
- **Proof is required**: a photo, screenshot or PDF. With none, a reason must be given ("approved on a phone call"). The record shows who recorded the approval and when.
- **Partial approval:** untick lines the customer declined. They stay on the quotation, struck through, and drop out of the total. At least one line must be approved; otherwise use **Customer said no**.

### Revisions
- **Revise** makes revision 2 (same number, `QT-A1F3-000001`) as a new draft with the same lines and prices. The earlier version stays, approval and all, but no longer counts; the new one needs its own approval.
- Only one revision per visit is current.

### Printing
A4 quotation with the customer, car, lines (declined lines left out), totals, any advance and balance, validity and terms, and signature lines.

---

## 10. Advances and payments (money in)

- **Advance:** taken on a quotation once it is Sent or Approved (or after the repair order is made). It is held as the **customer's money**, not income, until the invoice uses it.
- **Payment:** taken on an issued invoice, up to the balance.
- Every record has the amount, where it went (**Cash**, **Bank transfer**, **Mobile wallet**), a reference, and **proof** (photo, screenshot or PDF) or a reason why there is none. Records without proof are shown with "No proof: …".
- A bank transfer or wallet payment needs its **transaction reference** or a screenshot.
- Receipts are numbered `PAY-A1F3-000001`. Nothing is edited after it is recorded.
- A visit holding money can't be cancelled. A refund of an advance needs admin approval and comes with the Money Out stage.

---

## 11. Repair order

**Where:** approved quotation → Make the repair order; or Repair orders.

- Carries the **approved lines at the agreed prices**. Declined lines stay behind. One repair order per visit; numbers `RO-A1F3-000001`.

### Progress
```
Received → Diagnosis → Awaiting approval → In repair → Testing → Ready → (Delivered at the gate pass)
                                 On hold (from any stage)
```
- **Moving back a stage or putting the job on hold needs a note.** Resume returns the job to the stage it was paused at.
- **Ready** needs every line marked **Done** or **Not done**.

### Lines
- Each line: Done / Not done / To do, and the **technician** who did it.
- **Parts are issued from stock here**, at average cost. **Return unused** puts them back at the cost they left at, so the stock value doesn't drift.
- A part can't be marked Done before it is issued, or Not done while issued parts are still out.
- **Extra work** found during the repair (labour code or part, price, and a reason) is flagged **"Not in the quotation"**. Only those added lines can be removed.

### Activity
One timeline of everything that happened, newest first, with who and when:
- automatic: status changes (with the note), parts issued and returned, lines marked or added;
- written: **Note**, **Finding** (what was found), **Customer update** (marked "Customer can see"), each optionally about one line and with photos.

---

## 12. Invoice

**Where:** repair order (when Ready) → Make the invoice; or Invoices.

- Lines come from the repair order: **labour marked Done**, and **parts at the quantity issued** (not the quantity quoted). Prices start at the agreed prices. Lines added after approval are labelled.
- **Draft:** prices, discount, tax switch and notes can be changed. If the repair order changes after the draft was made (a part returned, a line marked differently), issuing is refused until you press **Refresh from the repair order**; edited prices are kept.
- **Issue** (permission `invoice-issue`): locks the prices and **applies the advances held on the visit**. If the advances are more than the invoice, issuing is refused until the difference is refunded.
- After issuing: **Unpaid**, **Partly paid** or **Paid**; take payments up to the balance. An issued invoice is never edited; corrections will be made with a credit note.
- A draft can be **voided** with a reason (its number stays on record). One live workshop invoice per visit.
- Numbers: `INV-A1F3-000001`.

---

## 13. Counter sale

**Where:** Invoices → New counter sale.

For parts sold over the counter, with no car in the workshop (a walk-in buys a headlight).

1. **Customer:** Walk-in (name and mobile optional) or a customer on file, optionally for one of their cars (the sale then shows in that car's history).
2. **Parts:** scan or search. **Parts only**: labour goes through a visit. Each line shows stock; price starts at the sale price.
3. Discount and tax switch; the total updates as you type.
4. **Payment:** the amount starts at the total. **Split the payment** to take part in cash and part by transfer; the payments must add up to the total, each with proof or a reason.
5. **Take Rs … and finish** does it all in one step: takes the parts out of stock, issues the invoice and records the payments. If anything fails (not enough stock, payments don't add up), nothing is changed.

- **Save as draft** keeps it for later.
- Prints as an **A4 invoice** marked "Counter sale" (owner decision: A4 only, no thermal receipt).
- Numbers: `CS-A1F3-000001` (their own series).

---

## 14. Gate pass

**Where:** visit page → Gate pass.

The panel lists anything stopping the car from leaving:
- the repair order isn't Ready;
- there is no invoice, or it is still a draft;
- an advance is held with no invoice to use it (refund first).

It also warns (without blocking) about an inspection left as an unsigned draft.

**Balance outstanding:** the car can't leave while the invoice has a balance, unless someone with `release-on-credit` releases it **with a reason**. The release is recorded with their name on the invoice, the gate pass and the audit log.

**Release the car:** odometer at exit (can't be lower than at check-in; updates the car's odometer), who collected it, and a note. The visit closes, the repair order becomes **Delivered**, and the gate pass prints as a slip for the gate, with customer and security signature lines.

---

## 15. Visit record and printed documents

| Document | Where | Size |
|---|---|---|
| Inspection report | Inspection page → Print report | A4 |
| Quotation | Quotation page → Print | A4 |
| Invoice (workshop and counter sale) | Invoice page → Print | A4 |
| Gate pass | Visit page (after release) → Print gate pass | A5 |
| **Visit record** | Visit page → Print visit record | A4 |

**The visit record** is the whole visit on paper, entry to exit:
1. check-in with photos and the customer's signature;
2. inspections;
3. job card;
4. every quotation version with its approval or rejection;
5. repair order with technicians and the full activity timeline;
6. invoice;
7. every payment with its method, reference and proof status;
8. gate pass, including any release on credit;
9. the audit trail: who did what, and when;
10. the proofs themselves (approval and payment images).

It is an **internal** record and includes notes the customer doesn't see. Every page prints with **Print or save as PDF**.

---

## 16. Administration

- **Users:** username, full name, phone, email, role, branches, active or disabled. A disabled account can't sign in; its history stays. You can't change your own role.
- **Roles and permissions:** make roles from the permission list in [section 3](#3-signing-in-roles-and-permissions).
- **Audit log:** every change to every record (who, when, which fields, before and after), plus sign-ins and failed sign-ins. Filter by action.
- **Branch settings:** name, address, phone, branch code (the `A1F3` in every document number) and the **sales tax rate**.

---

## 17. Rules that protect the data

- **Validated twice.** Forms check what is typed before sending (phone, CNIC, VIN / chassis, amounts, quantities) and show the problem beside the field; the server checks everything again.
- **No silent overwrites.** Two people editing the same record: the second save is refused with "changed on another device, reload".
- **Gap-free numbers** per branch and document kind, even with many people working at once.
- **Nothing is deleted.** Mistakes are voided with a reason or corrected by a new document; both stay on record.
- **Audit everything.** Every change is logged with who, when and what changed.
- **Stock and money can't drift.** Stock is the sum of its movements; payments are never edited; invoices bill exactly what was issued.
- **Proof on every money record**, or a written reason.

---

## 18. Not built yet

| Item | Where it comes |
|---|---|
| Inspection repair rows sent straight to the job card | Next workshop round |
| Supplementary quotation for extra work found during the repair | Next workshop round |
| Credit notes (returns, corrections to issued invoices) | Phase 5 (money out) |
| Advance refunds with admin approval | Phase 5 |
| Below-cost price approval (`discount-approve`), selling below zero stock with an admin override | Phase 4 / 5 |
| WhatsApp: quotation, ready, receipt, reminders | Phase 8 |
| Purchasing: purchase orders, goods received, supplier bills | Phase 4 |
| Money In / Money Out pages, accounts, journal, daily cash close | Phase 5 |
| HR, attendance (ZKTeco), payroll | Phase 6 |
| Monthly and yearly closing, missing-proof sign-off | Phase 7 |
| Reports with drill-down | Phase 7 |
| Offline branch server and sync | Phase 9 |
| Dashboard figures | With reports |
| Returning goods to a vendor (purchase returns), correcting a wrong goods receipt | Phase 5 (with credit notes) |
| Purchase order sent to the vendor on WhatsApp | Phase 8 |
| Vendor payments on the Money Out page, with the other money out | Phase 5 |

---

## 19. For developers

### Stack
- **API:** FastAPI, SQLAlchemy 2 (sync), PostgreSQL, Alembic, Pydantic 2, managed with `uv` (Python 3.12). Code in `api/app`.
- **Web:** Next.js 16 (App Router), React 19, Tailwind CSS 4, **Zustand** for shared state (`web/lib/session.tsx`, `web/lib/records.ts`) and **Zod** for form validation (`web/lib/schemas.ts`). Code in `web/`. `/api/*` is proxied to the API.
- **Design:** `DESIGN.md` (GermanATO colours from the logo, 44px touch targets, phone / tablet / desktop layouts).

### Run it
```bash
cd api && uv run alembic upgrade head && uv run uvicorn app.main:app --reload
```
```bash
cd web && pnpm dev
```

### Test it
```bash
cd api && TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/germanato_test uv run pytest -q
```
```bash
cd web && pnpm exec tsc --noEmit && pnpm lint
```

### Migrations
| Revision | Adds |
|---|---|
| 0001 | Branches, users, roles, sessions, audit log, attachments, sync outbox, numbering |
| 0002 | Customers, cars, ownerships, labour codes, items, item codes, stock movements |
| 0003 | Visits and inspections |
| 0004 | Pre-purchase buyer on visits |
| 0005 | VIN and chassis number as one field |
| 0006 | Job cards, quotations, payments |
| 0007 | Repair orders and their activity |
| 0008 | Invoices, gate pass fields, payment links to invoices |
| 0009 | Vendors, purchase orders, goods receipts, vendor bills, vendor payments |
| 0010 | Accounts and expense categories |

### API by module
All under `/api`. Every route checks the permission named in [section 3](#3-signing-in-roles-and-permissions).

| Module | Routes |
|---|---|
| Auth | `POST auth/login`, `POST auth/logout`, `GET auth/me`, `POST auth/switch-branch` |
| Admin | `GET/POST users`, `PATCH users/{id}`, `GET/POST roles`, `PUT roles/{id}`, `GET permissions`, `GET/PUT branch`, `GET audit` |
| Files | `POST attachments`, `GET attachments/{id}`, `GET attachments/{id}/file` |
| Customers and cars | `GET/POST customers`, `GET/PUT customers/{id}`, `GET/POST cars`, `GET/PUT cars/{id}`, `POST cars/{id}/transfer`, `GET cars/{id}/history` |
| Catalogue | `GET/POST labour-codes`, `PUT labour-codes/{id}`, `GET/POST items`, `GET items/lookup`, `GET/PUT items/{id}`, `POST items/{id}/adjust`, `GET stock/levels` |
| Visits | `GET/POST visits`, `GET/PUT visits/{id}`, `POST visits/{id}/cancel` |
| Inspections | `GET inspection-template`, `POST visits/{id}/inspections`, `GET/PUT inspections/{id}`, `POST inspections/{id}/sign`, `POST inspections/{id}/revise` |
| Job card | `GET estimate-catalog`, `POST visits/{id}/job-card`, `GET/PUT job-cards/{id}` |
| Quotation | `POST job-cards/{id}/quotation`, `GET quotations`, `GET/PUT quotations/{id}`, `POST quotations/{id}/send`, `…/approve`, `…/reject`, `…/revise`, `…/advances` |
| Repair order | `POST quotations/{id}/repair-order`, `GET repair-orders`, `GET repair-orders/{id}`, `POST repair-orders/{id}/status`, `POST …/lines`, `PATCH/DELETE …/lines/{line}`, `POST …/lines/{line}/issue`, `…/return`, `POST …/activity`, `GET technicians` |
| Billing | `POST repair-orders/{id}/invoice`, `POST counter-sales`, `PUT counter-sales/{id}`, `GET invoices`, `GET/PUT invoices/{id}`, `POST invoices/{id}/refresh`, `…/issue`, `…/payments`, `…/void` |
| Gate and record | `GET visits/{id}/gate-check`, `POST visits/{id}/gate-pass`, `GET visits/{id}/dossier` |
| Purchasing | `GET/POST vendors`, `GET/PUT vendors/{id}`, `GET purchase-catalog`, `GET/POST purchase-orders`, `GET/PUT purchase-orders/{id}`, `POST purchase-orders/{id}/send`, `…/cancel`, `…/close`, `…/receive`, `POST goods-receipts/{id}/bill`, `GET bills`, `GET bills/{id}`, `POST bills/{id}/payments`, `POST bills/{id}/void`, `POST vendor-payments/{id}/void` |

### Quality checks run on every stage
- API tests (`api/tests`), TypeScript, ESLint, and the Hallmark design checker.
- Each new or changed screen is opened in the browser at **375px (phone), 768px (tablet) and desktop**, and scanned for sideways scrolling, elements past the screen edge, clipped text, content wider than its card and touch targets under 44px.

---

## 20. Purchasing

```
Vendor ─► Purchase order ─► (send) ─► Goods received ─► Bill ─► Payment
            draft → sent        count on arrival     what we owe   money out, with proof
                              stock in + average cost
```

Prices and stock change **only** through a goods receipt, so the cost of a part is always traceable to a delivery.

### Vendors
**Where:** Purchasing → Vendors.
- Name, contact person, phone, email, address, notes, and **days to pay a bill** (sets the due date on each bill; 0 means due at once).
- A vendor name can't be used twice (capitals ignored). Phones are stored as `+92…`.
- An inactive vendor can't be put on new orders; its history stays.
- The vendor page shows **what we owe** and the **account**: every bill and payment, newest first, with the amount owed after each. The account is **worked out from bills and payments every time it is shown; nobody types a balance**, so it cannot drift. Voided entries stay visible, struck through, and don't count.

### Purchase order
**Where:** Purchasing → Purchase orders → New purchase order (or a vendor's page → New purchase order).
- Choose the vendor, then add **items already in Inventory**: search by name or number, or **scan a barcode or part number**. An item can only be listed once.
- Each line has a quantity and the agreed **cost each**. The line shows the stock on hand and the item's average cost, for comparison.
- **Add everything below its reorder level** fills the list from the items under their reorder level, using each item's reorder quantity (needs the `inventory` permission).
- **Create this item** (when a search finds nothing and you have `inventory`) opens the item form with the scanned code filled in, then adds the new item to the order.
- Optional expected date and notes for the vendor.
- **Send** locks the order. A sent order cannot be edited; to change one, cancel it and make a new one. Print it to hand or send (WhatsApp comes with the messaging stage).

| Status | Meaning |
|---|---|
| Draft | Being written |
| Sent | Locked, waiting for goods |
| Part received | Some goods have arrived |
| Received | Everything arrived |
| Closed early | Part received, and the vendor won't send the rest (reason kept) |
| Cancelled | Nothing arrived; cancelled with a reason |

Numbers: `PO-A1F3-000001`.

### Goods received (counting stock in)
**Where:** a sent purchase order → Count the goods in (needs `goods-receipt`).
- Each line starts at **what is still expected** and the agreed cost. Change the **Arrived** quantity to what you actually counted, and the **cost each** if the vendor charged something different.
- You can receive **part of an order**; the rest stays expected. Receiving **more than is still expected is refused**.
- Optional **new sale price** per item. Before you confirm, the screen shows what the **average cost** and the **margin** become.
- The vendor's delivery note number and the receipt date can be recorded.
- **Putting the stock in** does three things in one step: adds the quantity to stock, moves the item's **weighted average cost** (for example 10 in stock at 100 plus 10 arriving at 200 gives 20 at 150), and applies the new sale price if you gave one. It can't be undone from this screen.
- Warnings after a receipt: the average cost is above the sale price, the margin is under 10%, or no sale price is set.
- Numbers: `GRN-A1F3-000001`.

### Bill
**Where:** under each delivery on the purchase order → Record the vendor's bill (needs `purchasing`).
- One bill per delivery. The **goods value comes from the receipt**; the bill date, the **vendor's invoice number**, an optional due date, and an optional **adjustment** (freight as a plus, a discount as a minus, with a reason) are entered.
- The **same vendor invoice number can't be recorded twice** for a vendor.
- A blank due date uses the vendor's days to pay.
- A bill can be **voided** with a reason only while nothing is paid on it; the delivery can then be billed again.
- Numbers: `BILL-A1F3-000001`.

### Paying a vendor
**Where:** Purchasing → Bills and payments → a bill → Pay this bill (needs `payments-out`).
- Any part of the balance can be paid; **more than is owed is refused**.
- Every payment has the amount, where it came from (**Cash**, **Bank transfer**, **Mobile wallet**), a reference, and **proof** (photo, screenshot or PDF) or a written reason why there is none. A bank or wallet payment also needs its **transaction reference** or a screenshot.
- A wrong payment is **voided** with a reason: it stays on record, struck through, and the bill owes that money again.
- Numbers: `VPAY-A1F3-000001`.
- The **Bills and payments** list shows what is owing, oldest due date first, with an **Overdue** mark, and the total shown.

### Rules
- Stock only goes up through a goods receipt, and only against a sent order.
- A purchase order, receipt and bill each keep their number; nothing is deleted.
- Money paid to vendors is recorded the same way as money received: with proof or a reason.
- Vendor payments will also appear on the Money Out page when it is built.

---

## 21. Money

### Accounts and expense categories
**Where:** Administration → Money settings (needs `settings`).
- Every branch has three **accounts**: **Cash in hand**, **Bank account** and **Mobile wallet**. They are created the first time they are needed.
- Each account has an **opening balance** and the date it applies from: what was in the account when you started using the system. Every later change to the account comes from money in and money out; nobody types a balance.
- **Expense categories** are a managed list (tea, fuel, rent, electricity, repairs, equipment, stationery, internet, marketing, bank charges, taxes, other). Add one, rename one, or **retire** one: a retired category can't be chosen for new expenses but stays on the expenses already recorded. A name can't be used twice (capitals ignored).
- The accountant can see accounts and categories; only people with `settings` change them.
