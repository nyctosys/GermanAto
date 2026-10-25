"""Additive foundation helpers: branch, money, audit, attachments, roles, soft delete."""

from app.foundation.attachments import save_evidence
from app.foundation.audit import audit_write
from app.foundation.branch import DEFAULT_BRANCH_ID, ensure_default_branch, for_branch, new_branch_id
from app.foundation.hooks import install_foundation_hooks
from app.foundation.idempotent import idempotent_create
from app.foundation.money import from_paisa, to_paisa, validate_paisa
from app.foundation.roles import (
    DEFAULT_ROLE_PERMISSIONS,
    PERMISSION_ROLES,
    VALID_ROLES,
    expand_allowed_roles,
)
from app.foundation.scope import assign_branch, get_active, scoped_query
from app.foundation.soft_delete import not_deleted, soft_delete
from app.foundation.validation import (
    normalize_cnic,
    normalize_pk_phone,
    normalize_reg_no,
    validate_money_fields,
)
from app.foundation.versioning import bump_version, check_version, extract_version

__all__ = [
    "DEFAULT_BRANCH_ID",
    "DEFAULT_ROLE_PERMISSIONS",
    "PERMISSION_ROLES",
    "VALID_ROLES",
    "assign_branch",
    "audit_write",
    "bump_version",
    "check_version",
    "ensure_default_branch",
    "expand_allowed_roles",
    "extract_version",
    "for_branch",
    "from_paisa",
    "get_active",
    "idempotent_create",
    "install_foundation_hooks",
    "new_branch_id",
    "normalize_cnic",
    "normalize_pk_phone",
    "normalize_reg_no",
    "not_deleted",
    "save_evidence",
    "scoped_query",
    "soft_delete",
    "to_paisa",
    "validate_money_fields",
    "validate_paisa",
]
