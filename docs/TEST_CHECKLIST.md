# GermanATO: team test checklist

Use this to test the whole app before it goes live, and again after every update. Tick each box as you go. Anything that does not behave as written is a bug: write it down using the form at the end.

How long it takes: the smoke test is about 15 minutes. The full run is about one working day for two people.

---

## 0. Before you start

**Use a practice copy, never the real workshop data.** Money, stock and numbers cannot be undone (mistakes are voided, never deleted), so test records stay in the books.

- [ ] The app opens at the practice address and the sign-in page shows.
- [ ] The Owner (Admin) account is ready. Ask the owner for the practice password. Never share it in a group chat.
- [ ] Make one test user for each role (Administration → Users): **Manager, Front desk, Technician, Cashier, Guard, Accountant, Inventory manager.** Give each a different username. Write the list on the results sheet.
- [ ] Under Money settings, the cash, bank and wallet accounts exist. Set opening balances so you can see the numbers move.
- [ ] Under Inventory, add **2 parts with opening stock** (for example 10 oil filters and 4 brake pads) and add **2 labour codes** (for example "Oil change", "Brake pad fitting").
- [ ] Keep these at hand: a phone (about 375px wide), a tablet or a narrowed browser window (about 768px), a desktop, and a real A4 printer (or "Save as PDF" with paper size A4).
- [ ] Two people, two browsers: one tester signs in as the role being tested, the other watches the Owner's screens.

**Test data to reuse** (so nobody invents odd values):

| What | Use |
|---|---|
| Customer | Ali Khan, phone 0300 1234567 |
| Second customer | Sara Ahmed, phone 0321 7654321 |
| Car | Toyota Corolla, plate LEA-1234, VIN `JTDKB20U093123456` |
| Vendor | Auto Parts Co. |
| Proof file | any small photo or PDF |

**How to read each line:** *Do* is what you click or type. *Expect* is what must happen. If *Expect* does not happen, stop and report it.

---

## 1. Smoke test (15 minutes, do this first, and after every update)

As the Owner:

- [ ] **Sign in.** Expect: the Dashboard opens with "My work" first.
- [ ] Open every item in the left menu one by one. Expect: each screen loads, no red error, no blank page.
- [ ] **Check in a car** (Visits → Check in a car) using the test customer and car. Expect: a visit page opens with a visit number.
- [ ] Write a **job card** with one labour line and one part. Expect: it saves, a success notice appears at the bottom or top of the screen.
- [ ] Press **Back** at the top of the screen. Expect: you return to the previous screen, not the sign-in page.
- [ ] Press **Ctrl+K** (Cmd+K on Mac). Expect: the quick-search menu opens; type "invoices" and press Enter to jump there.
- [ ] Open **Help**. Expect: the manual shows with chapters.
- [ ] **Sign out** and sign in as the Guard. Expect: the Guard sees almost nothing except "Cars ready to leave".

If any of these fail, stop. Do not continue with the full test until it is fixed.

---

## 2. Sign-in and access

### 2.1 Sign-in
- [ ] Wrong password once. Expect: a clear "wrong username or password" message, no hint which one was wrong.
- [ ] Wrong password **5 times** for one user. Expect: the account locks for 15 minutes with a message saying so. The correct password is refused during the lock.
- [ ] Right password after the lock ends. Expect: sign-in works.
- [ ] Open a page address directly while signed out (for example `/invoices`). Expect: sent to the sign-in page, then back to that page after signing in.
- [ ] Sign out, then press the browser Back button. Expect: you cannot see private pages.

### 2.2 What each role sees
Sign in as each test user. For each, check the menu and "My work", then try to open a page they should **not** have by typing its address. Expect: a "you don't have access" message, never the data.

| Role | Should see | Must NOT be able to |
|---|---|---|
| **Owner (Admin)** | Everything | (nothing blocked) |
| **Manager** | Visits, repair orders, invoices, inventory, workshop report, messages | Take payments, pay vendors, close a month |
| **Front desk** | Customers, visits, job cards, quotations, messages, labour codes | Issue an invoice, record a payment |
| **Technician** | Visits, job cards, repair orders (own work) | See money, customers' accounts, reports |
| **Cashier** | Invoices (issue), payments in, customers, counter sales | Pay vendors, change stock |
| **Guard** | Only "Cars ready to leave" (Gate) | Anything else |
| **Accountant** | Vendors, bills, payments out, expenses, cash close, payroll, finance reports, month end | Take customer payments, receive stock |
| **Inventory manager** | Inventory, vendors, purchase orders, goods receipt | Pay the bill |

