"""Create the admin user. From the api directory: python create_admin.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.models import User
from app.security import hash_password


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.scalar(select(User).where(User.username == "admin"))
        if existing:
            print("Admin user already exists")
            return
        admin = User(
            username="admin",
            email="admin@germanato.com",
            password_hash=hash_password("admin123"),
            role="admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print("Admin user created")
        print("Username: admin")
        print("Password: admin123")
    finally:
        db.close()


if __name__ == "__main__":
    main()
