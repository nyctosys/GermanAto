"""Canonical workshop roles and permission defaults.

Legacy names `admin` and `inventory_manager` remain valid.
Owner ≡ admin; Store Keeper ≡ inventory_manager.
"""

from __future__ import annotations

# Granular override permissions (foundation gap #8).
GRANULAR_PERMISSIONS = [
    "approve_discount",
    "override_payment_gate",
    "qc_signoff",
    "adjust_stock",
    "reopen_period",
    "approve_evidence_exception",
    "approve_po",
    "override_po_price",
    "override_assignment_conflict",
]

ADMIN_PERMISSIONS = [
    "home",
    "invoice",
    "search",
    "inventory",
    "car",
    "reports",
    "admin",
    "daily-expenses",
    "major-expenses",
    "vendors",
    "vendor-detail",
    "hr",
    "worker-detail",
    "repair-order",
    "repair-orders-management",
    "settings",
    "logs",
    *GRANULAR_PERMISSIONS,
]

VALID_ROLES = (
    "admin",  # Owner (legacy)
    "owner",
    "manager",
    "accountant",
    "service_advisor",
    "technician",
    "store_keeper",
    "inventory_manager",  # Store Keeper (legacy)
)

# Roles whose permission matrices are editable in Admin UI (not owner/admin).
PERMISSION_ROLES = (
    "manager",
    "accountant",
    "service_advisor",
    "technician",
    "store_keeper",
    "inventory_manager",
)

DEFAULT_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": ADMIN_PERMISSIONS,
    "owner": ADMIN_PERMISSIONS,
    "manager": [
        "home",
        "invoice",
        "search",
        "inventory",
        "car",
        "reports",
        "daily-expenses",
        "major-expenses",
        "vendors",
        "vendor-detail",
        "hr",
        "worker-detail",
        "repair-order",
        "repair-orders-management",
        "settings",
        "approve_discount",
        "override_payment_gate",
        "qc_signoff",
        "adjust_stock",
        "reopen_period",
        "approve_evidence_exception",
        "approve_po",
        "override_po_price",
        "override_assignment_conflict",
    ],
    "accountant": [
        "home",
        "invoice",
        "search",
        "car",
        "daily-expenses",
        "major-expenses",
        "vendors",
        "vendor-detail",
        "hr",
        "worker-detail",
        "repair-order",
        "repair-orders-management",
        "reports",
        "settings",
        "approve_discount",
        "approve_po",
        "override_po_price",
    ],
    "service_advisor": [
        "home",
        "invoice",
        "search",
        "car",
        "repair-order",
        "repair-orders-management",
        "qc_signoff",
        "override_assignment_conflict",
    ],
    "technician": [
        "home",
        "repair-order",
        "repair-orders-management",
        "car",
        "qc_signoff",
    ],
    "store_keeper": [
        "home",
        "inventory",
        "repair-order",
        "repair-orders-management",
        "vendors",
        "vendor-detail",
        "settings",
        "adjust_stock",
    ],
    "inventory_manager": [
        "home",
        "inventory",
        "repair-order",
        "repair-orders-management",
        "vendors",
        "vendor-detail",
        "settings",
        "adjust_stock",
    ],
}

# When a route lists legacy roles, also accept hierarchy peers.
_ROLE_EXPAND: dict[str, frozenset[str]] = {
    "admin": frozenset({"admin", "owner"}),
    "owner": frozenset({"admin", "owner"}),
    "accountant": frozenset({"accountant", "manager", "admin", "owner"}),
    "inventory_manager": frozenset(
        {"inventory_manager", "store_keeper", "manager", "admin", "owner"}
    ),
    "store_keeper": frozenset(
        {"store_keeper", "inventory_manager", "manager", "admin", "owner"}
    ),
    "manager": frozenset({"manager", "admin", "owner"}),
    "service_advisor": frozenset(
        {"service_advisor", "manager", "admin", "owner"}
    ),
    "technician": frozenset({"technician", "service_advisor", "manager", "admin", "owner"}),
}


def expand_allowed_roles(roles: set[str] | list[str] | tuple[str, ...]) -> set[str]:
    """Expand an allow-list so Owner/Manager cover legacy route guards."""
    allowed: set[str] = set()
    for role in roles:
        allowed |= _ROLE_EXPAND.get(role, frozenset({role}))
        # Anyone explicitly listed is allowed as themselves
        allowed.add(role)
    # If route allows admin, owner is enough; also let admin pass any list
    if allowed & {"admin", "owner"}:
        allowed |= {"admin", "owner"}
    return allowed


def normalize_role(role: str) -> str:
    if role == "owner":
        return "admin"
    if role == "store_keeper":
        return "store_keeper"
    return role
