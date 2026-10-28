// The user manual shown on the Help page. Plain data so it is easy to edit: one chapter has several
// procedures (SOPs); each says who does it, the steps, how to tell it was done right, and what to avoid.
// Keep it in step with docs/SYSTEM_GUIDE.md when a screen changes.

export type Sop = { id: string; title: string; who: string; steps: string[]; right?: string[]; avoid?: string[] };
export type Chapter = { id: string; title: string; intro: string; sops: Sop[] };

export const RULES: string[] = [
  "Record everything in the system the moment it happens: the cash, the part, the approval. If it is not recorded, it did not happen.",
  "Every money record needs proof (photo, screenshot or PDF) or a written reason. A bank or wallet payment also needs its transaction reference.",
  "One customer and one car record is used everywhere. Fix a wrong detail on the record itself (Edit), never by typing it again somewhere else.",
  "Stock is never typed in. It changes only through receiving goods, issuing parts on a repair order, returns, counter sales and counted adjustments.",
  "Prices are set per quotation line. Labour codes have no price of their own.",
  "Nothing issued or signed is edited. Fix mistakes with a revision, a credit note, a void with a reason, or a correcting entry in the current month.",
  "Two people can work at once. If the screen says it was changed on another device, reload and redo your change.",
  "Close the day (cash count) every evening and the month every month. Closed days and months cannot be changed.",
];

