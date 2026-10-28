"""First-run setup: the branch, the default roles and the first admin.

    uv run python -m app.seed --branch-name "GermanATO Lahore" --admin-username owner

The admin password is read from the ADMIN_PASSWORD environment variable or
asked for interactively; it is never a hard-coded default. Running it again
only adds what is missing.
"""

import argparse
import getpass
import os
import secrets

from sqlalchemy import select

import app.events  # noqa: F401
from app.auth import hash_password
from app.db import SessionLocal
from app.models import Branch, Role, RolePermission, User, UserBranch
from app.permissions import DEFAULT_ROLES


def seed(branch_name: str, admin_username: str, admin_password: str, branch_code: str | None = None) -> None:
    with SessionLocal() as db:
        branch = db.scalar(select(Branch).order_by(Branch.created_at))
        if not branch:
            branch = Branch(code=(branch_code or secrets.token_hex(2)).upper(), name=branch_name)
            db.add(branch)
            print(f"Created branch {branch.name} ({branch.code})")

        roles = {r.name: r for r in db.scalars(select(Role))}
        for name, spec in DEFAULT_ROLES.items():
            if name not in roles:
                roles[name] = Role(name=name, is_admin=spec["is_admin"],
                                   permissions=[RolePermission(permission=p) for p in spec["permissions"]])
                db.add(roles[name])
                print(f"Created role {name}")
        db.flush()

        if not db.scalar(select(User).where(User.username == admin_username)):
            if len(admin_password) < 8:
                raise SystemExit("The admin password must be at least 8 characters")
            db.add(User(username=admin_username, full_name="Administrator", password_hash=hash_password(admin_password),
                        role_id=roles["Admin"].id, branches=[UserBranch(branch_id=branch.id)]))
            print(f"Created admin user {admin_username}")
        db.commit()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--branch-name", default="GermanATO")
    ap.add_argument("--branch-code", help="4 hex characters; random if omitted")
    ap.add_argument("--admin-username", default="admin")
    args = ap.parse_args()
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password for the admin user: ")
    seed(args.branch_name, args.admin_username.lower(), password, args.branch_code)
