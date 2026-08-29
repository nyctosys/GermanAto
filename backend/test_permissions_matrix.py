#!/usr/bin/env python3
import os
import sys
import logging

import werkzeug

werkzeug.__version__ = getattr(werkzeug, "__version__", "3")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test"

from app import app
from models import RolePermission, User, db

logging.getLogger("reports_routes").disabled = True
logging.getLogger("jwt_auth").disabled = True


def auth_header(client, username):
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": "pw"},
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    return {"Authorization": f"Bearer {response.get_json()['access_token']}"}


def seed():
    with app.app_context():
        db.drop_all()
        db.create_all()

        users = [
            User(username="admin", email="admin@example.com", role="admin"),
            User(username="acct", email="acct@example.com", role="accountant"),
            User(username="inv", email="inv@example.com", role="inventory_manager"),
        ]
        for user in users:
            user.set_password("pw")
        db.session.add_all(users)

        matrix = {
            "accountant": ["invoice", "vendors", "hr"],
            "inventory_manager": ["inventory", "vendors", "reports", "repair-order"],
        }
        for role, permissions in matrix.items():
            for permission in permissions:
                db.session.add(RolePermission(role=role, permission=permission))

        db.session.commit()


def main():
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite:///:memory:")
    seed()

    client = app.test_client()
    admin = auth_header(client, "admin")
    accountant = auth_header(client, "acct")
    inventory_manager = auth_header(client, "inv")

    checks = [
        ("admin logs route", client.get("/api/admin/app-logs", headers=admin), 200),
        ("matrix grants vendors", client.get("/api/vendors", headers=inventory_manager), 200),
        ("matrix grants reports", client.get("/api/reports", headers=inventory_manager), 200),
        ("matrix denies inventory write", client.post("/api/inventory", headers=accountant, json={}), 403),
        ("my permissions", client.get("/api/auth/permissions/my", headers=inventory_manager), 200),
    ]

    for name, response, expected_status in checks:
        assert response.status_code == expected_status, (
            name,
            response.status_code,
            response.get_data(as_text=True),
        )

    with app.app_context():
        RolePermission.__table__.drop(db.engine)

    fallback = client.get("/api/auth/permissions/my", headers=accountant)
    assert fallback.status_code == 200, fallback.get_data(as_text=True)
    assert "invoice" in fallback.get_json()["permissions"]

    fallback_route = client.get("/api/vendors", headers=accountant)
    assert fallback_route.status_code == 200, fallback_route.get_data(as_text=True)

    print("permission matrix checks passed")


if __name__ == "__main__":
    main()