- [ ] Role table verified for all 8 roles. Note any difference in the results sheet.
- [ ] **Separation of duties:** the person who receives stock against a purchase order cannot pay that same bill; the person who pays cannot receive stock. Try it with the Inventory manager and the Accountant.
- [ ] Create a custom role with a few permissions and a user on it. Expect: that user sees exactly those screens and no others.
- [ ] Remove a permission from a role while a user of that role is signed in. Expect: after reloading, the screen is gone.

---

## 3. Workflow A: a car through the workshop (the main one)

Follow one car all the way. Use the role shown in brackets; the **Next step … For: <role>** line on the visit page tells who is next. Every step must show up in that person's "My work" without anyone telling them.

### A1. Check in [Front desk]
- [ ] Visits → Check in a car. Add **new customer** and **new car** (plate, make, model, VIN, odometer). Expect: visit number is created, status "Checked in".
- [ ] "My work" for the **Front desk** now lists "Job card needed" for this car.
- [ ] Try a **second customer with the same phone number**. Expect: a "customer already exists" warning showing the match, not a silent duplicate.
- [ ] Type a bad VIN (too short) and a bad phone. Expect: red message beside the field before saving.
- [ ] VIN and chassis number are **one field**. Expect: no separate chassis box anywhere.
- [ ] Attach a photo of the car as an attachment. Expect: it shows on the visit.

### A2. Inspection (optional) [Front desk / Technician]
- [ ] Start an inspection. Mark items OK / needs attention, add notes, add a photo. Expect: saves and shows on the visit.
- [ ] Print the inspection. Expect: clean A4 page (see section 8).

### A3. Job card [Front desk]
- [ ] Add one labour line and one part using the picker (type a name, or scan/type a barcode and press Enter). Expect: only labour codes and stock items can be added, never free text.
- [ ] Set quantity **1** for a line. Expect: accepted, no red mark.
- [ ] Try quantity 0 or a negative number. Expect: refused with a message.
- [ ] Add a part that is out of stock. Expect: the picker says "Out of stock", but you can still plan it.
- [ ] Save, reload. Expect: lines are still there.
- [ ] "My work" for the Front desk now lists "Quotation to prepare".

### A4. Quotation [Front desk]
- [ ] Make the quotation from the job card. Expect: prices fill in from the catalogue; you can edit them.
- [ ] Add the legacy **terms and conditions** (15 clauses). Expect: they show on the printout on their own page.
- [ ] Mark the quotation **Sent**. Expect: status "Sent, waiting for the customer"; "My work → Quotation waiting for the customer" appears.
- [ ] Check **Messages**. Expect: a "quotation sent" WhatsApp message is **queued** (nothing really sends unless Twilio details are set).
- [ ] Record the customer's approval with a **proof file** (photo of a signature or a screenshot). Expect: status "Approved".
- [ ] Try approving **without proof or reason**. Expect: refused.
- [ ] Decline one line on the quotation. Expect: that line drops out of the total.
- [ ] Reject a second quotation, then revise it. Expect: the old one shows "Replaced by a revision".
- [ ] Search the Quotations list by number, customer name, phone and plate. Expect: each finds it.

### A5. Advance (money in) [Cashier]
- [ ] On the visit, take an **advance** (for example 5,000). Pay by cash, then try a bank transfer with a proof file. Expect: money appears in Money in and the right account goes up.
- [ ] Take an advance by bank/wallet **without proof**. Expect: refused (or needs a written reason from someone with Evidence sign-off).

### A6. Repair order [Manager]
- [ ] "My work" for the Manager lists "Make repair order". Make it from the approved quotation. Expect: stage "In progress"; parts reserved/listed.
- [ ] Try to make a repair order **without an approved quotation**. Expect: not possible.

### A7. Repairs [Technician]
- [ ] "My work" for the Technician lists the repair order.
- [ ] **Issue a part.** Expect: stock on hand drops by exactly that quantity; Inventory → the item → movements shows the issue.
- [ ] Try to issue **more than is in stock**. Expect: refused with the shortage shown.
- [ ] Mark a line **done** (and tick it again to undo). Expect: the change shows immediately; if the network fails, it flips back with a notice.
- [ ] Add findings / notes.
- [ ] Move the order to **Ready**. Expect: "My work" for the Cashier lists "Make invoice"; the customer gets a "car ready" message (queued).

