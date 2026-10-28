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
    # Later phases add their own here (expenses, hr, payroll, ...).
}

DEFAULT_ROLES: dict[str, dict] = {
    "Admin": {"is_admin": True, "permissions": []},
    "Accountant": {"is_admin": False, "permissions": ["dashboard", "attachments", "audit", "customers", "vendors", "payments-out"]},
    "Inventory manager": {"is_admin": False, "permissions": ["dashboard", "attachments", "inventory", "stock-adjust",
                                                            "labour-codes", "vendors", "purchasing", "goods-receipt"]},
}