export const CHAPTERS: Chapter[] = [
  {
    id: "start", title: "Start here",
    intro: "How to sign in, find your way around and read what the screens are telling you.",
    sops: [
      {
        id: "sign-in", title: "Signing in and out", who: "Everyone",
        steps: [
          "Open the workshop address in your browser (the address your administrator gave you, usually http://<server PC>:3000).",
          "Enter your username and password and press Sign in.",
          "If you work at more than one branch, choose the branch from the menu at the top. Everything you see and record belongs to that branch.",
          "When you finish, sign out from the menu, especially on a shared PC or tablet.",
        ],
        right: ["Your name is shown in the menu. The menu lists only what your role allows."],
        avoid: ["Do not share your password. Every record carries the name of the person who made it.", "Five wrong passwords lock the account for 15 minutes; ask an administrator if you are locked out."],
      },
      {
        id: "read-screens", title: "Reading the screens", who: "Everyone",
        steps: [
          "The menu on the left (the three-line button on a phone) is grouped: Workshop, Stock and services, Purchasing, Money, People, Reports, Customers, Administration, Help.",
          "A filled button does something. Underlined text opens another page. A row with an arrow on the right opens that record.",
          "Red text and notices mean something is wrong or missing. Amber means be careful. Read them: they say what to do.",
          "Every list has a search box. Scan a barcode into any item search and it finds the part.",
          "Printable documents (invoice, quotation, inspection, gate pass, purchase order, payslip) have a bar at the top: Back, Print or save as PDF, Share as PDF, and Send on WhatsApp.",
        ],
        right: ["You can always get back: every printed page has a Back link to the screen it came from."],
      },
      {
        id: "no-access", title: "\"You don't have access to this page\"", who: "Everyone",
        steps: ["Your role does not include that permission. Ask an administrator to add the permission named on the screen to your role (Administration, Roles and permissions)."],
      },
    ],
  },
  {
    id: "front-desk", title: "Front desk: customers, cars and check-in",
    intro: "Everything that happens before the technician touches the car.",
    sops: [
      {
        id: "customer-car", title: "Adding a customer and a car", who: "Front desk",
        steps: [
          "Customers, then Add customer. Enter the name, type (individual or company) and a mobile number. Phone, CNIC and address can be added now or later.",
          "If the system shows an existing customer with the same phone, open that record. Make a second record only if it really is someone else (for example, family sharing a phone).",
          "From the customer's page, add the car: number plate, make, model, year, fuel, colour, VIN or chassis number (one field), engine number and odometer.",
          "Tick \"Don't send WhatsApp messages\" if the customer asks not to be messaged.",
        ],
        right: ["The customer and car appear in search by name, plate, phone and VIN or chassis number."],
        avoid: ["Do not create a second record for the same car. A plate or VIN can belong to one car only.", "Do not type customer or car details again on other screens; use Edit on the Vehicle and people panel."],
      },
      {
        id: "check-in", title: "Checking a car in", who: "Front desk",
        steps: [
          "Cars in the workshop, then Check in a car. Find the car by plate, VIN or owner.",
          "Check the Vehicle and people panel and correct anything wrong with Edit.",
          "Choose the visit type: Repair or service, or Pre-purchase inspection (then choose the buyer; the owner is the seller).",
          "Write what the customer says is wrong. Enter the odometer and tap the fuel gauge.",
          "Take photos of all four sides and of existing damage. Record valuables left in the car.",
          "Have the customer sign on the screen, then press Check in.",
        ],
        right: ["The visit number (VIS-…) appears and the car shows under Cars in the workshop."],
        avoid: ["The odometer cannot be lower than the last reading on file; check the number rather than forcing it.", "A car already in the workshop cannot be checked in again; open its visit."],
      },
      {
        id: "inspection", title: "Doing and signing an inspection", who: "Inspector or technician",
        steps: [
          "On the visit, start an inspection: Workshop (at check-in or diagnosis), Delivery (before the car leaves) or Pre-purchase.",
          "Rate each check G (good), A (average), NA (needs attention) or NC (not checked). Add notes and photos where useful.",
          "Fill in the paint and tyre sections, scan results, the hybrid or EV battery checks (shown only for those cars) and the recommended repairs with an estimated cost.",
          "Set the overall condition and recommendation, then Sign. Signing freezes the report.",
          "After signing, use Send to job card on each recommended repair that the customer wants. The estimate becomes the proposed price.",
        ],
        right: ["Unrated checks show as Not checked, never as Good.", "The signed report prints as an A4 document."],
        avoid: ["A signed report cannot be edited. Use Revise to make a new draft that replaces it."],
      },
      {
        id: "cancel-visit", title: "Cancelling a visit", who: "Front desk or administrator",
        steps: ["Open the visit and choose Cancel visit. Enter the reason."],
        avoid: ["Not allowed once money has been taken, parts issued or an invoice issued. Refund or reverse those first."],
      },
    ],
  },
  {
    id: "workshop", title: "Workshop: job card, quotation and repair",
    intro: "From the list of work to the finished repair.",
    sops: [
      {
        id: "job-card", title: "Writing the job card", who: "Service advisor",
        steps: [
          "On the visit, Start the job card (or send repairs from a signed inspection).",
          "Add lines by typing a name or code, or by scanning a part's barcode. Only labour codes and stock items can be added.",
          "Set the quantity. Add a note where needed. A red stock figure means a shortage; you can still quote.",
          "Press Make the quotation.",
        ],
        avoid: ["There is no free-text line. If a labour code or part is missing, add it under Labour codes or Inventory first."],
      },
      {
        id: "quotation", title: "Pricing and sending a quotation", who: "Service advisor",
        steps: [
          "Open the quotation draft. Parts start at their sale price. Type a price on every labour line.",
          "Add a discount if agreed (it cannot exceed the lines). Keep the sales tax switch on unless the customer is exempt. Set the validity date (7 days by default).",
          "Press Send. Every line must have a price.",
          "Print it or use Send on WhatsApp from its print page. If WhatsApp messaging is connected, the customer also receives an automatic message.",
        ],
        right: ["Status changes to Sent. The quotation is locked."],
        avoid: ["A sent quotation cannot be edited. Use Revise to make revision 2 with the same lines; it needs its own approval."],
      },
      {
        id: "approval", title: "Recording the customer's approval", who: "Service advisor",
        steps: [
          "On the sent quotation choose Record approval and select how the customer agreed: in person, WhatsApp reply or phone call.",
          "Attach proof: a photo, a screenshot of the WhatsApp reply, or a PDF. If there truly is none, write the reason (for example \"approved on a phone call at 3 pm\").",
          "If the customer declined some lines, untick them. At least one line must stay approved.",
          "If they decline everything, press Customer said no and give the reason.",
        ],
        right: ["Status shows Approved with your name and the time."],
        avoid: ["Never start the repair on a verbal OK that is not recorded."],
      },
      {
        id: "advance", title: "Taking an advance", who: "Cashier",
        steps: [
          "On a Sent or Approved quotation, choose Take an advance.",
          "Enter the amount and choose Cash, Bank transfer or Mobile wallet.",
          "Attach proof (or write the reason). For bank or wallet, enter the transaction reference or attach the screenshot.",
          "Give the customer the receipt (PAY-…).",
        ],
        right: ["The advance is held as the customer's money and is used automatically when the invoice is issued."],
        avoid: ["A visit that holds money cannot be cancelled. Giving an advance back needs an administrator (Give back on the quotation)."],
      },
      {
        id: "repair-order", title: "Running the repair order", who: "Service advisor and technicians",
        steps: [
          "On the approved quotation press Make the repair order. Only the approved lines come across.",
          "Move the job through its stages as work progresses: Received, Diagnosis, Awaiting approval, In repair, Testing, Ready.",
          "Issue each part from stock on its line (Issue). The quantity leaves stock at its average cost.",
          "Choose the technician on each line and mark it Done or Not done when finished.",
          "Write notes in the activity: Note, Finding, or Customer update (customer can see).",
          "When everything is finished, move the job to Ready. Every line must be Done or Not done first.",
        ],
        right: ["The activity timeline shows who did what and when."],
        avoid: ["Moving back a stage or putting a job On hold needs a written note.", "Use Return unused for parts that were not fitted so stock and cost stay right."],
      },
      {
        id: "extra-work", title: "Extra work found during the repair", who: "Service advisor",
        steps: [
          "On the repair order, use the Extra work found during the repair panel: choose the labour code or part and enter the price and the reason.",
          "Record how the customer agreed (in person, WhatsApp or phone) with proof or a written reason.",
          "The line is flagged Not in the quotation and carries to the invoice with the approval details.",
        ],
        avoid: ["Do not add extra work before the customer has agreed. Phone the customer first and record it."],
      },
    ],
  },
  {
    id: "billing", title: "Billing and releasing the car",
    intro: "Turn finished work into money and let the car leave only when it is right.",
    sops: [
      {
        id: "invoice", title: "Invoicing a repair", who: "Billing clerk",
        steps: [
          "On a Ready repair order press Make the invoice. Labour marked Done and the parts actually issued come across.",
          "Review the prices, discount and tax switch in the draft.",
          "If the screen says the repair order changed, press Refresh from the repair order. Your edited prices stay.",
          "Press Issue. Prices lock and any advances held on the visit are applied.",
          "Press Take a payment: amount, account, proof or reason, reference for bank or wallet. Repeat for part payments.",
        ],
        right: ["The invoice shows Paid when the balance is zero."],
        avoid: ["An issued invoice is never edited. Use Return or correct (a credit note).", "A draft can be voided with a reason; its number stays on record."],
      },
      {
        id: "counter-sale", title: "Selling parts over the counter", who: "Counter staff",
        steps: [
          "Invoices and counter sales, then New counter sale.",
          "Choose Walk-in or a customer on file (optionally one of their cars).",
          "Scan or search each part. Check the stock and price. Parts only; labour goes through a visit.",
          "Set a discount if agreed. Choose how the customer pays; use Split the payment for part cash, part transfer. The payments must add up to the total.",
          "Attach proof or a reason for each payment, then press Take Rs … and finish. Print the A4 invoice.",
        ],
        right: ["Stock, invoice and payment are all recorded in one step. If anything fails, nothing is changed."],
      },
      {
        id: "gate-pass", title: "Releasing the car (gate pass)", who: "Front desk or cashier",
        steps: [
          "Open the visit and look at the Gate pass panel. It lists anything stopping the car: repair order not Ready, no issued invoice, an advance with no invoice.",
          "Fix each blocker. The invoice must be paid.",
          "Enter the odometer at exit and who collected the car. Press Release the car.",
          "Print the gate pass for the gate and get the customer's signature.",
        ],
        right: ["The visit closes and the repair order shows Delivered."],
        avoid: ["A car with an unpaid balance can leave only if someone with the release-on-credit permission gives a reason. It is recorded under their name.", "The exit odometer cannot be lower than at check-in."],
      },
      {
        id: "credit-note", title: "Returns, corrections and refunds", who: "Accountant or manager (credit-notes permission)",
        steps: [
          "Open the issued invoice and choose Return or correct.",
          "Select the lines and the quantity that came back (part of a line is allowed) and give a reason.",
          "Tick Put it back in stock for parts that return to the shelf.",
          "If the customer had already paid, the invoice shows Owed back to the customer. Press Give money back, choose the account, attach proof or a reason.",
        ],
        right: ["The invoice shows Credited (returns) and the new balance. The refund appears on Money out."],
        avoid: ["A line cannot be credited for more than was invoiced."],
      },
      {
        id: "advance-refund", title: "Giving back a held advance", who: "Administrator (advance-refund permission)",
        steps: ["On the quotation, press Give back next to the unused advance. Enter the reason, the account and the proof. The whole advance goes back."],
      },
    ],
  },
  {
    id: "stock", title: "Stock and purchasing",
    intro: "Parts come in only through a purchase order and a goods receipt, so every cost can be traced to a delivery.",
    sops: [
      {
        id: "new-item", title: "Adding an inventory item", who: "Inventory manager",
        steps: [
          "Inventory, then Add item. Enter the name, brand, category, unit, shelf location, sale price and reorder level and quantity.",
          "Add every barcode and manufacturer part number so a scan finds the item.",
          "If you hold stock already, enter the opening quantity and cost once, at the start.",
        ],
        avoid: ["Never edit a quantity directly; it cannot be typed. Use an adjustment for counts."],
      },
      {
        id: "adjust-stock", title: "Correcting stock after a count", who: "Inventory manager (stock-adjust permission)",
        steps: ["Open the item and choose Adjust. Enter the quantity found or lost and the reason (required).", "Check the movement list on the item: it shows who adjusted and why."],
        right: ["The inventory value in the books changes by the same amount."],
      },
      {
        id: "vendor", title: "Adding a vendor", who: "Purchasing",
        steps: ["Purchasing, Vendors, Add vendor. Enter the name, contact, phone and days to pay a bill (it sets each bill's due date)."],
        avoid: ["A vendor name cannot be used twice."],
      },
      {
        id: "po", title: "Ordering from a vendor", who: "Purchasing (purchasing permission)",
        steps: [
          "Purchasing, Purchase orders, New purchase order. Choose the vendor.",
          "Add items from Inventory (type or scan). Enter the quantity and the agreed cost each. Use Add everything below its reorder level to fill the list.",
          "Set the expected date and notes. Press Send. Print it or Send on WhatsApp.",
        ],
        avoid: ["A sent order cannot be edited. Cancel it and make a new one."],
      },
      {
        id: "grn", title: "Receiving goods", who: "Storekeeper (goods-receipt permission)",
        steps: [
          "Open the sent order and press Count the goods in.",
          "Change Arrived to what you actually counted and the cost each if the vendor charged differently. Record the delivery note number.",
          "Check the average cost and margin shown, add a new sale price if needed, then confirm.",
        ],
        right: ["Stock goes up, the average cost updates and the order shows Part received or Received."],
        avoid: ["You cannot receive more than is still expected. Confirming cannot be undone from this screen.", "The person who receives goods cannot pay the bill (separation of duties)."],
      },
      {
        id: "bill", title: "Recording the vendor's bill", who: "Purchasing (purchasing permission)",
        steps: [
          "Under the delivery on the order, press Record the vendor's bill.",
          "Enter the bill date and the vendor's invoice number. Add freight (plus) or a discount (minus) as an adjustment with a reason.",
        ],
        avoid: ["The same vendor invoice number cannot be entered twice.", "A bill can be voided only while nothing has been paid on it."],
      },
      {
        id: "pay-vendor", title: "Paying a vendor", who: "Accountant (payments-out permission)",
        steps: [
          "Purchasing, Bills and payments. Open the bill and press Pay this bill.",
          "Enter the amount (part payments are allowed), the account, the reference and the proof or reason.",
        ],
        right: ["The bill shows what is still owed. The payment appears on Money out."],
        avoid: ["You cannot pay more than is owed. A wrong payment is voided with a reason, not edited."],
      },
    ],
  },
  {
    id: "money", title: "Money: in, out, proof and the daily close",
    intro: "Every rupee in and out is recorded once, with proof, and counted at the end of each day.",
    sops: [
      {
        id: "money-in", title: "Recording money that is not an invoice payment", who: "Cashier (payments-in permission)",
        steps: [
          "Money, Money in, then Record money in. Choose the kind: Other income (scrap sale, rent, commission), Owner capital, or Transfer between accounts.",
          "Enter the amount, the account it went into, who it came from and the date.",
          "Attach proof or write the reason. Bank or wallet money needs the reference or screenshot.",
        ],
        right: ["It appears in the list and in the totals by account. A transfer is not counted as income."],
      },
      {
        id: "expense", title: "Recording an expense or owner drawing", who: "Accountant (expenses or payments-out permission)",
        steps: [
          "Money, Money out, then Record money out. Choose Expense, Owner drawings or Transfer.",
          "For an expense choose the category (tea, fuel, rent, electricity ...), the account it was paid from, the amount and the date.",
          "Attach the receipt photo or write why there is none.",
        ],
        avoid: ["A retired category cannot be chosen. Ask an administrator to add one under Money settings."],
      },
      {
        id: "void-money", title: "Fixing a wrong money record", who: "Whoever recorded it, or the accountant",
        steps: ["Open the record in Money in or Money out and choose Void. Enter the reason.", "Record the correct entry again."],
        right: ["The wrong record stays on the list, struck through, and the books are corrected."],
        avoid: ["Days already closed cannot be changed. Record the correction today."],
      },
      {
        id: "missing-proof", title: "Reviewing records without proof", who: "Administrator (evidence-signoff permission)",
        steps: [
          "Money, Missing proof. Read the reason given for each record.",
          "For each acceptable one press Accept and type why. Chase the rest for proof.",
        ],
        right: ["Accepted records stop counting as waiting and no longer block month end."],
      },
      {
        id: "cash-close", title: "Closing the day (cash, bank and wallet count)", who: "Accountant (cash-close permission), every evening",
        steps: [
          "Money, Cash close. For each account, count what is really there: the cash drawer, the bank balance, the mobile wallet.",
          "Type the counted amount. If it differs from what the books expect, the screen shows over or short and you must say why.",
          "Sign. Do the accounts in order, one day at a time.",
        ],
        right: ["The difference is posted as Cash over and short, so tomorrow starts from what you counted."],
        avoid: ["Signing is final and locks that day for that account. Record anything missed today, not backdated.", "Do not skip days; days close in order."],
      },
    ],
  },
  {
    id: "people", title: "People: attendance and payroll",
    intro: "Attendance comes from the fingerprint or face terminal. Payroll reads it.",
    sops: [
      {
        id: "employee", title: "Adding an employee", who: "HR (hr permission)",
        steps: [
          "People, Employees, Add employee. Enter the name, job title, phone, CNIC, monthly salary, shift start and end, weekly day off and joining date.",
          "Enter the device number: the person's number on the terminal. Existing punches for that number are claimed automatically.",
          "Link a login if the employee also uses the system.",
        ],
        avoid: ["A CNIC or a device number cannot belong to two employees. When someone leaves, set the leaving date; do not delete."],
      },
      {
        id: "device", title: "Connecting a terminal", who: "Administrator or HR",
        steps: [
          "People, Attendance, Devices: register the terminal by its serial number. Optionally create a shared secret (shown once; copy it now).",
          "On the terminal, set the server address to the workshop PC (for example http://<PC address>:8000) with the secret if used. It pushes punches to /iclock/cdata.",
          "Punch once and check the punch appears under Attendance.",
        ],
        avoid: ["An unregistered or switched-off terminal is refused. Punches for a number nobody owns are kept under Unmatched; give that number to the right employee."],
      },
      {
        id: "attendance", title: "Checking and correcting attendance", who: "HR",
        steps: [
          "People, Attendance: review the month. Status is worked out from punches: Present, Late (more than 15 minutes after shift start), Incomplete, Absent, Off, Paid leave, Unpaid leave.",
          "For a forgotten or failed scan use Add a missed punch with a reason (at least five characters).",
          "For approved leave add a leave mark (paid or unpaid) with a reason.",
          "Do this before running payroll.",
        ],
        avoid: ["A punch from the terminal can never be removed, only corrected with a missed-punch entry or leave mark."],
      },
      {
        id: "advance-salary", title: "Giving a salary advance", who: "Payroll (payroll permission)",
        steps: ["People, Payroll and advances, then Advances. Choose the employee, amount, account and proof or reason."],
        avoid: ["No more than one month's salary can be outstanding for a person."],
      },
      {
        id: "payroll", title: "Running monthly payroll", who: "Payroll (payroll permission)",
        steps: [
          "After the month ends and attendance is corrected, Start a run for that month.",
          "Check each line: pay for working days, deductions for absent and unpaid-leave days (late days cost nothing). Add a bonus or other deduction with a reason. Check the advance recovery.",
          "Use Refresh if attendance was corrected; your adjustments stay.",
          "Press Approve. The figures are fixed and the salary expense is booked.",
          "Pay each person (account, proof or reason). The run shows Paid when everyone is paid. Print the payslips.",
        ],
        avoid: ["One run per month. A draft can be thrown away and restarted; an approved run cannot be edited."],
      },
    ],
  },
  {
    id: "owner", title: "Owner and accountant: review, reports and month end",
    intro: "How to see how the business is doing and close each period correctly.",
    sops: [
      {
        id: "dashboard", title: "Daily review", who: "Owner or manager",
        steps: [
          "Open the Dashboard. Start with Needs attention: payments with no proof, invoices unpaid over 30 days, bills past due, low stock, months not closed. Each line opens the screen that fixes it.",
          "Read In the workshop (cars, open quotations, repairs) and Money this month. Every tile opens the report behind it.",
        ],
        right: ["The goal is a dashboard that says Nothing needs attention."],
      },
      {
        id: "reports", title: "Using the reports", who: "Accountant, owner (reports-finance or reports-ops permission)",
        steps: [
          "Reports, then Finance reports. Choose This month, Last month, This year or a custom range. Pick Profit and loss, Cash flow, Customers owe us, We owe vendors, Stock value, or Discounts and voids.",
          "Use Download for Excel to export. The range is in the address, so you can share the link.",
          "Workshop report: cars, conversion rate, time in each stage, top labour and parts, comebacks. People report: attendance, payroll cost, advances.",
        ],
        right: ["Customers owe us, We owe vendors and Stock value each equal their account in the books."],
      },
      {
        id: "month-end", title: "Closing a month", who: "Accountant (period-close permission)",
        steps: [
          "Reports, Month end. Open the month that just finished.",
          "Work down the checklist. Each item that is not done has a Fix it link: close earlier months, clear missing proof, count cash, bank and wallet on the last day, finish payroll.",
          "When every required item is done press Close this month.",
          "Print or share the Closing pack for the owner and the accountant.",
        ],
        right: ["Nothing can be recorded dated inside a closed month."],
        avoid: ["Reopening needs an administrator and a reason, and months reopen latest first.", "Correct mistakes in a closed month in the current month."],
      },
      {
        id: "year-end", title: "Closing a year", who: "Accountant",
        steps: ["Once the year has ended and every month with activity is closed, open the year on the Month end page and close it. The yearly pack adds a month-by-month profit table."],
      },
    ],
  },
  {
    id: "messages", title: "Customer WhatsApp messages",
    intro: "The system messages customers automatically. Nothing is sent until WhatsApp (Twilio) details are added to the server.",
    sops: [
      {
        id: "messages-queue", title: "Checking and retrying messages", who: "Front desk or manager (messages permission)",
        steps: [
          "Customers, Messages. Filter by status: Waiting to send, Sent, Delivered, Read, Failed, Not sent.",
          "For a Failed message read the reason and press Try again.",
          "If the notice says WhatsApp is not connected, messages wait here; ask the administrator to add the Twilio details.",
        ],
        right: ["Not sent shows why: no phone number, or the customer opted out."],
      },
      {
        id: "reminders", title: "Sending due reminders", who: "Front desk or manager",
        steps: [
          "Press Queue due reminders once a day (or let a daily job do it). It adds payment reminders at 3, 7 and 15 days, service reminders and welcome messages.",
          "Each reminder is queued only once, so pressing it twice is safe.",
        ],
      },
      {
        id: "wording", title: "Changing the wording or reminder days", who: "Administrator",
        steps: [
          "Administration, Message wording. Edit a message's text (keep the {fields} such as {name} and {number}) or switch it off with Send this message.",
          "Set the reminder days (for example 3,7,15) and the service interval, then Save.",
        ],
      },
    ],
  },
  {
    id: "admin", title: "Administration",
    intro: "Set-up, safety and the things that keep the data healthy.",
    sops: [
      {
        id: "users-roles", title: "Adding a user and choosing their role", who: "Administrator (users permission)",
        steps: [
          "Administration, Users, Add user. Enter the username, full name, phone, a first password and the role and branches.",
          "To make a new kind of role (front desk, technician, cashier) go to Roles and permissions and tick exactly what that person needs.",
          "To stop someone using the system, make the user inactive. Do not delete; their history stays.",
        ],
        avoid: ["Give the least permission that does the job. Separate duties: the person who receives goods should not pay the bill; the person who records money should not close the day."],
      },
      {
        id: "settings", title: "Branch and money settings", who: "Administrator (settings permission)",
        steps: [
          "Branch settings: name, address, phone, sales tax rate.",
          "Money settings: the opening balance and date of the cash, bank and wallet accounts (what was there when you started), and the expense categories.",
        ],
        avoid: ["Set opening balances once at the start. Changing later posts a reversal and a new entry."],
      },
      {
        id: "audit", title: "Reading the audit log", who: "Administrator (audit permission)",
        steps: ["Administration, Audit log. Filter by what happened. Each entry shows who, when, and the old and new value of every field that changed."],
        right: ["Entries cannot be edited or deleted."],
      },
      {
        id: "backups", title: "Backups", who: "Administrator or whoever looks after the workshop PC",
        steps: [
          "Make sure the nightly backup is scheduled on the server (see the runbook).",
          "Every week copy the backups folder to a USB drive or cloud storage kept away from the PC.",
          "Once, test a restore on a spare PC so the first time is not an emergency.",
        ],
        avoid: ["A backup only on the same disk does not survive a dead disk."],
      },
      {
        id: "sync", title: "Cloud sync and conflicts", who: "Administrator (sync permission)",
        steps: [
          "Administration, Cloud sync shows what is waiting to be sent, the last send and receive, and any error. Sync now runs it at once.",
          "If conflicts are waiting, open Review conflicts. For each, compare This server and Other server, then choose Keep this server's or Take the other server's.",
        ],
        right: ["An error does not lose anything; unsent changes wait and are retried."],
      },
    ],
  },
  {
    id: "trouble", title: "When something goes wrong",
    intro: "The messages you may see, what they mean and what to do.",
    sops: [
      {
        id: "t-changed", title: "\"Changed on another device. Reload to continue.\"", who: "Anyone",
        steps: ["Someone else saved this record first. Reload the page, look at the new version, and redo your change."],
      },
      {
        id: "t-locked", title: "\"Closed\" month or locked day", who: "Anyone",
        steps: ["The day was counted and signed, or the month closed. Record the entry dated today. Only an administrator can reopen a month, with a reason."],
      },
      {
        id: "t-stock", title: "Not enough stock", who: "Storekeeper",
        steps: ["Check the item's movements. If goods arrived but were not received, receive them against the purchase order. If a count was wrong, make an adjustment with a reason."],
      },
      {
        id: "t-proof", title: "\"Proof or a reason is needed\"", who: "Anyone",
        steps: ["Attach the photo, screenshot or PDF. If none exists, write the reason. For bank or wallet money enter the transaction reference."],
      },
      {
        id: "t-gate", title: "The gate pass will not release the car", who: "Front desk",
        steps: ["Read the blockers in the Gate pass panel: repair order not Ready, invoice not issued or not paid, or an advance still held. Fix each one. For an unpaid balance only a person with the release-on-credit permission can release, with a reason."],
      },
      {
        id: "t-refresh", title: "The invoice will not issue: repair order changed", who: "Billing clerk",
        steps: ["Press Refresh from the repair order, check the lines, then Issue again."],
      },
      {
        id: "t-down", title: "The system does not open", who: "Anyone, then the administrator",
        steps: [
          "Check the Wi-Fi and the address. Try another device.",
          "The administrator checks the workshop PC is on and running (docker compose ps) and restarts it if needed. If data looks wrong after a power cut, restore the last backup.",
          "The workshop works without internet. Only cloud sync and WhatsApp need it, and they catch up later.",
        ],
      },
      {
        id: "t-print", title: "A document will not print or share", who: "Anyone",
        steps: ["Use Print or save as PDF, then send the saved file. On a computer without share support, Share as PDF saves the file to Downloads; attach it in WhatsApp Web or email."],
      },
    ],
  },
  {
    id: "checklists", title: "Daily, weekly and monthly checklists",
    intro: "Tick these off to keep the records right.",
    sops: [
      {
        id: "c-daily", title: "Every day", who: "Front desk, cashier, accountant",
        steps: [
          "Morning: look at the Dashboard's Needs attention and Cars in the workshop.",
          "During the day: record every payment and expense as it happens, with proof.",
          "Before a car leaves: invoice issued and paid, gate pass printed.",
          "Evening: close the day (Cash close) for cash, bank and wallet; check Messages for failures.",
        ],
      },
      {
        id: "c-weekly", title: "Every week", who: "Manager, accountant, administrator",
        steps: [
          "Clear Missing proof. Chase overdue invoices and vendor bills. Order items below their reorder level.",
          "Review attendance for corrections. Copy the backups folder off the PC.",
        ],
      },
      {
        id: "c-monthly", title: "Every month", who: "Payroll, accountant, owner",
        steps: [
          "Correct attendance, run payroll, approve and pay.",
          "Count cash, bank and wallet on the last day. Work the Month end checklist and close the month.",
          "Read the closing pack and the profit and loss report.",
        ],
      },
    ],
  },
];