### A8. Invoice [Cashier]
- [ ] Make the invoice from the Ready repair order. Expect: lines match the repair order exactly; the advance is applied.
- [ ] Try to make an invoice for a repair order that is **not Ready**. Expect: refused.
- [ ] **Issue** the invoice. Expect: prices are locked; the invoice number is gap-free (no number skipped).
- [ ] Try to edit an issued invoice. Expect: not possible. Correct it with a **credit note** instead.
- [ ] Search Invoices by number, customer, phone and plate. Expect: each finds it.

### A9. Payment [Cashier]
- [ ] Take a **part payment**. Expect: balance goes down; status "Part paid".
- [ ] Take the **rest**. Expect: balance 0; status "Paid".
- [ ] Pay by cash, bank and wallet at least once each. Expect: the right account moves each time.
- [ ] Double-click the Save button on a payment. Expect: **one** payment recorded, not two.
- [ ] Try to pay more than the balance. Expect: refused or flagged as an overpayment (not silently taken).

### A10. Gate [Guard]
- [ ] As the **Guard**, open "Cars ready to leave". Expect: this car appears only once it is fully paid.
- [ ] A car that still owes money: Expect: shown as **"Do not release"** and the Guard cannot release it.
- [ ] Release the paid car with the gate pass form (name of person collecting, odometer out). Expect: visit closes; a printable gate pass is produced.
- [ ] As the Owner, release a car **on credit** (needs the release-on-credit permission) with a written reason. Expect: allowed, and recorded in the audit log.
- [ ] After release the visit shows as closed and nobody can add to it.

### A11. Visit record
- [ ] Open the visit page. Expect: the "The job" panel shows job card, quotation, advance, repair order and invoice, each opening the right document.
- [ ] Print the whole **visit record** (A4). Expect: clean, readable.

---

## 4. Workflow B: counter sale (no car)

- [ ] Counter sale: sell 2 parts to a walk-in customer (name optional). Expect: invoice made, stock goes down.
- [ ] Take payment, issue, print. Expect: prints on **A4** (counter sales print A4 invoices only, no slip printer layout).
- [ ] Sell more than is in stock. Expect: refused.
- [ ] Sell to a registered customer. Expect: shows in their account.

---

## 5. Workflow C: buying stock and paying vendors

### C1. Setup
- [ ] Add a vendor [Inventory manager]. Expect: appears in Vendors; a duplicate name is warned.

### C2. Order and receive
- [ ] "My work" for the Inventory manager shows low stock. Create a **purchase order** for the low item. Expect: PO number created.
- [ ] Send / print the PO (A4). Expect: clean.
- [ ] **Receive** part of the order (goods receipt). Expect: stock goes up by the counted quantity only; the PO shows "Part received".
- [ ] Receive the rest. Expect: PO "Received"; the stock movement history shows both receipts.
- [ ] Try to receive more than ordered. Expect: refused or flagged.

### C3. Bill and pay [Accountant]
- [ ] "My work" for the Accountant shows "Bill needed". Record the **vendor bill** with the vendor's invoice number and a photo. Expect: shows as owed to the vendor.
- [ ] **Pay** the bill (cash/bank with proof). Expect: vendor balance falls; money goes out of the right account.
- [ ] Part pay, then pay the rest. Expect: balance tracks correctly.
- [ ] Void a vendor bill with a reason. Expect: stays on record, marked void, balance corrected.
- [ ] **Same person rule:** the Inventory manager cannot pay; the Accountant cannot receive.

---

## 6. Workflow D: day-to-day money

- [ ] **Money in** list: shows every advance and payment. Filter by date and by account. Expect: totals match.
- [ ] **Money out → expense**: record a daily expense (for example tea, 500) and a major expense (for example rent) with proof. Expect: the account goes down.
- [ ] Record a money item **without proof** as a normal user. Expect: refused. As the Owner with a written reason (Evidence sign-off). Expect: accepted and listed under **Missing evidence**.
- [ ] **Cash close** (end of day) [Accountant]: count cash, bank and wallet. Enter a counted amount that differs from the book. Expect: the difference is shown and a reason is required.
- [ ] After closing the day, try to post money to that closed day. Expect: refused.
- [ ] **Credit note**: issue one against an invoice for a return. Expect: the invoice balance and stock/money follow the rules; the original stays on record.
- [ ] **Advance refund**: refund an unused advance. Expect: needs admin approval.

---

