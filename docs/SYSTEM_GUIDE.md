# GermanATO: system guide

This guide describes the software **as it is built today**, module by module: what each part is for, how to use it, the rules the system enforces, and where it lives. It is updated in the same commit as every change, so it always matches the code. The plan for what comes next is in [NEW_SYSTEM_SPEC.md](NEW_SYSTEM_SPEC.md).

Last updated: 29 Oct 2026 (repair order stages simplified). Every phase (0 to 9) is built; see section 18 for what is deliberately left for later.

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

Purchasing is [section 20](#20-purchasing). Money (accounts, money in and out, journal, cash close) is [section 21](#21-money). People (employees, attendance, salary advances, payroll) is [section 22](#22-people-and-payroll). Dashboard, reports and month end is [section 23](#23-dashboard-reports-and-month-end). Customer messages (WhatsApp) is [section 24](#24-customer-messages). Running the server and syncing is [section 25](#25-server-backups-and-sync). The in-app user manual is [section 26](#26-the-help-page-user-manual). Interface behaviour (search, shortcuts, loading, duplicate protection) is [section 27](#27-interface-behaviour). Who does what (roles and hand-offs) is [section 28](#28-roles-and-hand-offs).

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
| Money in and out, accounts, cash close, missing proof, credit notes, refunds, journal | Built | Money menu, section 21 |
| Employees, attendance devices, salary advances, payroll | Built | People menu, section 22 |
| Dashboard, finance, workshop and people reports, month and year end, closing pack | Built | Dashboard, Reports menu, section 23 |
| WhatsApp messages, reminders, Twilio status and STOP | Built | Customers menu, section 24 |
| Docker server, backups, cloud sync, conflict review | Built | Cloud sync, runbook, section 25 |

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
| `sync` | See sync status, run a sync, and settle sync conflicts (admin) |
| `messages` | See and retry customer messages, edit their wording and the reminder days |
| `period-close` | Close a finished month, with its checklist |
| `period-approve` | Reopen a closed month (admin) |
| `reports-ops` | See operations reports |
| `gate` | See the cars ready to leave and release them with a gate pass (guard) |
| `hr` | Manage employees, attendance and attendance devices |
| `payroll` | Run payroll and give salary advances |
| `evidence-signoff` | Accept a money record that has no proof, with a reason (admin) |
| `cash-close` | Count and sign off the cash, bank and wallet at the end of the day |
| `credit-notes` | Issue credit notes for returns and corrections, and refund the customer |
| `advance-refund` | Give a held advance back to the customer (admin approval) |
| `reports-finance` | See the journal, trial balance and finance reports |

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
- **Send repairs to the job card:** once a report is signed, a panel under it lists the recommended repairs. **Send to job card** turns a repair into a labour code or a part on the visit's job card (creating the job card if needed), and the inspector's **estimate becomes the proposed price** on the quotation. Each repair can be sent once; a repair that is already there shows **On the job card**. Not possible once the visit has a quotation (revise the quotation instead).
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
- A visit holding money can't be cancelled. A held advance can be given back with admin approval (see Credit notes and refunds in section 21).

---

## 11. Repair order

**Where:** approved quotation → Make the repair order; or Repair orders.

- Carries the **approved lines at the agreed prices**. Declined lines stay behind. One repair order per visit; numbers `RO-A1F3-000001`.

### Progress
```
Received → In repair → Testing → Ready → (Delivered at the gate pass)
                    On hold (from any stage)
```
- **Moving back a stage or putting the job on hold needs a note.** Resume returns the job to the stage it was paused at.
- **Moving to Testing or Ready** needs every line marked **Done** or **Not done** first (no line left as To do).

### Lines (what you can do depends on the stage)
| Stage | Work and parts | Issue / return stock | Mark Done / Not done |
|---|---|---|---|
| Received | Shown; mostly read | Issue allowed (early); return allowed | Locked |
| In repair | Full edit | Main issue window; return unused | Labour and parts |
| Testing | Shown | Top-up issue and return unused | Finish remaining lines |
| Ready | Read-only lines | Return unused only (before the invoice) | Locked |
| Delivered | Closed | Locked | Locked |

- Each line: Done / Not done / To do, and the **technician** who did it.
- **Parts are issued from stock here**, at average cost, up to the quantity on the line. **Return unused** puts them back at the cost they left at, so the stock value doesn't drift.
- A part can't be marked Done before it is issued, or Not done while issued parts are still out.
- **Extra work** (In repair / Testing): labour code or part, price, and a reason, flagged **"Not in the quotation"**. It also records **how the customer agreed** (in person, WhatsApp or phone) with **proof or a written reason**; this shows on the repair order and carries to the invoice. Only those added lines can be removed.

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
- After issuing: **Unpaid**, **Partly paid** or **Paid**; take payments up to the balance. An issued invoice is never edited; returns and corrections are made with a credit note (section 21).
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
| Gate pass | Visit page (after release) → Print gate pass | A4 |
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

It is an **internal** record and includes notes the customer doesn't see.

**On every printed document (the bar at the top):**
- **Back** returns to the screen the document came from (the invoice, the visit, the quotation, ...), so you are never stranded on a printout.
- **Print or save as PDF** uses the browser's print.
- **Share as PDF** makes a real A4 PDF of the document and opens the phone's or computer's **share sheet**, so it can be sent on **WhatsApp**, email, Drive or any other app, as a file (not a link that needs a login). A browser that can't share files saves the PDF to the downloads instead.
- **Send on WhatsApp** (on documents meant for a customer or vendor: invoices, quotations, inspection reports, purchase orders) opens a WhatsApp chat with that person's number and a ready message, and saves the PDF so you can attach it. Without a number (a walk-in) WhatsApp asks whom to send it to.
- The PDF is laid out at A4 width whatever the screen, and never includes the bar itself.

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
| A separate supplementary quotation document for extra work (today the customer's go-ahead is recorded on the repair order line instead) | Later, if wanted |
| Below-cost price approval (`discount-approve`), selling below zero stock with an admin override | Later, if wanted |
| The cloud server and its owner panel, inter-branch stock transfers, syncing proof files | When the second branch opens |
| Returning goods to a vendor (purchase returns), correcting a wrong goods receipt | Later |

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

### Demo / test data
After `app.seed` has created a branch and admin, load sample customers, stock, a finished job, an open repair, purchasing, counter sales, money entries and HR rows:

```bash
cd api && set ADMIN_PASSWORD=your-password && uv run python -m app.demo_data
```

Safe to run again: it exits without duplicating if the marker customer (`Demo Ali Khan`, phone `0399 0000001`) is already there. Data goes through the same API routes the UI uses, so journals and stock stay consistent.

### Test it
```bash
cd api && TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/germanato_test uv run pytest -q
```
```bash
cd web && pnpm exec tsc --noEmit && pnpm lint
```

### How the code is organised
**API (`api/app`)**
| File | Owns |
|---|---|
| `main.py` | App, router list, error handlers (database rule broken becomes a readable 409/422; `JournalError` becomes 409) |
| `models.py`, `db.py` | All tables. `Entity` (id UUIDv7, created/updated by and at, `version`) and `BranchScoped` (adds `branch_id`, stamped automatically) |
| `events.py` | One flush hook writes the audit log and the sync outbox for every ORM change |
| `auth.py`, `permissions.py` | Sessions, `require("permission")`, the permission list and default roles |
| `stock.py` | `move()`: the only way stock changes (locks the item, weighted average cost, posts the inventory journal entry) |
| `journal.py`, `posting.py`, `pricing.py`, `money_setup.py` | Double-entry journal; one posting function per business event; shared totals and rounding; accounts created on first use |
| `attendance.py`, `reports.py` | Attendance summary rules; every report figure (routers are thin wrappers) |
| `messaging.py` | Templates, queue, Twilio provider, webhook signature check, reminders |
| `sync.py`, `sync_worker.py` | Applying incoming changes with conflict detection; the push/pull worker |
| `seed.py`, `demo_data.py` | First-run branch/admin; optional sample data for local browsing (`python -m app.demo_data`) |
| `routers/*.py` | One file per area; each route checks a permission and commits once |

**Web (`web`)**: `app/(app)/...` are the screens, `app/print/...` the printable documents, `components/` the shared pieces per area (`ui.tsx` primitives, `print.tsx` PrintBar), `lib/` holds `api.ts` (fetch and `useApi`), `schemas.ts` (zod, `parseForm`), `session.tsx` and `records.ts` (zustand), `format.ts`, `csv.ts`.

### Rules the code depends on
- **Stock** changes only through `stock.move()`. Never `db.refresh()` an item after it (that discards the unflushed average cost).
- **Money** is posted to the journal in the same transaction as the event, right before `db.commit()`, using a `posting.*` function. Journal tables are append-only (database trigger); mistakes are reversed, not edited. `post()` refuses unbalanced entries and entries dated in a closed month.
- **Money records** carry proof or a written reason (CHECK constraint). A new route that records or voids money on a past date calls `cashclose.assert_day_open`.
- **Concurrency:** every table has `version`; editing routes take the client's version and return 409 if it is stale.
- **Migrations:** Alembic autogenerate does not see changed CHECK constraints; edit those by hand and name foreign keys so downgrades work. Run `alembic check` after each.
- **Sync:** pulled changes are applied with Core statements so they skip the outbox hook and never echo back. Tests build tables with `create_all`, so database triggers are not exercised by them.
- **Messages and sync never block a sale:** failures are recorded and retried.
- **Web:** a Next.js page file cannot export extra names (shared constants go in `components/`). Forms validate with a zod schema through `parseForm`. Every control is at least 44px, clickable things must look clickable (DESIGN.md section 6b), and every new screen is scanned at 320, 375, 768 and 1280px. After editing `globals.css` the dev server may serve stale CSS: stop it, delete `web/.next/dev`, restart.
- **Print pages** pass `back`, `name` and (for customer documents) `whatsapp` to `PrintBar`.
- **New numbered document:** add its prefix in `numbering.py` and call `next_number`. **New permission:** add it in `permissions.py`, in `DEFAULT_ROLES` where it fits, and in the guide's permission table.
- **Every change updates this guide in the same commit.**

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
| 0011 | Journal: chart of accounts, entries and lines (append-only, enforced by the database) |
| 0012 | Money entries (other income, owner capital, expenses, drawings, transfers) |
| 0013 | Credit notes and refunds |
| 0014 | Daily cash closes |
| 0015 | Evidence sign-offs |
| 0016 | Inspection repairs sent to the job card, extra-work approval on repair order lines |
| 0017 | Employees, attendance devices, punches, leave marks |
| 0018 | Payroll runs and lines; salary and salary-advance money entries |
| 0019 | Closed periods (month and year locks) |
| 0020 | Customer messages, message wording, reminder days on the branch |
| 0021 | Sync bookkeeping: credentials, state, inbox, conflicts |
| 0022 | Idempotency keys (retry protection for writes) |
| 0023 | Quotation terms and conditions on the branch |
| 0024 | Repair order stages simplified: received → in_repair → testing → ready → delivered |

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
| Money | `GET/PUT accounts`, `GET/POST expense-categories`, `PUT expense-categories/{id}`, `GET money-in`, `GET money-out`, `POST money-entries`, `POST money-entries/{id}/void`, `GET journal/trial-balance`, `GET journal/entries` |
| Missing proof | `GET missing-evidence`, `POST missing-evidence/sign`, `POST missing-evidence/attach` |
| Sync | `GET sync/status`, `POST sync/run`, `GET sync/conflicts`, `POST sync/conflicts/{id}/resolve`, `POST sync/tokens`; branch servers call `POST sync/push` and `GET sync/pull` with a token |
| Messages | `GET messages`, `POST messages/send`, `POST messages/{id}/retry`, `POST messages/run-reminders`, `GET/PUT message-templates`, `PUT message-settings`; Twilio calls `POST webhooks/twilio/status` and `/inbound` |
| Reports and month end | `GET dashboard`, `GET reports/pnl`, `…/cashflow`, `…/receivables`, `…/payables`, `…/stock-value`, `…/discounts`, `…/operations`, `…/hr`, `GET periods`, `GET periods/{p}/checklist`, `POST periods/{p}/close`, `…/reopen`, `GET periods/{p}/pack` |
| People | `GET/POST employees`, `GET/PUT employees/{id}`, `GET employee-logins`, `GET/POST attendance-devices`, `PUT attendance-devices/{id}`, `POST attendance-devices/{id}/secret`, `GET attendance`, `GET attendance/{employee}`, `GET attendance/unmatched`, `POST attendance/punches`, `POST attendance/punches/{id}/void`, `POST/DELETE attendance/marks`, `GET/POST salary-advances`, `GET/POST payroll-runs`, `GET payroll-runs/{id}`, `PUT payroll-runs/{id}/lines/{line}`, `POST payroll-runs/{id}/refresh`, `…/approve`, `…/void`, `POST payroll-runs/{id}/lines/{line}/pay`, `GET payroll-runs/{id}/lines/{line}` |
| Device push (no login) | `GET/POST /iclock/cdata`, `GET /iclock/getrequest` |
| Cash close | `GET cash-closes/status`, `GET cash-closes`, `POST cash-closes` |
| Credit notes | `POST invoices/{id}/credit-notes`, `POST invoices/{id}/refund`, `POST advances/{id}/refund` |
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
- **Send** locks the order. A sent order cannot be edited; to change one, cancel it and make a new one. Print it to hand over, or use **Send on WhatsApp** on its print page (section 15).

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
- Vendor payments appear on the Money out page (section 21).

---

## 21. Money

### Accounts and expense categories
**Where:** Administration → Money settings (needs `settings`).
- Every branch has three **accounts**: **Cash in hand**, **Bank account** and **Mobile wallet**. They are created the first time they are needed.
- Each account has an **opening balance** and the date it applies from: what was in the account when you started using the system. Every later change to the account comes from money in and money out; nobody types a balance.
- **Expense categories** are a managed list (tea, fuel, rent, electricity, repairs, equipment, stationery, internet, marketing, bank charges, taxes, other). Add one, rename one, or **retire** one: a retired category can't be chosen for new expenses but stays on the expenses already recorded. A name can't be used twice (capitals ignored).
- The accountant can see accounts and categories; only people with `settings` change them.

### The journal (double-entry books)
Every business event posts a **balanced journal entry** automatically, so the books are provable without anyone doing bookkeeping. Users never type journal entries; they record documents and payments, and the system posts the matching entry.
- **Always balanced.** An entry whose debits and credits differ is refused, as is one with a single line.
- **Append-only.** Entries are never edited or deleted (the database itself refuses). A mistake is fixed by a **reversing entry** that mirrors the original; an entry can be reversed once.
- **Chart of accounts** (created automatically): cash, bank, mobile wallet, receivables, inventory, payables, goods received not billed, customer advances, sales tax payable, owner capital and drawings, opening balance equity, revenue (labour, parts, other), cost of parts sold, operating expenses (by expense category), salaries, freight and purchase adjustments, stock write-offs.
- **Opening balances.** Setting an account's opening balance posts an entry (money account against opening balance equity). Changing it later posts a reversal and a new entry, so the history of the correction is kept.
- **What is in an account** is worked out from the journal: Money settings shows each account's balance now.
- **Trial balance** (`GET /api/journal/trial-balance`, needs `reports-finance`) lists every account with debits and credits; the two totals are always equal. `GET /api/journal/entries` lists the entries behind it, filterable by the document that caused them.

### What each event posts
| Event | Debit | Credit |
|---|---|---|
| Opening stock, stock found | Inventory | Opening balance equity (opening) or Stock write-offs and corrections (a count adjustment) |
| Stock lost or written off | Stock write-offs and corrections | Inventory |
| Goods received | Inventory | Goods received not billed |
| Vendor bill | Goods received not billed (and freight as Purchase adjustments) | Payables to vendors |
| Vendor payment | Payables to vendors | Cash, bank or wallet |
| Advance taken | Cash, bank or wallet | Customer advances |
| Invoice issued | Receivables | Revenue: labour, Revenue: parts, Sales tax payable |
| Advance applied to the invoice | Customer advances | Receivables |
| Customer payment | Cash, bank or wallet | Receivables |
| Part issued on a repair order, or sold at the counter | Cost of parts sold | Inventory |
| Part returned from a repair order | Inventory | Cost of parts sold |

- The **discount** on an invoice is shared between labour and parts revenue in proportion to each.
- Voiding a vendor payment or a bill posts a **reversal** of its entry.
- Stock entries are posted from the single place stock changes, so the inventory balance in the books always equals the stock ledger (quantity times the cost each unit moved at).
- **Reconciliation checks** run in the tests: after a full workshop job and a purchase, the trial balance is zero; receivables, payables, advances held and inventory match the figures derived from the documents.
- For a database that predates posting, `uv run python -m app.backfill_journal` posts what is missing; it is safe to run again.

### Money in
**Where:** Money → Money in (needs one of `payments-in`, `payments-out`, `expenses` or `reports-finance` to see it).
One page for **every payment received**, whatever its source:

| Source | Comes from |
|---|---|
| Invoice payment | a payment on a workshop invoice or counter sale |
| Advance | an advance taken on a quotation |
| Other income | scrap sale, rent received, commission (recorded here) |
| Owner capital | money the owner puts into the business (recorded here) |
| Transfer | money moved between the cash drawer, bank and wallet (recorded here; counted in each account but **not as income**) |

- **Record money in** (needs `payments-in`): other income, owner capital, or a transfer. Each has an amount, the account it went into, who it came from, the date, a transaction reference for bank or wallet money, and **proof or a written reason**.
- **Find:** search by name, number or reference; filter by source, account, and date range; and **Only those with no proof**.
- The page shows the **total** (transfers excluded), the total **by account** and **by source**, and a warning with the number of records that have a reason but no proof.
- Each row links to its document (invoice, quotation). A record entered here can be **voided** with a reason: it stays on the list, struck through, and the books are corrected.

### Money out
**Where:** Money → Money out. The same page for **every payment made**:

| Source | Comes from |
|---|---|
| Vendor payment | paying a vendor's bill |
| Expense | a daily or major expense, with its **category** from the managed list (needs `expenses`) |
| Owner drawings | money the owner takes out (needs `payments-out`) |
| Transfer | money moved between accounts (needs `payments-out`) |

- A vendor payment appears here once, from the bill it paid; it is not entered twice.
- An expense needs a category, an amount, the account it was paid from, the date and proof or a reason. A bank or wallet payment needs its reference or a screenshot.
- Same filters, totals and voiding as Money in.
- **Who can record what:** money in needs `payments-in`; expenses need `expenses`; owner drawings and transfers need `payments-out`. The accountant role can record expenses and pay vendors but not receive money.

### Credit notes and refunds
**Where:** an issued invoice → **Return or correct** (needs `credit-notes`).
- An issued invoice is never edited. A **credit note** reverses the part you choose: pick the lines and how many of each came back, and give a reason. Works for workshop invoices and counter sales.
- You can credit **part of a line**; a line can't be credited for more than was invoiced (counting earlier credit notes). Labour can be credited but never goes "back in stock".
- **Put it back in stock** returns a part to the shelf **at the cost it left at**, so the stock value stays right.
- The invoice's discount and tax are shared in proportion, so the credit is exactly the share the customer paid for.
- The invoice then shows **Credited (returns)** and the new balance. If the customer had already paid, the balance goes negative and the page shows **Owed back to the customer**.
- **Give money back** records the refund: it appears on **Money out** as a *Refund to customer*, with proof or a reason, and clears what is owed. It can't be more than what is owed back.
- Credit notes are numbered `CN-A1F3-000001`; refunds `RFD-A1F3-000001`.

**Giving back a held advance** (needs `advance-refund`, an admin permission): on a quotation, **Give back** next to an advance that hasn't been used on an invoice. The whole advance goes back, with the admin's reason and proof. It shows on Money out as a refund, the advance is marked *Refunded to the customer*, and the visit no longer counts as holding money (so it can be cancelled). Voiding the refund restores the advance.

**Books:** a credit note reverses revenue (labour and parts), sales tax and the receivable, and a returned part goes back to Inventory against Cost of parts sold. A refund of an overpayment clears the receivable; a refund of an advance clears Customer advances.

### Daily cash close
**Where:** Money → Cash close (needs `cash-close`; the accountant has it).
At the end of the day, count what is really in the **cash drawer**, the **bank** and the **mobile wallet**, and sign each one off.
- Each account shows what **the books say there should be** and when it was last counted.
- **Count and close**: type what is really there. If it differs from the books, the screen shows how much it is **over or short** and you must say **why** before you can sign.
- **Signing is final.** The close can't be edited, and the day is **locked** for that account: nothing can be recorded or voided on or before that date (record it today instead). Days close in order, once per account per day.
- A difference is **posted to the books** as *Cash over and short* (a shortage is an expense, a surplus is income), so tomorrow starts from what you counted and the books match the drawer.
- **Past closes** lists every signed count: the day, who signed, what the books said, what was counted, the difference and the reason.

### Missing proof
**Where:** Money → Missing proof.
- **Proof is always asked for.** When there truly is none, the person gives a written reason instead, and the record is flagged **no proof**.
- This page lists **every** such record, money in and money out (customer payments and advances, vendor payments, expenses, owner money, transfers, refunds), each with the reason that was given. A transfer is listed once.
- It shows how many are **waiting for an admin** and their total value.
- An admin (needs `evidence-signoff`) can **Accept** a record with a reason. Their name and the reason are kept. The record still shows as having no proof, but it no longer counts as waiting: the alert on the Money in and Money out pages goes down, and month-end closing will not be blocked by it.
- **Add proof** is optional: if the photo or document turns up later, anyone who can open this page can attach it (`POST missing-evidence/attach`). The record then leaves the list. You do not have to add proof — Accept still works without it.
- **Waiting and accepted** shows both, so nothing that was accepted is hidden.

---

## 22. People and payroll

### Employees
**Where:** People → Employees (needs `hr`).
- Name, job title, phone, CNIC, **monthly salary**, the **shift** (start and end time), the **weekly day off** (Sunday unless changed), the day they joined and (if they left) the day they left, notes.
- **Device number:** the person's number on the fingerprint or face terminal. Giving an employee a device number **claims any punches** already received for that number.
- **Login:** an employee can be linked to a user account; a login can belong to one employee only.
- A CNIC or a device number can't belong to two employees. Numbers: `EMP-A1F3-000001`. An employee who leaves is marked inactive with a leaving date; their history stays.

### Attendance devices
**Where:** People → Attendance → Devices (needs `hr`).
- Register each terminal by its **serial number**. A terminal that is **not registered, or is switched off, is refused** when it tries to send punches.
- Optionally give a device a **shared secret**. It is shown **once** when created or replaced; the device must send it (as `?token=` on its server address, or an `X-Device-Secret` header). Replacing the secret stops the old one working at once.
- **Setting up a ZKTeco terminal:** in its cloud/ADMS server settings, set the server address to the branch server (for example `http://<the PC's address>:8000`) and the port to match. The terminal pushes to `/iclock/cdata`. Times are read as the workshop's local time (`TIMEZONE`, Asia/Karachi by default).
- A terminal that sends the same punch again is ignored. Punches for a device number nobody owns yet are kept and listed under **Unmatched**, so nothing is lost.

### Attendance
**Where:** People → Attendance.
Each day is worked out from the punches: the **first punch is in, the last is out**.
| Status | Meaning |
|---|---|
| Present | First punch within 15 minutes of the shift start |
| Late | First punch more than 15 minutes after the shift start |
| Incomplete | Only one punch that day (forgot to punch out); counts as attended, with no hours |
| Absent | A working day with no punch and no leave |
| Off | The employee's weekly day off |
| Paid leave / Unpaid leave | A day marked as approved leave, with a reason |
- The month view shows present, late, absent, leave and off days and hours for everyone; open a person for the day-by-day list and their punches.
- **Manual punch** (with a reason of at least five characters) covers a forgotten or failed scan. A manual punch can be voided with a reason; **a punch from the device can never be removed**, only corrected with a manual punch or a leave mark.
- Days before a person joined, after they left, or in the future are not counted.

### Salary advances
**Where:** People → Payroll → Advances (needs `payroll`).
- Money lent against salary is **paid out now** (cash, bank or wallet, with proof or a reason) and shows on **Money out** as a *Salary advance*. In the books it is an asset (Employee advances).
- **No more than one month's salary** can be outstanding for a person.
- It is taken back through payroll. Each person's **advanced, recovered and outstanding** amounts are worked out from the records.

### Payroll
**Where:** People → Payroll (needs `payroll`).
1. **Start a run** for a month that has ended. Everyone employed that month gets a line worked out from attendance.
2. **Pay for the month:** the monthly salary for the working days they were employed (a part month is prorated). **A day's pay is the salary divided by the month's working days**, and one day's pay is deducted for each **absent day and each unpaid-leave day**. Late days are shown on the payslip but cost nothing.
3. **Adjust** a line before approving: a bonus (+) or another deduction (-) with a reason, and the **advance recovery** (by default the outstanding advance, as far as the pay covers it).
4. **Refresh** re-reads attendance after a correction and keeps the adjustments. A draft can also be **thrown away** and started again.
5. **Approve** fixes the figures and books the month's salary expense. The advances recovered stop being outstanding.
6. **Pay** each person their net pay (cash, bank or wallet, with proof or a reason). It shows on **Money out** as *Salary*. When everyone is paid the run is marked **Paid**. Voiding a salary payment reopens the run.
7. **Payslip:** every line prints as a payslip.
- One payroll run per month. Numbers: `PR-A1F3-000001`, `SAL-…` for salary payments, `ADV-…` for advances.
- **Books:** approving posts salary expense against salaries payable (and employee advances for what was recovered); paying clears salaries payable against the account the money came from.

---

## 23. Dashboard, reports and month end

### Dashboard
**Where:** Dashboard (the first page).
- **Needs attention:** payments with no proof waiting for an admin, invoices unpaid for over 30 days, vendor bills past due, items at or below their reorder level, and months not yet closed. Each line opens the screen that fixes it. "Nothing needs attention" when all is well.
- **In the workshop:** cars in the workshop, open quotations (and how many wait for the customer), repair orders under way (ready, on hold), items low on stock.
- **Money this month** and **Where the money is** (for people who may see finance): revenue, profit, money in and out, cash by account, what customers owe, what vendors are owed, stock at cost. Every tile opens the report behind it.
- People without finance permission see only the workshop and stock tiles.

### Finance reports
**Where:** Reports → Finance reports (needs `reports-finance`). Choose **This month**, **Last month**, **This year** or a custom range; the range is in the address, so a report can be shared as a link. Each report has **Download for Excel**.
| Report | What it shows |
|---|---|
| Profit and loss | Revenue (labour, parts, other), cost of parts sold, gross profit and margin, expenses by category, salaries, purchase adjustments, cash differences, net profit. Sales tax is shown separately: it belongs to the government, not to the business. Lines link to the records behind them. |
| Cash flow | For the cash drawer, the bank and the wallet: at the start, what came in (by source), what went out (by source), at the end. The totals agree with each account's balance. |
| Customers owe us | Every unpaid invoice, aged from the day it was issued (0-30, 31-60, 61-90, over 90 days). A customer who has overpaid shows as owed back. Totals equal the Receivables account. |
| We owe vendors | Every unpaid bill, aged by how late it is (not yet due, then 1-30, 31-60, 61-90, over 90 days). Totals equal the Payables account. |
| Stock value | Each item's quantity, average cost and value; the total equals the Inventory account. |
| Discounts and voids | Discounts given, by invoice and by the person who issued it; and every voided record with its reason. |

### Workshop report
**Where:** Reports → Workshop report (needs `reports-ops`).
- Cars checked in (by status) and the **average time in the workshop**.
- Workshop revenue, **revenue per invoiced visit**, and counter-sale revenue (the two channels kept apart).
- **Quotations:** made, sent, approved and the **conversion rate**.
- **Average time in each stage** of a repair order (time on hold is not counted).
- **Top labour codes** and **top parts** by revenue.
- **Comebacks:** cars that returned within 30 days of leaving, linked to the visits.
- Repair orders still open, by age.

### People report
**Where:** Reports → People report (needs `hr`). Attendance for a month, payroll cost by month, advances owed, and what each technician billed (labour lines marked done and assigned to them).

### Month end
**Where:** Reports → Month end (needs `period-close`; the accountant has it).
- Open a finished month to see its **checklist**: the month has ended; earlier months with activity are closed; every payment has proof or has been accepted by an admin; the books balance; the cash, bank and wallet were **counted and signed on the last day** (an account with no activity needs no count); payroll is not left as a draft. Two further items are shown but don't stop the close: payroll was run, and no draft invoices are left over.
- **Each item that isn't done has a Fix it link** to the screen that fixes it. **Close this month** is available only when every required item is done.
- **Closing locks the month.** Nothing can be recorded dated inside it: the system refuses, with the month's name in the message. Corrections are made in the current month.
- **Reopen** (needs `period-approve`, an admin permission) needs a reason, which is kept. Months reopen latest first, and a month inside a closed year can't be reopened until the year is.
- **Closing pack:** a printable document with profit and loss, cash and bank by account with the signed counts, what customers owe and what vendors are owed, stock at cost, and **every payment with its proof status**, and the payroll summary. It prints and shares like any other document.
- **Years:** once a year has ended and every month in it with activity is closed, the year can be closed, which locks the whole year. The yearly pack adds a month-by-month profit table.

---

## 24. Customer messages

The system tells customers what is happening on WhatsApp, so the counter doesn't have to.

### What is sent, and when
| Message | Sent when |
|---|---|
| Quotation | A quotation is sent to the customer |
| Car ready | A repair order moves to Ready |
| Invoice | An invoice is issued (total and balance) |
| Payment received | A payment is taken on an invoice (with the new balance) |
| Payment reminder | An invoice is still unpaid **3, 7 and 15 days** after it was issued (the days can be changed). Only the latest step is sent, never three at once. |
| Service reminder | **180 days** (changeable) after the customer's last visit, if the car is not in the workshop |
| Welcome | After the customer's first finished visit |

Nothing is sent to a **walk-in**, to a customer with no phone number, or to a customer marked **Don't send WhatsApp messages** (or who replied STOP). Those appear as **Not sent** with the reason, so there is a record.

### Messages screen
**Where:** Customers → Messages (needs `messages`). Every message with its customer, number, wording and status: **Waiting to send**, **Sent**, **Delivered**, **Read**, **Failed** (with the reason, and **Try again**) or **Not sent**. **Queue due reminders** adds the reminders that are due; each reminder is queued once, so pressing it twice does nothing new. A daily job can call the same action.

### Wording and reminder days
**Where:** Administration → Message wording. Each message has its text and a **Send this message** switch. Fill-in fields (`{name}`, `{number}`, `{total}`, `{balance}`, `{car}`, `{workshop}`, `{days}`) are replaced with the real details; a misspelt field shows as typed instead of stopping the sale. The reminder days and the service interval are set on the same page.

### Connecting WhatsApp
Messages are sent through **Twilio WhatsApp**. Without credentials the system runs in **dry-run**: every message is queued and none is sent, and the Messages screen says so. To connect, set these on the server (never in the app or the repository):
| Setting | Meaning |
|---|---|
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` | The Twilio account |
| `TWILIO_WHATSAPP_FROM` | The approved sender number, like +923001234567 |
| `PUBLIC_URL` | The address Twilio reaches the server on (used to check the signature), no trailing slash |

In Twilio, point the sender's **status callback** to `PUBLIC_URL/api/webhooks/twilio/status` and **incoming messages** to `PUBLIC_URL/api/webhooks/twilio/inbound`. Both check Twilio's signature and refuse anything else. Status updates move a message to Delivered or Read (a late "sent" never undoes "delivered"); a customer who replies **STOP** is opted out at once.

### Rules
- A failed send never stops a sale, invoice or payment: the message is kept as **Failed** and can be retried.
- Phone numbers are turned into international form (03001234567 becomes +923001234567).
- Customer-facing documents can still be shared by hand from their print page (section 15).

---

## 25. Server, backups and sync

### The workshop server
One PC in the workshop runs everything (database, API, web app) in Docker; every device uses it over the Wi-Fi. If the internet is down, nothing stops: the workshop never needs the internet to work. The step-by-step install, update, backup and restore instructions are in [docs/RUNBOOK.md](RUNBOOK.md).

- `docker-compose.yml` starts **db**, **api** and **web** (and **sync**, only when asked for). `workshop.env.example` lists the settings; copy it to `.env`.
- **Backups:** `deploy/backup.sh` writes the database and all proof files to a dated folder with checksums and keeps the last 14. Run it nightly and copy the folder off the PC. `deploy/restore.sh` puts a backup back after checking its checksums and asking for confirmation. A damaged backup is refused before anything changes.

### Cloud sync
The workshop never depends on the internet. With sync switched on, a worker on the workshop PC does two things every minute (and when someone presses **Sync now**):
1. **Sends** every change made since last time, oldest first, to the cloud.
2. **Brings in** what other branches did, using a bookmark ("cursor") so each change is received once.

- **Safe to repeat.** Every change has a number from its branch; the receiver remembers the numbers it has applied, so a resend after a dropped connection changes nothing.
- **Never out of order.** If one change can't be applied, the batch stops there, everything before it is confirmed, and the rest waits and is retried. Nothing after a failure is skipped.
- **Outages.** Without internet the changes simply wait. After a failed attempt the worker waits longer each time (up to 15 minutes) so a dead link isn't hammered.
- **Newer wins.** A change with a higher version replaces ours; a lower one is ignored. **The same version with different content** means two places edited the same record independently: ours is kept, and a **conflict** is recorded with both versions.
- A change brought in from the cloud is not sent back out.

**Where:** Administration → **Cloud sync** (admins, permission `sync`).
- **Status:** changes waiting to be sent (and how old the oldest is), last sent, last received, the last error if the latest attempt failed, and how many conflicts need a decision. **Sync now** runs it immediately.
- **Conflicts:** each one shows only the fields that differ, **This server** against **Other server**. Choose **Keep this server's** (our version is raised so it wins everywhere) or **Take the other server's**. A settled conflict stays on the **Settled** list. Whoever settles it and when is recorded.

**Connecting a branch (once the cloud server exists):**
1. On the cloud, an admin creates the branch's token (`POST /api/sync/tokens` with the branch id shown on the Cloud sync page). The token is shown once; only its fingerprint is stored.
2. On the workshop PC set `SYNC_CLOUD_URL` and `SYNC_TOKEN` in `.env`, then `docker compose --profile sync up -d`.
3. Use **HTTPS** for the cloud address: the token travels with every request.

**Known limit:** conflicts are found when both sides reach the same version number with different content. If one side edits a record twice while the other edits it once, the higher version wins without a conflict (every change is still kept in the audit log). Proof files are not sent by sync yet; they are covered by the nightly backup.

---

## 26. The Help page (user manual)

**Where:** Help → User manual (everyone who is signed in; no permission needed).

A step-by-step manual with procedures (SOPs) for every area: start here, front desk, workshop, billing and releasing the car, stock and purchasing, money and the daily close, people and payroll, owner and accountant (reports, month end), customer messages, administration, troubleshooting, and daily, weekly and monthly checklists. Each procedure says **who** does it, the **steps**, **how to tell it was done right** and **what to avoid**. The golden rules are at the top.

- **Search** filters the procedures as you type (try "refund" or "payroll"). **Print this manual** prints it (the search box and contents are left out).
- **For developers:** the text is data in `web/content/manual.ts` (chapters of procedures); the page is `web/app/(app)/help/page.tsx`. **When a screen, button name or rule changes, update the manual in the same commit**, together with this guide.

---

## 27. Interface behaviour

- **Search and shortcuts.** Ctrl+K (Cmd+K on a Mac), or the magnifying glass on a phone, opens a search of every page and action the person is allowed to use; arrow keys and Enter work without a mouse. "G" then a letter jumps to a page (G D dashboard, G V cars in the workshop, G Q quotations, G R repair orders, G I invoices, G C customers, G A cars, G S inventory, G M messages, G H manual, G N check in a car, G P counter sale). Shortcuts never fire while typing in a field. Code: `web/components/command-menu.tsx`; shortcut letters sit on the `NAV` entries in `web/components/shell.tsx`.
- **Loading.** A skeleton appears only if loading takes longer than 300 ms, so quick loads never flash. Lists of customers, cars, visits, employees and labour codes show the last answer instantly and refresh in the background, again when the window regains focus or the network returns (`useApi(path, { swr: true })`). Money, stock, invoices and balances are never shown from the cache.
- **No duplicate records.** Every create or change the browser sends carries an `Idempotency-Key`. The same request sent again (a double click, a retry after a dropped connection) is answered with the first result and done once; the server remembers keys for 24 hours, per signed-in session. A key reused for a different request is refused (422); a request still running answers 409 "already being processed". Failed requests do not use up the key. Code: `api/app/idempotency.py` (middleware), `web/lib/api.ts`.
- **Instant feedback.** Marking a repair job To do / Done / Not done updates the screen at once and goes back with the error if the server refuses. Nothing that moves money or stock is ever done optimistically.
- **Phones.** The page extends to the screen edges on notched phones, with padding so nothing sits under the notch or the home bar. The menu can be swiped left to close. Corners are continuous (squircle) in browsers that draw them. Numbers in tables and amount fields use tabular figures so columns line up.
- **Clarity.** The Dashboard states the main finding under its title and has the most frequent job ("Check in a car") one click away; a visit shows its **Next step** in plain words at the top.
- **Search on every working list.** Invoices, Quotations and Repair orders each have a search box (above the status filter) that finds by document number, customer name, customer phone, number plate or visit number; the search is kept in the address, so a search can be shared. Cars in the workshop, Customers and Cars have theirs too.
- **No dev-time "instant navigation" warnings.** Every screen is a small server page (`page.tsx`, with `export const instant = false`) that renders the real screen from `view.tsx` beside it. New screens follow the same pair of files.
- **Notices (toasts).** After every successful save the system shows a short notice at the bottom of the screen ("Payment recorded", "Invoice issued", "Saved"); it clears itself after 5 seconds and has a close button. A failure the person cannot fix (no connection, a server error) shows a red notice for 9 seconds. Mistakes they can fix (a missing field) stay on the form as before. Sign-in, autosave and the screens that already say what happened are quiet. Notices are announced to screen readers. Code: `web/lib/toast.ts`, `web/components/toaster.tsx`; the wording per action is the `DONE` list in `web/lib/api.ts` (pass `toast: "..."` or `toast: false` to `api()` to change one call).
- **Back button.** Every record or form screen (a visit, a customer, an invoice, a purchase order, a month, a new check-in...) has a Back button at the top. It returns to the screen the person came from, or to the list when they opened the record directly. List screens do not have one.

### Printed documents and Excel
- **Every printed document is laid out for A4 portrait**, 12 mm margins, black on white, table headings repeated on each page, and no table row, list item or heading split across a page break. This is applied by the bar at the top of every document (`web/components/print.tsx`). The gate pass and the payslip, which were A5, are now A4 too.
- **Quotation terms and conditions.** A quotation prints on one sheet, followed by a page headed **TERMS & CONDITIONS** with a signature line. The standard text is the 15 clauses of the legacy system's quotation, word for word (`api/app/terms.py`). Administration → Branch settings has a box to change them (one clause per line); clearing the box and saving returns to the standard text. Invoices do not carry terms (as in the legacy system).
- **Download for Excel** is on every printed document (quotation, invoice, purchase order, visit record, inspection, gate pass, payslip, closing pack). It makes a real `.xlsx` of what is on the page: headings, lines of text, numbered clauses and every table, one row each, with amounts as real numbers so Excel can add them up, bold headings, and A4 page setup. Code: `web/lib/xlsx.ts` (no spreadsheet library; it writes the file format directly with `fflate`).

---

## 28. Roles and hand-offs

The system is built so that one job passes from person to person **without anyone telling anyone**. Each step ends in a state (a quotation is approved, a repair is Ready, an invoice is paid), and that state puts the next task in front of the right role.

### Suggested roles
Each person gets **one** role, holding only the permissions for their part. Seven standard roles are created by the first-run setup (`uv run python -m app.seed ...`; running it again adds any that are missing and never changes a role that exists).
| Role | Does | Cannot |
|---|---|---|
| **Owner (Admin)** | Everything, and the decisions only an owner makes: releasing a car on credit, accepting a payment with no proof, reopening a month, refunding a held advance. | |
| **Manager** | Runs the workshop floor: customers, check-in, job cards, quotations, repair orders, invoices; sees stock and the workshop report; messages; accepts payments without proof. | Take or pay money, close months, see the books. |
| **Front desk** | Receives customers and cars, checks cars in, inspections, job cards, prices and sends quotations, records the customer's approval, WhatsApp messages. | Issue invoices, take money, issue parts. |
| **Technician** | Repair orders: issues parts, marks jobs done, writes findings, moves the job to Ready. Inspections. | See prices of other work, money, customers' accounts. |
| **Cashier** | Makes and issues invoices, takes payments and advances, counter sales. | Pay vendors, change stock, close the day. |
| **Guard** | Sees only **Cars ready to leave** and releases a car with the gate pass (odometer, who took it). A car that still owes money cannot be released by the guard. | Everything else. |
| **Accountant** | Pays vendors, records expenses, cash close each evening, missing-proof follow-up, payroll, reports, month end. | Take customer payments, receive stock. |
| **Inventory manager** | Inventory, stock counts, vendors, purchase orders, receiving deliveries. | Pay the bill, see the books. |

**Small workshop?** Make a custom role under Administration → Roles and permissions that adds the permissions of two roles (for example **Front desk + Cashier**). Keep these apart even in a small team, so no one person can take the money and also close the day: *receiving stock* and *paying the bill*, and *recording money* and *closing the day*.

### The hand-off chain
| Step | Who finishes it | What puts the next task on someone's screen |
|---|---|---|
| Car arrives, checked in | Front desk | Front desk (and technician): **Cars waiting for a job card** |
| Job card done, quotation made | Front desk | **Quotations to price and send** |
| Quotation sent | Front desk | **Waiting for the customer's answer** (follow-up) |
| Customer approves | Front desk | Manager: **Approved: make the repair order** |
| Repair order made | Manager | Technician: **Repairs in progress** |
| Repair moved to Ready | Technician | Cashier or manager: **Finished repairs: make the invoice** |
| Invoice made | Cashier | **Invoices to check and issue** |
| Invoice issued | Cashier | Cashier: **Waiting for payment**; guard: car appears in **Cars ready to leave**, marked "owes" until paid |
| Invoice paid | Cashier | Guard: **Release this car** |
| Car released | Guard | Visit closes |
| Stock runs low | (automatic) | Inventory manager: **Running low: order more**; accountant sees the **bills to pay** |
| Purchase order sent / goods arrive | Inventory manager | **Deliveries to receive**, then accountant/purchasing: **Deliveries waiting for the vendor's bill**, then **Vendor bills to pay** |
| Evening | Accountant | **Close today's cash**; owner: **Payments with no proof** |
| Month ends | Accountant | **Months to close** |

### My work
**Where:** the Dashboard, first section. It lists only the queues for the work **the signed-in person's permissions allow**, each with a count, the oldest items (and how long they have waited) and a "See all" link. Nothing there to do: "Nothing is waiting for you." People whose work is not the overview (guard, technician, cashier) see only My work; owners, managers and accountants also see the overview numbers below it. Queues are worked out from the records themselves (`api/app/routers/mywork.py`, `GET /api/my-work`), so they depend on **permissions, not role names**, and a custom role gets exactly the queues its permissions imply. Each visit also shows **Next step ... For: Cashier** at the top.

### Cars ready to leave (guard)
**Where:** Cars ready to leave (needs `gate` or `visits`; endpoint `GET /api/gate/queue`). Each car shows its plate, car, customer and invoice. **Release this car** opens a short form (odometer now, who is taking the car); a car that still owes money shows "Do not release" instead, because only a person holding `release-on-credit` may release it on credit, from the visit page.

---

## 29. Team feedback round (33 items)

Kept current as each story lands (stories US-1001 to US-1013 in `prd.json`).

- **US-1001 look and feel.** Cancel buttons use the red `danger` variant. Sidebar section titles are bold. `Field` shows a red asterisk unless its label contains "(optional)"; pass `required` to force it. The visit page has a progress bar (`JobProgress`: checked in, job card, quotation, approved, repair, ready, invoiced, paid, left). Back also shows on report, settings and admin pages. A repair order can only go to Ready from Testing.
- **US-1002 to US-1005.** Brand, category and car make are pick-lists (`ChoiceSelect`, lists in `web/lib/lists.ts`, with an "Other" way out). Counted units (pcs, set, pair, box) take whole numbers only; litre, kg and metre take decimals (`qtyStep`). Labour codes are made by the system (LAB-0001, ...). CNIC is required for customers (API and form). Customer pickers have "+ New customer" (a dialog). Forms reset their Saving state after a successful save. Quotation: Revise and Approve ask to confirm; an advance cannot take the held advances past the quotation total.
- **US-1007 attendance.** An employee has several weekly days off (`days_off`, migration 0025). A day can be marked **present** (counts as 8 hours) besides paid or unpaid leave. Missed punch, leave and mark present live on the Attendance screen ("Add or fix a day by hand"). Each device has an **Activity log** (`device_logs`, migration 0026): punches received and refused calls.
- **US-1008 to US-1011.** Payroll adjustments have a Bonus/Penalty switch and each amount can be rupees or a percentage (of base pay for bonus and penalty, of what is owed for the advance take-back). A held advance can be refunded in parts (`payments.refunded_amount`, `Payment.held`, migration 0027); voiding a refund puts the money back on hold. `/gate` shows **Cars that have left** (`GET /api/gate/history`). Items can have several vendors (`item_vendors`, migration 0028, `PUT /api/items/{id}/vendors`); the purchase order's "Add everything below its reorder level" adds only that vendor's items (and items with no vendor set) at the vendor's last price, and suggests a quantity of twice the reorder level less what is in stock. How much to order is decided on the purchase order, so the item form no longer asks for a reorder quantity.
- **US-1012 money.** Money out has **Add a daily expense** (category pick-list, today's total shown) apart from **Record other money out** (owner drawings, transfers). Money in starts with **Payment for an invoice**: pick the unpaid invoice from a list and the amount fills in. The red `*` on a field label shows only inside a form (CSS `.req`), so search and filter boxes stay clean.
- **Phone numbers** are stored and shown in international format (`+92 300 1234567`). Other country codes are kept as typed (`+971 ...`); a number starting 0 or 92 is taken as Pakistani. **Required marks:** the purchase order screen and the inspection (overall condition, recommendation, inspector signature) mark what is needed with a red `*`.
- **Newcomer test pass.** A walk through the whole job as a first-time user changed: the red `*` now shows only where a field is really required (`Field required`, or the control has `required`); the "Required" message reads "Please fill in: ..."; the car page has **Check in this car** (`/visits/new?car=ID`) and check-in offers **Add a new customer and car**; the visit page next step links to the job panel; a sent quotation explains what to press next; the paid invoice says the car can now leave; the gate list refreshes after a release; notices appear top right and a plain "Saved" is dropped when a specific notice shows; status badges use teal, not red; the dashboard has a hideable **How a job goes** strip (`HowItWorks`).
- **Visit progress bar** is now `web/components/job-progress.tsx`: round icons joined by a line (finished filled, current ringed, later grey), labels under each icon on wide screens and "Waiting for: ... (step 5 of 9)" on phones. `stepsOf(v)` in `visit-page.tsx` decides which steps are done.
- **Next step banners.** Every workflow page shows a highlighted **Next step** (`web/components/next-step.tsx`): a teal-barred card with the instruction, who it is for, and a button that does it. `target="act-..."` points at the page's own button by id: by default it opens that form (`open`), and `open={false}` only scrolls to the button and focuses it (used for actions that commit, such as issuing an invoice). When you add a workflow screen, add its `NextStep` too. Pages that have one: visit, job card, quotation, repair order, invoice, counter sale, purchase order, bill, payroll run, customer.
- **Users list** shows a missing phone as "Not added" and formats numbers like the rest of the app. Checked live with no changes needed: Messages, Month end checklist (each red line has a Fix it link), Roles, Money settings, Finance reports, Payroll (clear messages for a month not yet ended, a month with no staff, and a month already run).
- **Print pages and phone width checked.** The print toolbar button is teal (red means danger). All 26 list screens have no sideways scroll at 375 px.
- Empty-state links and proof links use teal (`text-primary`), not the red accent.
- Checked live: payroll Adjust (bonus or penalty, Rs or %, with a live "10% of base pay = Rs 2,600" hint), payslip print, throwing away a draft (notice now says "Draft thrown away"). "Please fill in:" keeps acronyms like CNIC in capitals. Employee details show "Not added" for empty fields.
