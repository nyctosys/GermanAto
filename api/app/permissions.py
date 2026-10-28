"""Permission strings (spec §5). Each one gates pages in the web app and the
matching API routes; the server is the only place they are enforced."""

PERMISSIONS: dict[str, str] = {
    "dashboard": "See the dashboard",
    "settings": "Edit branch settings (name, contact details, tax rate)",
    "users": "Manage users and roles",
    "audit": "Read the audit log",
    "attachments": "Upload and view proof files",
    # Later phases add their own here (visits, quotations, payments-in, ...).
}

DEFAULT_ROLES: dict[str, dict] = {
    "Admin": {"is_admin": True, "permissions": []},
    "Accountant": {"is_admin": False, "permissions": ["dashboard", "attachments", "audit"]},
    "Inventory manager": {"is_admin": False, "permissions": ["dashboard", "attachments"]},
}