## 7. Workflow E: people and payroll

- [ ] Add an employee (name, CNIC, salary). Expect: bad CNIC refused.
- [ ] Record attendance: present, absent, late, leave for a few days. Expect: counts update.
- [ ] Give a **salary advance**. Expect: shows in the employee's page and is deducted in payroll.
- [ ] **Run payroll** for the month. Expect: one pay slip per employee with correct days, deductions and net pay (check one by hand).
- [ ] Print a pay slip (A4). Expect: clean, one employee per page.
- [ ] Pay the payroll. Expect: money goes out of the chosen account.
- [ ] As a user without `payroll`/`hr`, try to open `/payroll`. Expect: no access.

---

## 8. Workflow F: reports and month end

- [ ] **Dashboard → My work**: counts match the real records (create one overdue item, check it shows "waiting" hours).
- [ ] **Operations report**: visits, repair times, parts used. Expect: numbers match what you created.
- [ ] **Finance reports**: journal and trial balance. Expect: trial balance **balances** (debits = credits). Spot-check a sale shows in the journal.
- [ ] **HR report**: attendance and payroll summary.
- [ ] **Month end** [Accountant]: open the checklist. Expect: every open item (unpaid draft, un-closed day, missing evidence) is listed.
- [ ] Close the month. Expect: no new money records can be dated inside it.
- [ ] Reopen it as the Owner (period-approve). Expect: allowed with a reason; non-owners cannot.
- [ ] Download any report to **Excel**. Expect: a file opens in Excel with the same numbers.

---

## 9. Workflow G: customer messages (WhatsApp)

- [ ] Messages screen lists queued messages with status. Expect: with no Twilio details set, they show as queued/dry-run, nothing is sent.
- [ ] Settings → Messages: edit the wording of one template, **Save**. Expect: success notice; reload shows the new wording (this used to fail once, so check it).
- [ ] Turn a template off. Expect: that event no longer queues a message.
- [ ] Change the reminder days. Expect: saved.
- [ ] Retry a failed message. Expect: it requeues once, not twice.
- [ ] **Only if real Twilio details are set on a practice number:** send one message to a team phone. Expect: it arrives; a reply or delivery update changes the status.

---

## 10. Workflow H: administration

- [ ] Branch settings: change the workshop name, tax rate and **quotation terms**. Expect: new name/terms appear on the next printout; old issued documents keep what they had.
- [ ] Users: add, disable and re-enable a user. Expect: a disabled user cannot sign in.
- [ ] Roles: add a role, edit permissions, delete a role that has no users. Expect: a role with users cannot be deleted.
- [ ] **Audit log**: change a customer's phone number, then find it. Expect: shows who, when, the old and new value.
- [ ] Customers: edit; search by name, phone and plate; open a customer and see their cars, visits and balance.
- [ ] Cars: **transfer** a car to another owner (needs car-transfer permission). Expect: history keeps the old owner.
- [ ] Labour codes: add, edit, switch off. Expect: switched-off codes cannot be added to new job cards.
- [ ] Inventory: add an item, adjust stock (count or write-off, needs stock-adjust). Expect: a movement is recorded, stock never edited directly.

---

## 11. Server and sync (only if the shop uses cloud sync)

- [ ] Settings → Sync shows the status and the last sync time.
- [ ] Run a sync. Expect: finishes without errors; a counter shows what was sent.
- [ ] Stop the internet on the workshop PC, create a visit, turn it back on. Expect: the work is kept and uploads later.
- [ ] Make the same record change on two branches. Expect: a **conflict** appears under Sync → Conflicts and the admin can settle it.
- [ ] Backup and restore: follow `docs/RUNBOOK.md` on a practice machine. Expect: after restore the data (last invoice, last payment) is all there.

---

## 12. Rules that must never break

Try to break each on purpose:

- [ ] **No gaps in numbers:** make 3 invoices quickly from two browsers at once. Expect: three consecutive numbers, no duplicate, no gap.
- [ ] **No silent overwrite:** open the same customer in two browsers, edit and save in both. Expect: the second save is refused with "changed on another device, reload".
- [ ] **Double clicks / bad network:** double-click Save on a payment, issue-invoice, release-car. Expect: it happens once.
- [ ] **Nothing is deleted:** there is no way to delete an invoice, payment, or stock record; only void with a reason.
- [ ] **Stock is the sum of its movements:** for one item, add up receipts minus issues and sales. Expect: equals "on hand".
- [ ] **Invoices bill what was issued:** change a labour price in the catalogue after issuing. Expect: the old invoice does not change.
- [ ] **Proof on every money record,** or a written reason.
- [ ] **Permissions on the server:** hiding a button is not enough. As a Guard, try opening a manager page address. Expect: refused.

