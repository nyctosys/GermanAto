"""Request-scoped foundation context (branch, actor, audit reason)."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any

current_branch_id: ContextVar[str | None] = ContextVar("germanato_branch_id", default=None)
current_user_obj: ContextVar[Any] = ContextVar("germanato_user", default=None)
current_reason: ContextVar[str | None] = ContextVar("germanato_reason", default=None)
include_deleted: ContextVar[bool] = ContextVar("germanato_include_deleted", default=False)
skip_branch_scope: ContextVar[bool] = ContextVar("germanato_skip_branch", default=False)
skip_audit: ContextVar[bool] = ContextVar("germanato_skip_audit", default=False)


def set_branch(branch_id: str | None) -> Token:
    return current_branch_id.set(branch_id)


def set_user(user) -> Token:
    return current_user_obj.set(user)


def set_reason(reason: str | None) -> Token:
    return current_reason.set(reason)


def get_branch() -> str | None:
    return current_branch_id.get()


def get_user():
    return current_user_obj.get()


def get_reason() -> str | None:
    return current_reason.get()
