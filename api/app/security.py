"""Password hashes and JWTs.

New passwords are bcrypt. Existing rows may be Werkzeug hashes
(``pbkdf2:sha256`` or the Werkzeug 3 default ``scrypt``), or the colon/base64
pbkdf2 fallback used by the Flask User model.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.config import settings

_ALGORITHM = "HS256"
_PBKDF2_DEFAULT_ITERATIONS = 600000

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
]

DEFAULT_ROLE_PERMISSIONS = {
    "admin": ADMIN_PERMISSIONS,
    "accountant": [
        "home",
        "invoice",
        "search",
        "car",
        "daily-expenses",
        "vendors",
        "vendor-detail",
        "hr",
        "worker-detail",
        "repair-order",
        "repair-orders-management",
        "settings",
    ],
    "inventory_manager": [
        "home",
        "inventory",
        "repair-order",
        "repair-orders-management",
        "settings",
    ],
}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash or password is None:
        return False
    try:
        if password_hash.startswith(("$2a$", "$2b$", "$2y$")):
            return bcrypt.checkpw(
                password.encode("utf-8"), password_hash.encode("ascii")
            )
        if "$" in password_hash:
            return _verify_werkzeug(password, password_hash)
        return _verify_pbkdf2_colon(password, password_hash)
    except (ValueError, TypeError):
        return False


def _verify_werkzeug(password: str, stored: str) -> bool:
    method, salt, hashval = stored.split("$", 2)
    digest = _werkzeug_digest(method, salt, password)
    return hmac.compare_digest(digest, hashval)


def _werkzeug_digest(method: str, salt: str, password: str) -> str:
    """Same KDF as Werkzeug's ``check_password_hash`` (hex digest)."""
    name, *args = method.split(":")
    salt_b = salt.encode("utf-8")
    password_b = password.encode("utf-8")

    if name == "pbkdf2":
        if len(args) == 0:
            hash_name, iterations = "sha256", _PBKDF2_DEFAULT_ITERATIONS
        elif len(args) == 1:
            hash_name, iterations = args[0], _PBKDF2_DEFAULT_ITERATIONS
        elif len(args) == 2:
            hash_name, iterations = args[0], int(args[1])
        else:
            raise ValueError("pbkdf2 takes 2 arguments")
        return hashlib.pbkdf2_hmac(hash_name, password_b, salt_b, iterations).hex()

    if name == "scrypt":
        if not args:
            n, r, p = 2**15, 8, 1
        else:
            n, r, p = map(int, args)
        maxmem = 132 * n * r * p
        return hashlib.scrypt(password_b, salt=salt_b, n=n, r=r, p=p, maxmem=maxmem).hex()

    raise ValueError(f"unsupported hash method {name}")


def _verify_pbkdf2_colon(password: str, stored: str) -> bool:
    """Flask ``User._fallback_check_password``: base64 salt and hash, 260000 rounds."""
    if not stored.startswith("pbkdf2:sha256:"):
        return False
    parts = stored.split(":")
    if len(parts) != 4:
        return False
    salt = base64.b64decode(parts[2])
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260000)
    return hmac.compare_digest(base64.b64encode(digest).decode("ascii"), parts[3])


def _encode(user_id: int, token_type: str, expires: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + expires,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=_ALGORITHM)


def create_access_token(user_id: int) -> str:
    return _encode(user_id, "access", timedelta(minutes=settings.jwt_access_minutes))


def create_refresh_token(user_id: int) -> str:
    return _encode(user_id, "refresh", timedelta(days=settings.jwt_refresh_days))


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[_ALGORITHM])


__all__ = [
    "ADMIN_PERMISSIONS",
    "DEFAULT_ROLE_PERMISSIONS",
    "JWTError",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "hash_password",
    "verify_password",
]


def _demo() -> None:
    secret = "admin123"
    salt = "salt"
    rounds = 1000
    pbkdf2 = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt.encode(), rounds).hex()
    stored = f"pbkdf2:sha256:{rounds}${salt}${pbkdf2}"
    assert verify_password(secret, stored)
    assert not verify_password("nope", stored)

    n, r, p = 2**15, 8, 1
    scrypt = hashlib.scrypt(
        secret.encode(), salt=salt.encode(), n=n, r=r, p=p, maxmem=132 * n * r * p
    ).hex()
    assert verify_password(secret, f"scrypt:{n}:{r}:{p}${salt}${scrypt}")

    colon_salt = base64.b64encode(b"salt").decode("ascii")
    colon_hash = base64.b64encode(
        hashlib.pbkdf2_hmac("sha256", secret.encode(), b"salt", 260000)
    ).decode("ascii")
    assert verify_password(secret, f"pbkdf2:sha256:{colon_salt}:{colon_hash}")
    assert not verify_password("nope", f"pbkdf2:sha256:{colon_salt}:{colon_hash}")

    new_hash = hash_password(secret)
    assert new_hash.startswith("$2")
    assert verify_password(secret, new_hash)
    assert not verify_password("nope", new_hash)

    access = create_access_token(7)
    payload = decode_token(access)
    assert payload["sub"] == "7" and payload["type"] == "access"
    print("security ok")


if __name__ == "__main__":
    _demo()