---

## 13. Printing and Excel

Open each printed page from its **Print** button, in the browser print preview. Paper size must be **A4**, margins default.

| Document | Print | Excel |
|---|---|---|
| Quotation (with terms on their own page) | [ ] | [ ] |
| Inspection report | [ ] | n/a |
| Visit record | [ ] | n/a |
| Invoice | [ ] | [ ] |
| Counter sale invoice | [ ] | [ ] |
| Gate pass | [ ] | n/a |
| Purchase order | [ ] | [ ] |
| Pay slip | [ ] | n/a |
| Month end | [ ] | [ ] |

For each print, check:
- [ ] Fits one A4 width: nothing cut off at the right edge.
- [ ] No page break through the middle of a table row or the totals.
- [ ] No menus, buttons or page backgrounds on paper.
- [ ] Workshop name, numbers, dates and totals are right and readable at arm's length.
- [ ] Long customer names and many lines still look neat.
- [ ] Excel: opens in Excel with columns in order, numbers as numbers (not text), totals match the screen.

---

## 14. Screen sizes and touch

Test the main screens (Dashboard, Visit, Job card, Quotation, Repair order, Invoice, Gate, Inventory list) at each size. Use browser device mode or real devices.

| Size | Width |
|---|---|
| Small phone | 320px |
| Phone | 375px |
| Tablet | 768px |
| Desktop | 1280px or wider |

At each size:
- [ ] Nothing is cut off, overlapping or touching the edge. No sideways scrolling on the page itself (wide tables may scroll inside their own box).
- [ ] The menu opens, can be swiped closed on a phone, and every item is reachable.
- [ ] Buttons and links look clickable and are easy to hit with a thumb (about 44px).
- [ ] The main action on each screen is obvious in 30 seconds (a new person should say "what is this page for, what do I do next" without help).
- [ ] The keyboard on a phone doesn't hide the field you are typing in.
- [ ] Rotate a tablet/phone. Expect: the layout adapts.
- [ ] Dark mode (if on): text readable.

---

## 15. Speed and feel

- [ ] Every list opens in under 2 seconds with about 500 records (make them with the practice data).
- [ ] After saving, the screen updates straight away (no need to reload).
- [ ] A slow or lost network shows a clear notice and never loses what you typed.
- [ ] Every action gives feedback: a success notice, a loading state, or a clear error.
- [ ] Every screen has a **Back** button that goes to the logical previous screen.
- [ ] Empty screens (no customers yet) explain what to do next.

---

## 16. Sign-off

| Area | Tested by | Date | Pass / Fail |
|---|---|---|---|
| Smoke test | | | |
| Access and roles | | | |
| Workflow A: car through the workshop | | | |
| Workflow B: counter sale | | | |
| Workflow C: buying and vendors | | | |
| Workflow D: money | | | |
| Workflow E: people and payroll | | | |
| Workflow F: reports and month end | | | |
| Workflow G: messages | | | |
| Workflow H: administration | | | |
| Server and sync | | | |
| Rules that must never break | | | |
| Printing and Excel | | | |
| Screen sizes | | | |
| Speed and feel | | | |

Go-live only when every row says Pass, or each Fail has a written decision from the owner.

---

## Bug report form (one per problem)

```
Title:            (one line: what went wrong)
Where:            (screen and address, e.g. /invoices/…)
Signed in as:     (role / username)
Device and size:  (phone / tablet / desktop, browser)
Steps:            1.  2.  3.
Expected:         (copy the Expect line from this checklist)
What happened:
Screenshot:       (attach)
How bad:          Blocks work / Wrong money or stock / Annoying / Cosmetic
```

**How bad, in plain words:**
- *Blocks work:* a person cannot finish their job. Fix before go-live.
- *Wrong money or stock:* a total, balance or quantity is wrong. Fix before go-live, the highest priority.
- *Annoying:* works but is confusing or slow. Fix soon.
- *Cosmetic:* spelling, spacing, colour. Fix when convenient.

Developers: see `docs/SYSTEM_GUIDE.md` for how each part works, and the automated tests in `api/tests/` for what is already checked by machine. This list covers what only a person can judge (wording, print, touch, and the hand-offs between people).
