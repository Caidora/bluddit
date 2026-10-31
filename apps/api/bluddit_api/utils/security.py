"""Shared credential validation and opaque token primitives."""
import base64
import hashlib
import re
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

PENDING, ACTIVE, REJECTED, INACTIVE = "pending", "active", "rejected", "inactive"
PASSWORD_HASHER = PasswordHasher()
# A dummy hash gives unknown usernames the same expensive verification path.
DUMMY_HASH = PASSWORD_HASHER.hash(secrets.token_urlsafe(32))


def normalize_username(value: str) -> str:
    username = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9_]{3,32}", username):
        raise ValueError("Username must contain 3–32 ASCII letters, digits, or underscores")
    return username


def validate_password(value: str) -> str:
    if not 12 <= len(value) <= 128:
        raise ValueError("Password must contain 12–128 characters")
    return value


def verify_password(encoded: str, password: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str | None) -> bytes | None:
    if token is None or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        return None
    decoded = base64.urlsafe_b64decode(token + "=")
    if base64.urlsafe_b64encode(decoded).decode().rstrip("=") != token:
        return None
    return hashlib.sha256(token.encode("ascii")).digest()
