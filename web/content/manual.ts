// The user manual shown on the Help page (and printed from it). Plain data, so it is easy to edit.
// Each procedure says who does it, the steps, how to know it went right, and what to avoid.
// Write for a first-time user: short sentences, everyday words, one action per step.
// Keep it in step with docs/SYSTEM_GUIDE.md whenever a screen or a button name changes.

export type Sop = { id: string; title: string; who: string; steps: string[]; right?: string[]; avoid?: string[]; checklist?: boolean };
export type Chapter = { id: string; title: string; intro: string; sops: Sop[] };

export const RULES: string[] = [
  "Write everything into the system as it happens: every payment, every part, every customer approval. If it is not in the system, it did not happen.",
  "Every payment or expense needs proof: a photo, a screenshot or a PDF. If there really is none, write the reason. For bank or wallet money, also write the transaction number.",
  "Each customer and each car is saved once. To fix a wrong detail, press Edit on that record. Do not type it again somewhere else.",
  "Nobody types a stock number. Stock goes up when goods are received, and goes down when a part is used or sold.",
  "Labour has no fixed price. You type the price on each quotation.",
  "Once something is issued or signed, it is never changed. To fix a mistake, make a new version, a credit note, or cancel the record with a reason. The old record stays visible.",
  "If the screen says someone else changed the record, reload the page and do your change again.",
  "Close the day every evening and the month every month. A closed day or month cannot be changed.",
];

// Everyday meanings of the words the system uses.
export const WORDS: [string, string][] = [
  ["Proof", "A photo, screenshot or PDF that shows a payment or an approval really happened."],
  ["Void", "Cancel a record by mistake or correction. It is not deleted: it stays on the list, crossed out, with your reason."],
  ["Account", "A place money is kept: the cash drawer, the bank, or the mobile wallet."],
  ["Advance", "Money a customer pays before the work is finished. It is kept aside and taken off the final bill."],
  ["Quotation", "The price list you give a customer before the repair. The customer must agree to it."],
  ["Repair order", "The work list the workshop follows after the customer agrees."],
  ["Invoice", "The final bill. Once issued, it cannot be changed."],
  ["Credit note", "A paper that reduces an issued invoice, for returned parts or a correction."],
  ["Gate pass", "The slip that lets a car leave the workshop."],
  ["Average cost", "What a part costs us on average, when we bought it at different prices."],
  ["Reorder level", "When stock falls to this number, it is time to order more."],
  ["Closing a day or month", "Counting the money and locking the records, so nothing can be changed afterwards."],
  ["Audit log", "A permanent list of who changed what, and when."],
  ["Sync", "Sending the workshop's records to the cloud copy when the internet works."],
];

