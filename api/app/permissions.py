"""Permission strings (spec §5). Each one gates pages in the web app and the
matching API routes; the server is the only place they are enforced."""

PERMISSIONS: dict[str, str] = {
    "dashboard": "See the dashboard",
    "settings": "Edit branch settings (name, contact details, tax rate)",
    "users": "Manage users and roles",
    "audit": "Read the audit log",
    "attachments": "Upload and view proof files",
    "customers": "See and edit customers and cars",
    "car-transfer": "Transfer a car to another owner",
    "labour-codes": "Add and edit labour codes",
    "inventory": "See stock and add or edit items",
    "stock-adjust": "Correct stock levels (opening stock, counts, write-offs)",
    "visits": "Check cars in and out, run inspections",
    "gate": "See the cars ready to leave and release them with a gate pass (guard)",
    "job-cards": "Write job cards",
    "quotations": "Price and send quotations, record approvals",
    "repair-orders": "Work repair orders and issue parts",
    "invoices": "Prepare invoices and counter sales",
    "invoice-issue": "Issue invoices (locks the prices)",
    "payments-in": "Record money received",
    "release-on-credit": "Let a car leave with an unpaid balance",
    "vendors": "Add and edit vendors, see what is owed to them",
    "purchasing": "Write and send purchase orders, record vendor bills",
    "goods-receipt": "Receive stock against a purchase order",
    "payments-out": "Pay vendors (money out)",
    "expenses": "Record daily and major expenses",
    "period-close": "Close a finished month, with its checklist",
    "period-approve": "Reopen a closed month (admin)",
    "reports-ops": "See operations reports",
    "messages": "See and retry customer messages, edit their wording and reminder days",
    "sync": "See sync status, run a sync, and settle sync conflicts (admin)",
    "hr": "Manage employees, attendance and attendance devices",
    "payroll": "Run payroll and give salary advances",
    "evidence-signoff": "Accept a money record that has no proof, with a reason (admin)",
    "cash-close": "Count and sign off the cash, bank and wallet at the end of the day",
    "credit-notes": "Issue credit notes for returns and corrections, and refund the customer",
    "advance-refund": "Give a held advance back to the customer (admin approval)",
    "reports-finance": "See the journal, trial balance and finance reports",
    # Later phases add their own here (expenses, hr, payroll, ...).
}

DEFAULT_ROLES: dict[str, dict] = {
    "Admin": {"is_admin": True, "permissions": []},
    # Each role holds exactly the permissions for its own part of the work, so the system hands a job from one person
    # to the next by itself (the Dashboard's "My work" shows each person what is waiting for them).
    "Manager": {"is_admin": False, "permissions": ["dashboard", "attachments", "customers", "visits", "job-cards", "quotations", "repair-orders", "invoices",
                                                   "labour-codes", "inventory", "messages", "reports-ops", "evidence-signoff"]},
    "Front desk": {"is_admin": False, "permissions": ["dashboard", "attachments", "customers", "visits", "job-cards", "quotations", "messages", "labour-codes"]},
    "Technician": {"is_admin": False, "permissions": ["dashboard", "attachments", "visits", "job-cards", "repair-orders"]},
    "Cashier": {"is_admin": False, "permissions": ["dashboard", "attachments", "customers", "invoices", "invoice-issue", "payments-in"]},
    "Guard": {"is_admin": False, "permissions": ["dashboard", "gate"]},
    "Accountant": {"is_admin": False, "permissions": ["dashboard", "attachments", "audit", "customers", "vendors", "payments-out", "expenses", "reports-finance", "cash-close", "hr", "payroll", "period-close", "reports-ops"]},
    "Inventory manager": {"is_admin": False, "permissions": ["dashboard", "attachments", "inventory", "stock-adjust",
                                                            "labour-codes", "vendors", "purchasing", "goods-receipt"]},
}
