import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.errors import DomainError

_hasher = PasswordHasher()


def normalize_email(value: str) -> str:
    return value.strip().casefold()


def validate_password(value: str) -> None:
    if (
        len(value) < 9
        or not any(x.isupper() for x in value)
        or not any(x.islower() for x in value)
        or not any(not x.isalnum() and not x.isspace() for x in value)
    ):
        raise DomainError(
            "INVALID_PASSWORD",
            "Use at least nine characters with uppercase, lowercase and a special character.",
            422,
            {"password": "Password requirements not met"},
        )


def hash_password(value: str) -> str:
    validate_password(value)
    return _hasher.hash(value)


def verify_password(value: str, encoded: str) -> bool:
    try:
        return _hasher.verify(encoded, value)
    except (VerificationError, InvalidHashError):
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