export const CHAPTERS: Chapter[] = [
  {
    id: "roles", title: "Who does what",
    intro: "Each person has one role and sees only their own work. A job passes from one person to the next by itself, so nobody has to tell anyone.",
    sops: [
      {
        id: "my-work", title: "Start your day with My work", who: "Everyone",
        steps: [
          "Open the Dashboard. The first section, My work, lists what is waiting for you, and only you.",
          "Each box is one kind of task: how many there are, the oldest ones, and how long each has waited. Press a line to open it and do it.",
          "When you finish your part, the next person's task appears on their screen by itself. You do not need to call or message them.",
          "If it says \"Nothing is waiting for you\", you are up to date.",
        ],
        right: ["You never have to search for what to do next. Each visit also shows a Next step line saying what is needed and who it is for."],
      },
      {
        id: "role-list", title: "The roles", who: "Owner, to decide who gets which role",
        steps: [
          "Owner (Admin): everything, and the owner-only decisions: release a car on credit, accept a payment with no proof, reopen a month.",
          "Manager: runs the workshop floor. Starts repair orders after approval, makes invoices, watches stock and the workshop report.",
          "Front desk: receives customers and cars, checks cars in, writes job cards, prices and sends quotations, records the customer's approval.",
          "Technician: does the repair. Issues parts, marks jobs done, writes findings, moves the job to Ready.",
          "Cashier: makes and issues invoices, takes payments and advances, counter sales.",
          "Guard: sees only Cars ready to leave and releases a car with the gate pass.",
          "Accountant: pays vendors, records expenses, counts the cash each evening, payroll, reports and month end.",
          "Inventory manager: stock, vendors, purchase orders, receiving deliveries.",
        ],
        avoid: ["In a small workshop one person can do two jobs: ask the owner for a custom role. Never combine receiving stock with paying the bill, or taking money with closing the day."],
      },
      {
        id: "chain", title: "How a car moves from person to person", who: "Everyone",
        steps: [
          "Front desk checks the car in. Front desk is asked for a job card, then a quotation, and follows up the customer.",
          "When the customer agrees, the manager is asked to make the repair order. The technician then sees the repair under Repairs in progress.",
          "The technician finishes and moves it to Ready. The cashier is asked to make and issue the invoice, then to collect payment.",
          "When the invoice is paid, the car appears for the guard under Cars ready to leave. The guard releases it.",
          "Behind the scenes: low stock asks the inventory manager to order; deliveries ask for receiving, then for the vendor's bill, then the accountant is asked to pay it. Each evening the accountant counts the cash.",
        ],
        right: ["Every person's list is short, because it only holds their own work."],
      },
      {
        id: "guard", title: "Release a car (guard)", who: "Guard",
        steps: [
          "Open Cars ready to leave. Each box is a car that is repaired and invoiced.",
          "Check the car and the person collecting it. Press Release this car.",
          "Type the odometer reading and the name of the person taking the car. Press Release the car.",
          "If a car shows Do not release, it still owes money. Send the customer to the cashier. Do not let it go.",
        ],
        right: ["A short notice says the plate was released, and the car leaves your list."],
        avoid: ["Only an administrator can release a car that owes money."],
      },
    ],
  },
  {
    id: "start", title: "Start here",
    intro: "How to sign in, move around, and understand what the screens tell you.",
    sops: [
      {
        id: "sign-in", title: "Sign in and sign out", who: "Everyone",
        steps: [
          "Open the workshop address in your browser. Your administrator will give it to you. It looks like http://<workshop PC>:3000.",
          "Type your username and password. Press Sign in.",
          "If you work at more than one branch, pick the branch from the menu at the top. Everything you record belongs to that branch.",
          "When you finish, sign out from the menu. Always do this on a shared computer or tablet.",
        ],
        right: ["Your name shows in the menu, and the menu lists only what you are allowed to use."],
        avoid: ["Never share your password. Every record carries the name of the person who made it.", "After five wrong passwords the account is locked for 15 minutes. Ask an administrator for help."],
      },
      {
        id: "read-screens", title: "How to read the screens", who: "Everyone",
        steps: [
          "The menu is on the left. On a phone, press the three-line button to open it.",
          "A solid button does something. Underlined words open another page. A row with an arrow on the right opens that record.",
          "Red text means something is wrong or missing. Orange means be careful. Read it: it tells you what to do.",
          "Every list has a search box. On Invoices, Quotations and Repair orders you can type a document number, the customer's name or phone, the number plate, or the visit number. You can also scan a barcode into any part search.",
          "Printed pages (invoice, quotation, inspection, gate pass, purchase order, payslip) have a bar at the top with Back, Print or save as PDF, Share as PDF, Download for Excel, and Send on WhatsApp. They are laid out for A4 paper.",
          "When you save something, a short notice appears at the bottom of the screen, for example \"Payment recorded\". It disappears by itself. A red notice means the save did not happen.",
          "Every record page (a visit, a customer, an invoice and so on) has a Back button at the top.",
        ],
        right: ["You can always go back. Every printed page has a Back link."],
      },
      {
        id: "find-fast", title: "Find anything fast (search and keyboard shortcuts)", who: "Everyone",
        steps: [
          "Press Ctrl and K together (Command and K on a Mac). On a phone, tap the magnifying glass at the top. A search box opens.",
          "Type a few letters of the page or action you want, for example \"repair\" or \"check\". Use the up and down arrow keys, then press Enter. Press Esc to close.",
          "Shortcuts: press G, then a letter. G D is the Dashboard, G V cars in the workshop, G Q quotations, G R repair orders, G I invoices, G C customers, G A cars, G S inventory, G M messages, G H this manual, G N check in a car, G P a new counter sale. Each shortcut is shown beside its name in the search box.",
        ],
        right: ["The search box lists only what your role is allowed to open."],
        avoid: ["Shortcuts do nothing while you are typing in a box, so they never change what you write."],
      },
      {
        id: "no-access", title: "\"You don't have access to this page\"", who: "Everyone",
        steps: ["Your role does not allow this page. Ask an administrator to add the permission named on the screen to your role."],
      },
    ],
  },
  {
    id: "front-desk", title: "Front desk: customers, cars and check-in",
    intro: "Everything that happens before the mechanic touches the car.",
    sops: [
      {
        id: "customer-car", title: "Add a customer and a car", who: "Front desk",
        steps: [
          "Go to Customers and press Add customer.",
          "Type the name, choose Individual or Company, and type a mobile number. You can add the CNIC and address now or later.",
          "If the system shows a customer with the same phone number, open that customer. Only make a second record if it is really a different person, for example a family member who shares the phone.",
          "From the customer's page, add the car: number plate, make, model, year, fuel, colour, VIN or chassis number (one box for both), engine number and odometer.",
          "Tick \"Don't send WhatsApp messages\" if the customer does not want messages.",
        ],
        right: ["You can now find the customer and the car by name, plate, phone or chassis number."],
        avoid: ["Do not make a second record for the same car. One plate or VIN belongs to one car.", "Do not retype customer or car details on other screens. Use Edit on the Vehicle and people panel."],
      },
      {
        id: "check-in", title: "Check a car in", who: "Front desk",
        steps: [
          "Go to Cars in the workshop and press Check in a car. Find the car by plate, chassis number or owner's name.",
          "Look at the Vehicle and people panel. If anything is wrong, press Edit and fix it.",
          "Choose the visit type: Repair or service, or Pre-purchase inspection. For a pre-purchase inspection, also choose the buyer. The car's owner is the seller.",
          "Write what the customer says is wrong. Type the odometer reading and tap the fuel level.",
          "Take photos of all four sides and of any damage already on the car. Write down any valuables left inside.",
          "Ask the customer to sign on the screen. Press Check in.",
        ],
        right: ["A visit number (VIS-...) appears and the car shows under Cars in the workshop."],
        avoid: ["The odometer cannot be lower than the last reading. Check the number.", "A car that is already in the workshop cannot be checked in again. Open its visit instead."],
      },
      {
        id: "inspection", title: "Do and sign an inspection", who: "Inspector or mechanic",
        steps: [
          "On the visit, start an inspection. Choose Workshop (at check-in or during diagnosis), Delivery (before the car leaves) or Pre-purchase.",
          "Rate each check: G for good, A for average, NA for needs attention, NC for not checked. Add notes and photos where useful.",
          "Fill in the paint and tyre sections, the scan results, the battery checks (only for hybrid and electric cars), and the repairs you recommend with an estimated cost.",
          "Choose the overall condition and your recommendation. Press Sign. Signing locks the report.",
          "After signing, press Send to job card next to each repair the customer wants. The estimate becomes the first price on the quotation.",
        ],
        right: ["Anything you did not rate shows as Not checked. It never shows as Good.", "The signed report prints as an A4 page."],
        avoid: ["A signed report cannot be changed. Press Revise to make a new copy that replaces it."],
      },
      {
        id: "cancel-visit", title: "Cancel a visit", who: "Front desk or administrator",
        steps: ["Open the visit and press Cancel visit. Write the reason."],
        avoid: ["You cannot cancel once money was taken, parts were issued, or an invoice was issued. Reverse those first."],
      },
    ],
  },
  {
    id: "workshop", title: "Workshop: job card, quotation and repair",
    intro: "From the list of work to the finished repair.",
    sops: [
      {
        id: "job-card", title: "Write the job card", who: "Service advisor",
        steps: [
          "On the visit, press Start the job card. You can also send repairs from a signed inspection.",
          "Add each job by typing its name or code. For a part, you can scan its barcode. You can only add labour codes and parts that are already in the system.",
          "Set the quantity. Add a note if needed. A red stock number means there is not enough in stock. You can still make the quotation.",
          "Press Make the quotation.",
        ],
        avoid: ["You cannot type a free-text job. If a labour code or a part is missing, add it first under Labour codes or Inventory."],
      },
      {
        id: "quotation", title: "Price and send a quotation", who: "Service advisor",
        steps: [
          "Open the quotation. Parts already have their sale price. Type a price on every labour line.",
          "Add a discount if you agreed one. Keep the sales tax switch on unless the customer is exempt. Check the last valid date (7 days by default).",
          "Press Send. Every line must have a price.",
          "Print it, or press Send on WhatsApp on its print page. The quotation prints on one sheet, with the terms and conditions on a second page for the customer to sign. If WhatsApp is connected, the customer also gets an automatic message.",
        ],
        right: ["The status changes to Sent and the quotation is locked."],
        avoid: ["A sent quotation cannot be edited. Press Revise to make revision 2. It needs its own approval."],
      },
      {
        id: "approval", title: "Record the customer's approval", who: "Service advisor",
        steps: [
          "On the sent quotation, press Record approval. Choose how the customer agreed: in person, WhatsApp reply, or phone call.",
          "Attach proof: a photo, a screenshot of the WhatsApp reply, or a PDF. If there is none, write the reason, for example \"approved by phone at 3 pm\".",
          "If the customer refused some lines, untick them. At least one line must stay approved.",
          "If the customer refuses everything, press Customer said no and write the reason.",
        ],
        right: ["The status shows Approved, with your name and the time."],
        avoid: ["Do not start the repair on a spoken \"OK\" that you have not recorded."],
      },
      {
        id: "advance", title: "Take an advance", who: "Cashier",
        steps: [
          "On a Sent or Approved quotation, press Take an advance.",
          "Type the amount. Choose Cash, Bank transfer or Mobile wallet.",
          "Attach proof, or write the reason. For bank or wallet, also type the transaction number or attach the screenshot.",
          "Give the customer the receipt (it starts with PAY-).",
        ],
        right: ["The advance is kept for the customer. It is taken off the invoice automatically when the invoice is issued."],
        avoid: ["You cannot cancel a visit that holds money. To give an advance back, an administrator presses Give back on the quotation."],
      },
      {
        id: "repair-order", title: "Run the repair order", who: "Service advisor and mechanics",
        steps: [
          "On the approved quotation, press Make the repair order. Only the approved lines come across.",
          "Move the job forward as work progresses: Received → In repair → Testing → Ready. Put on hold from any stage if you are waiting.",
          "Issue parts and mark work Done while In repair. You cannot move to Testing until every line is Done or Not done. In Testing you can still update marks; you cannot move to Ready until every line is Done or Not done. Ready locks marks but still lets you return unused parts.",
          "Press Issue on each part line to take the part out of stock.",
          "Choose the mechanic on each line. Mark the line Done or Not done when finished.",
          "Write notes in the activity list: a Note, a Finding, or a Customer update (the customer can see this one).",
          "When all lines are finished, move the job to Ready. Every line must be marked Done or Not done first.",
        ],
        right: ["The activity list shows who did what, and when."],
        avoid: ["To move a job back a stage or put it On hold, you must write a note.", "If a part was not used, press Return unused so the stock stays correct."],
      },
      {
        id: "extra-work", title: "Add extra work found during the repair", who: "Service advisor",
        steps: [
          "On the repair order, use the Extra work found during the repair box. Choose the labour code or part. Type the price and the reason.",
          "Record how the customer agreed: in person, WhatsApp or phone. Attach proof, or write the reason.",
          "The line is marked Not in the quotation and appears on the invoice with the approval details.",
        ],
        avoid: ["Do not add extra work before the customer agrees. Call the customer first, then record it."],
      },
    ],
  },
  {
    id: "billing", title: "Billing and releasing the car",
    intro: "Turn finished work into money, and let the car leave only when everything is in order.",
    sops: [
      {
        id: "invoice", title: "Make and issue an invoice", who: "Billing clerk",
        steps: [
          "On a repair order that is Ready, press Make the invoice. The jobs marked Done and the parts really used come across.",
          "Check the prices, the discount and the tax switch.",
          "If the screen says the repair order changed, press Refresh from the repair order. Prices you edited are kept.",
          "Press Issue. Prices are now locked, and any advance is taken off automatically.",
          "Press Take a payment. Type the amount, choose the account, attach proof or write the reason. Repeat for each part payment.",
        ],
        right: ["The invoice shows Paid when nothing is left to pay."],
        avoid: ["An issued invoice cannot be edited. Use Return or correct to make a credit note.", "You can cancel (void) a draft invoice with a reason. Its number stays on record."],
      },
      {
        id: "counter-sale", title: "Sell parts over the counter", who: "Counter staff",
        steps: [
          "Go to Invoices and counter sales and press New counter sale.",
          "Choose Walk-in, or pick a customer. You can also pick one of their cars.",
          "Scan or search each part. Check the price and the stock. Counter sales are for parts only. Labour goes through a visit.",
          "Add a discount if agreed. Choose how the customer pays. If they pay part cash and part transfer, press Split the payment. The payments must add up to the total.",
          "Attach proof or a reason for each payment. Press Take Rs ... and finish. Print the A4 invoice.",
        ],
        right: ["Stock, invoice and payment are all saved together. If anything fails, nothing is saved."],
      },
      {
        id: "gate-pass", title: "Let the car leave (gate pass)", who: "Front desk or cashier",
        steps: [
          "Open the visit and look at the Gate pass box. It lists anything that stops the car from leaving.",
          "Fix each item on the list. The invoice must be issued and fully paid.",
          "Type the odometer at exit and the name of the person collecting the car. Press Release the car.",
          "Print the gate pass and give it to the gate. Ask the customer to sign it.",
        ],
        right: ["The visit closes and the repair order shows Delivered."],
        avoid: ["A car with an unpaid balance can leave only if someone with the release-on-credit permission writes a reason. Their name is recorded.", "The exit odometer cannot be lower than the check-in reading."],
      },
      {
        id: "credit-note", title: "Returns, corrections and refunds", who: "Accountant or manager (credit-notes permission)",
        steps: [
          "Open the issued invoice and press Return or correct.",
          "Tick the lines that came back and type how many. You can return part of a line. Write the reason.",
          "Tick Put it back in stock for parts that go back on the shelf.",
          "If the customer had already paid, the invoice shows Owed back to the customer. Press Give money back, choose the account, and attach proof or a reason.",
        ],
        right: ["The invoice shows Credited (returns) and the new balance. The refund shows on the Money out page."],
        avoid: ["You cannot return more than was invoiced."],
      },
      {
        id: "advance-refund", title: "Give back an unused advance", who: "Administrator (advance-refund permission)",
        steps: ["On the quotation, press Give back next to the advance. Write the reason, choose the account and attach proof. Change the amount to give back part of it; the rest stays held for the customer."],
      },
    ],
  },
  {
    id: "stock", title: "Stock and buying",
    intro: "Parts come in only through a purchase order and a goods receipt, so you can always see what each part cost and when it arrived.",
    sops: [
      {
        id: "new-item", title: "Add a part to inventory", who: "Inventory manager",
        steps: [
          "Go to Inventory and press Add item.",
          "Type the name, brand, category, unit, shelf, sale price, and the reorder level (how much to order is decided later, on the purchase order). Pick the brand and category from the lists. If yours is missing, choose "+ Add a new one to the list", type it and press Add to list: the spelling is checked (it may ask "Did you mean ...?") and the new name is then there for everyone. The same works for car makes and labour categories. To fix a name or hide one, use Settings, Pick-lists. Add the vendors who supply it on the item page.",
          "Add every barcode and manufacturer part number, so scanning finds the part.",
          "If you already hold stock, type the opening quantity and cost once, when you start.",
        ],
        avoid: ["You cannot type a stock quantity directly. To fix a wrong count, use an adjustment."],
      },
      {
        id: "adjust-stock", title: "Fix stock after a count", who: "Inventory manager (stock-adjust permission)",
        steps: ["Open the part and press Adjust. Type how many you found or lost. Write the reason (required).", "Check the movement list on the part. It shows who made the change and why."],
        right: ["The stock value in the books changes by the same amount."],
      },
      {
        id: "vendor", title: "Add a vendor", who: "Purchasing",
        steps: ["Go to Purchasing, then Vendors, and press Add vendor. Type the name, contact person, phone, and the days allowed to pay a bill. That sets each bill's due date."],
        avoid: ["A vendor name can only be used once."],
      },
      {
        id: "po", title: "Order from a vendor", who: "Purchasing (purchasing permission)",
        steps: [
          "Go to Purchasing, then Purchase orders, and press New purchase order. Choose the vendor.",
          "Add parts from Inventory by typing or scanning. Type the quantity and the agreed cost for each. Choose the vendor first. To fill the list quickly, press Add everything below its reorder level: only that vendor's items (and items with no vendor set) are added, with a suggested quantity you can change.",
          "Add the expected date and notes. Press Send. Print it, or press Send on WhatsApp.",
        ],
        avoid: ["A sent order cannot be changed. Cancel it and make a new one."],
      },
      {
        id: "grn", title: "Receive goods", who: "Storekeeper (goods-receipt permission)",
        steps: [
          "Open the sent order and press Count the goods in.",
          "Change Arrived to the number you really counted. Change the cost if the vendor charged a different price. Type the delivery note number.",
          "Check the average cost and margin shown. Add a new sale price if needed. Confirm.",
        ],
        right: ["Stock goes up, the average cost is updated, and the order shows Part received or Received."],
        avoid: ["You cannot receive more than is still expected. You cannot undo a confirmed receipt from this screen.", "The person who receives goods should not be the one who pays the bill."],
      },
      {
        id: "bill", title: "Record the vendor's bill", who: "Purchasing (purchasing permission)",
        steps: [
          "Under the delivery on the order, press Record the vendor's bill.",
          "Type the bill date and the vendor's invoice number. If there is freight (add) or a discount (subtract), enter it as an adjustment with a reason.",
        ],
        avoid: ["The same vendor invoice number cannot be entered twice.", "You can cancel a bill only while nothing has been paid on it."],
      },
      {
        id: "pay-vendor", title: "Pay a vendor", who: "Accountant (payments-out permission)",
        steps: [
          "Go to Purchasing, then Bills and payments. Open the bill and press Pay this bill.",
          "Type the amount. You can pay part of the bill. Choose the account, type the reference, and attach proof or a reason.",
        ],
        right: ["The bill shows what is still owed. The payment shows on the Money out page."],
        avoid: ["You cannot pay more than is owed. A wrong payment is cancelled (voided) with a reason, not edited."],
      },
    ],
  },
  {
    id: "money", title: "Money: in, out, proof and the daily close",
    intro: "Every rupee that comes in or goes out is recorded once, with proof, and counted at the end of the day.",
    sops: [
      {
        id: "money-in", title: "Record money received (not from an invoice)", who: "Cashier (payments-in permission)",
        steps: [
          "Go to Money, then Money in, and press Record money in. Choose the kind: Other income (scrap, rent, commission), Owner capital, or Transfer between accounts.",
          "Type the amount, the account it went into, who it came from, and the date.",
          "Attach proof or write the reason. For bank or wallet money, also type the reference or attach the screenshot.",
        ],
        right: ["It shows in the list and in the totals for each account. A transfer is not counted as income."],
      },
      {
        id: "expense", title: "Record an expense or owner drawing", who: "Accountant (expenses or payments-out permission)",
        steps: [
          "Go to Money, then Money out, and press Record money out. Choose Expense, Owner drawings or Transfer.",
          "For an expense, choose the category (tea, fuel, rent, electricity and so on), the account it was paid from, the amount and the date.",
          "Attach the receipt photo, or write why there is none.",
        ],
        avoid: ["A retired category cannot be chosen. Ask an administrator to add a new one under Money settings."],
      },
      {
        id: "void-money", title: "Fix a wrong money record", who: "The person who made it, or the accountant",
        steps: ["Open the record in Money in or Money out and press Void. Write the reason.", "Record the correct entry again."],
        right: ["The wrong record stays on the list, crossed out, and the books are corrected."],
        avoid: ["You cannot change a day that is already closed. Record the correction today."],
      },
      {
        id: "missing-proof", title: "Check records that have no proof", who: "Administrator (evidence-signoff permission); anyone on Money can optionally add proof later",
        steps: [
          "Go to Money, then Missing proof. Read the reason given for each record.",
          "If the reason is acceptable, press Accept and type why. If not, ask the person to bring proof.",
          "Optional: if the photo or document turns up later, press Add proof and upload it. You do not have to — Accept still clears the wait.",
        ],
        right: ["Accepted records no longer count as waiting, and they no longer stop the month from closing.", "A record with proof attached later leaves the list."],
      },
      {
        id: "cash-close", title: "Close the day (count the money)", who: "Accountant (cash-close permission). Every evening.",
        steps: [
          "Go to Money, then Cash close. For each account, count what is really there: the cash drawer, the bank balance and the mobile wallet.",
          "Type the amount you counted. If it is different from what the system expects, the screen shows how much is over or short. You must write why.",
          "Press Sign. Close the accounts in order, one day at a time.",
        ],
        right: ["Any difference is recorded as Cash over and short. Tomorrow starts from the amount you counted."],
        avoid: ["Signing cannot be undone. It locks that day for that account. Record anything you missed today, not on the old date.", "Do not skip days. Days must be closed in order."],
      },
    ],
  },
  {
    id: "people", title: "People: attendance and salary",
    intro: "Attendance comes from the fingerprint or face machine. Salary is worked out from it.",
    sops: [
      {
        id: "employee", title: "Add an employee", who: "HR (hr permission)",
        steps: [
          "Go to People, then Employees, and press Add employee.",
          "Type the name, job title, phone, CNIC, monthly salary, shift start and end times, weekly days off (tick every day, more than one is fine), and the joining date. Phone numbers are written with the country code, for example +92 300 1234567. CNIC is required.",
          "Type the device number, which is the person's number on the attendance machine. Any punches already received for that number are linked automatically.",
          "If the person also uses the system, link their login.",
        ],
        avoid: ["A CNIC or a device number can belong to one employee only. When someone leaves, enter the leaving date. Do not delete them."],
      },
      {
        id: "device", title: "Connect an attendance machine", who: "Administrator or HR",
        steps: [
          "Go to People, then Attendance, then Devices. Register the machine by its serial number. If you want a password for it, create a secret. It is shown only once, so copy it now.",
          "In the machine's settings, type the workshop PC's address (for example http://<PC address>:8000), and the secret if you made one.",
          "Punch once on the machine. Check the punch appears under Attendance.",
        ],
        avoid: ["A machine that is not registered, or is switched off, is refused. Punches for a number nobody owns are kept under Unmatched. Give that number to the right employee."],
      },
      {
        id: "attendance", title: "Check and correct attendance", who: "HR",
        steps: [
          "Go to People, then Attendance, and look at the month. Each day shows one status: Present, Late (more than 15 minutes after shift start), Incomplete (only one punch), Absent, Off, Paid leave or Unpaid leave.",
          "If someone forgot or failed to punch, go to Attendance, choose the employee under Add or fix a day by hand, and press Add a missed punch (write a reason). To mark a whole day as worked (8 hours) or as leave, press Mark present or leave.",
          "For approved leave, add a leave mark (paid or unpaid) with a reason.",
          "Do this before you run salary.",
        ],
        avoid: ["A punch from the machine can never be removed. Fix it with a missed-punch entry or a leave mark."],
      },
      {
        id: "advance-salary", title: "Give a salary advance", who: "Payroll (payroll permission)",
        steps: ["Go to People, then Payroll and advances, then Advances. Choose the employee, type the amount, choose the account, and attach proof or a reason."],
        avoid: ["An employee cannot owe more than one month's salary in advances."],
      },
      {
        id: "payroll", title: "Run the monthly salary", who: "Payroll (payroll permission)",
        steps: [
          "When the month has ended and attendance is corrected, press Start a run for that month.",
          "Check each person's line. Pay is for the days worked. One day's pay is taken off for each absent day and each unpaid-leave day. Late days cost nothing. Add a bonus or another deduction with a reason. Check the advance being taken back.",
          "If you corrected attendance, press Refresh. Your adjustments are kept.",
          "Press Approve. The figures are now fixed.",
          "Pay each person: choose the account and attach proof or a reason. When everyone is paid, the run shows Paid. Print the payslips.",
        ],
        avoid: ["There is one run per month. A draft can be thrown away and started again. An approved run cannot be edited."],
      },
    ],
  },
  {
    id: "owner", title: "Owner and accountant: reports and month end",
    intro: "How to see how the business is doing, and how to close each month correctly.",
    sops: [
      {
        id: "dashboard", title: "Daily review", who: "Owner or manager",
        steps: [
          "Open the Dashboard. Start with Needs attention: payments with no proof, invoices unpaid for over 30 days, bills past their due date, low stock, and months not closed. Each line opens the screen that fixes it.",
          "Then read In the workshop (cars, quotations, repairs) and Money this month. Every tile opens the report behind it.",
        ],
        right: ["The goal is a dashboard that says Nothing needs attention."],
      },
      {
        id: "reports", title: "Use the reports", who: "Accountant or owner (reports-finance or reports-ops permission)",
        steps: [
          "Go to Reports, then Finance reports. Choose This month, Last month, This year, or your own dates.",
          "Pick a report: Profit and loss, Cash flow, Customers owe us, We owe vendors, Stock value, or Discounts and voids.",
          "Press Download for Excel to save it as a spreadsheet. The dates are in the web address, so you can share the link.",
          "The Workshop report shows cars, how many quotations were accepted, time spent in each stage, top jobs and parts, and cars that came back. The People report shows attendance, salary cost and advances.",
        ],
        right: ["Customers owe us, We owe vendors, and Stock value each match their figure in the books."],
      },
      {
        id: "month-end", title: "Close a month", who: "Accountant (period-close permission)",
        steps: [
          "Go to Reports, then Month end. Open the month that just finished.",
          "Work down the checklist. Each item that is not done has a Fix it link. Typical items: close earlier months, clear missing proof, count cash, bank and wallet on the last day, finish salary.",
          "When every required item is done, press Close this month.",
          "Print or share the Closing pack for the owner and the accountant.",
        ],
        right: ["Nothing can be recorded with a date inside a closed month."],
        avoid: ["Only an administrator can reopen a month, with a reason, and the latest month must be reopened first.", "To fix a mistake in a closed month, make the correction in the current month."],
      },
      {
        id: "year-end", title: "Close a year", who: "Accountant",
        steps: ["When the year has ended and every month with activity is closed, open the year on the Month end page and close it. The yearly pack adds a month-by-month profit table."],
      },
    ],
  },
  {
    id: "messages", title: "Customer WhatsApp messages",
    intro: "The system sends messages to customers by itself. Nothing is sent until the WhatsApp (Twilio) details are added to the server.",
    sops: [
      {
        id: "messages-queue", title: "Check and retry messages", who: "Front desk or manager (messages permission)",
        steps: [
          "Go to Customers, then Messages. Use the filter to see Waiting to send, Sent, Delivered, Read, Failed or Not sent.",
          "For a Failed message, read the reason and press Try again.",
          "If a notice says WhatsApp is not connected, messages wait here. Ask the administrator to add the Twilio details.",
        ],
        right: ["A message marked Not sent shows why: no phone number, or the customer opted out."],
      },
      {
        id: "reminders", title: "Send due reminders", who: "Front desk or manager",
        steps: [
          "Once a day, press Queue due reminders. It adds payment reminders (3, 7 and 15 days after the invoice), service reminders, and welcome messages.",
          "Each reminder is added only once, so pressing the button twice is safe.",
        ],
      },
      {
        id: "wording", title: "Change the wording or the reminder days", who: "Administrator",
        steps: [
          "Go to Administration, then Message wording. Edit a message. Keep the words in curly brackets, such as {name} and {number}. They are filled in automatically. To stop a message, untick Send this message.",
          "Type the reminder days (for example 3,7,15) and the service interval. Press Save.",
        ],
      },
    ],
  },
  {
    id: "admin", title: "Administration",
    intro: "Set-up and safety.",
    sops: [
      {
        id: "users-roles", title: "Add a user and choose their role", who: "Administrator (users permission)",
        steps: [
          "Go to Administration, then Users, and press Add user. Type the username, full name, phone, a first password, and choose the role and branches.",
          "To make a new kind of role, such as front desk, mechanic or cashier, go to Roles and permissions and tick only what that person needs.",
          "To stop someone using the system, make the user inactive. Do not delete them. Their history stays.",
        ],
        avoid: ["Give each person only the permissions they need. Keep duties apart: the person who receives goods should not pay the bill, and the person who records money should not close the day."],
      },
      {
        id: "settings", title: "Branch and money settings", who: "Administrator (settings permission)",
        steps: [
          "Branch settings: the workshop's name, address, phone and sales tax rate, and the terms and conditions printed on every quotation (one clause per line; clear the box and save to go back to the standard terms).",
          "Money settings: the opening balance and date of the cash, bank and wallet accounts (what was there when you started), and the list of expense categories.",
        ],
        avoid: ["Set the opening balances once, at the start. Changing them later creates a reversal and a new entry."],
      },
      {
        id: "audit", title: "Read the audit log", who: "Administrator (audit permission)",
        steps: ["Go to Administration, then Audit log. Use the filter to choose what to see. Each line shows who did it, when, and the old and new value of everything that changed."],
        right: ["Entries in the audit log cannot be edited or deleted."],
      },
      {
        id: "backups", title: "Backups", who: "Administrator, or whoever looks after the workshop PC",
        steps: [
          "Make sure the nightly backup is scheduled on the server. The runbook explains how.",
          "Every week, copy the backups folder to a USB drive or to cloud storage kept away from the PC.",
          "Once, test a restore on a spare PC, so the first time is not an emergency.",
        ],
        avoid: ["A backup kept only on the same computer is lost if that computer's disk fails."],
      },
      {
        id: "sync", title: "Cloud sync and conflicts", who: "Administrator (sync permission)",
        steps: [
          "Go to Administration, then Cloud sync. It shows what is waiting to be sent, when it last sent and received, and any error. Press Sync now to run it immediately.",
          "If conflicts are waiting, press Review conflicts. For each one, compare This server and Other server. Press Keep this server's or Take the other server's.",
        ],
        right: ["An error loses nothing. Changes wait and are sent later."],
      },
    ],
  },
  {
    id: "trouble", title: "When something goes wrong",
    intro: "Messages you may see, what they mean, and what to do.",
    sops: [
      {
        id: "t-changed", title: "\"Changed on another device. Reload to continue.\"", who: "Anyone",
        steps: ["Someone else saved this record first. Reload the page, look at the new version, and make your change again."],
      },
      {
        id: "t-locked", title: "A closed month or a locked day", who: "Anyone",
        steps: ["The day was counted and signed, or the month was closed. Record the entry with today's date. Only an administrator can reopen a month, and must give a reason."],
      },
      {
        id: "t-stock", title: "Not enough stock", who: "Storekeeper",
        steps: ["Look at the part's movement list. If goods arrived but were not received, receive them on the purchase order. If a count was wrong, make an adjustment with a reason."],
      },
      {
        id: "t-proof", title: "\"Proof or a reason is needed\"", who: "Anyone",
        steps: ["Attach the photo, screenshot or PDF. If there is none, write the reason. For bank or wallet money, type the transaction number too."],
      },
      {
        id: "t-gate", title: "The gate pass will not release the car", who: "Front desk",
        steps: ["Read the list in the Gate pass box: repair order not Ready, invoice not issued or not paid, or an advance still held. Fix each one. If there is an unpaid balance, only a person with the release-on-credit permission can release the car, and must write a reason."],
      },
      {
        id: "t-refresh", title: "The invoice will not issue because the repair order changed", who: "Billing clerk",
        steps: ["Press Refresh from the repair order. Check the lines. Press Issue again."],
      },
      {
        id: "t-down", title: "The system will not open", who: "Anyone, then the administrator",
        steps: [
          "Check the Wi-Fi and the address. Try another device.",
          "The administrator checks that the workshop PC is switched on and running, and restarts it if needed. If data looks wrong after a power cut, restore the last backup.",
          "The workshop keeps working without internet. Only cloud sync and WhatsApp need it, and they catch up later.",
        ],
      },
      {
        id: "t-print", title: "A document will not print or share", who: "Anyone",
        steps: ["Press Print or save as PDF, then send the saved file. If Share as PDF is not available on your computer, it saves the file to Downloads. Attach it in WhatsApp Web or email."],
      },
    ],
  },
  {
    id: "checklists", title: "Daily, weekly and monthly checklists",
    intro: "Tick these off to keep your records right.",
    sops: [
      {
        id: "c-daily", title: "Every day", who: "Front desk, cashier, accountant", checklist: true,
        steps: [
          "Morning: look at the Dashboard's Needs attention and at Cars in the workshop.",
          "During the day: record every payment and expense as it happens, with proof.",
          "Before a car leaves: the invoice is issued and paid, and the gate pass is printed.",
          "Evening: close the day (Cash close) for cash, bank and wallet. Check Messages for failures.",
        ],
      },
      {
        id: "c-weekly", title: "Every week", who: "Manager, accountant, administrator", checklist: true,
        steps: [
          "Clear Missing proof. Follow up overdue invoices and vendor bills. Order parts that are below their reorder level.",
          "Check attendance and correct it. Copy the backups folder off the PC.",
        ],
      },
      {
        id: "c-monthly", title: "Every month", who: "Payroll, accountant, owner", checklist: true,
        steps: [
          "Correct attendance, run salary, approve and pay.",
          "Count cash, bank and wallet on the last day. Work through the Month end checklist and close the month.",
          "Read the closing pack and the profit and loss report.",
        ],
      },
    ],
  },
];
