"""Additive foundation helpers: branch, money, audit, attachments, roles, soft delete."""

from app.foundation.attachments import save_evidence
from app.foundation.audit import audit_write
from app.foundation.branch import DEFAULT_BRANCH_ID, ensure_default_branch, for_branch, new_branch_id
from app.foundation.hooks import install_foundation_hooks
from app.foundation.idempotent import idempotent_create
from app.foundation.money import from_paisa, to_paisa, validate_paisa
from app.foundation.overrides import (
    assert_discount_override,
    assert_payment_gate_override,
    require_audit_reason,
    require_override,
    user_has_permission,
)
from app.foundation.roles import (
    ADMIN_PERMISSIONS,
    DEFAULT_ROLE_PERMISSIONS,
    GRANULAR_PERMISSIONS,
    PERMISSION_ROLES,
    VALID_ROLES,
    expand_allowed_roles,
)
from app.foundation.scope import assign_branch, get_active, scoped_query
from app.foundation.settings import (
    ensure_default_settings,
    get_setting,
    get_workshop_settings,
    set_setting,
)
from app.foundation.soft_delete import not_deleted, soft_delete
from app.foundation.validation import (
    normalize_cnic,
    normalize_pk_phone,
    normalize_reg_no,
    validate_money_fields,
)
from app.foundation.versioning import bump_version, check_version, extract_version

__all__ = [
    "ADMIN_PERMISSIONS",
    "DEFAULT_BRANCH_ID",
    "DEFAULT_ROLE_PERMISSIONS",
    "GRANULAR_PERMISSIONS",
    "PERMISSION_ROLES",
    "VALID_ROLES",
    "assert_discount_override",
    "assert_payment_gate_override",
    "assign_branch",
    "audit_write",
    "bump_version",
    "check_version",
    "ensure_default_branch",
    "ensure_default_settings",
    "expand_allowed_roles",
    "extract_version",
    "for_branch",
    "from_paisa",
    "get_active",
    "get_setting",
    "get_workshop_settings",
    "idempotent_create",
    "install_foundation_hooks",
    "new_branch_id",
    "normalize_cnic",
    "normalize_pk_phone",
    "normalize_reg_no",
    "not_deleted",
    "require_audit_reason",
    "require_override",
    "save_evidence",
    "scoped_query",
    "set_setting",
    "soft_delete",
    "to_paisa",
    "user_has_permission",
    "validate_money_fields",
    "validate_paisa",
]
