"""Password hashing via bcrypt directly.

Replaces passlib's CryptContext: passlib 1.7.4 is unmaintained and its
backend self-test crashes with bcrypt >= 4.1 ("password cannot be longer
than 72 bytes"), which broke register/login entirely. Hashes remain
standard $2b$ bcrypt, so everything already stored keeps verifying.
"""

from __future__ import annotations

import bcrypt


def hash_password(password: str) -> str:
    """Hash a password with bcrypt (72-byte input limit enforced upstream
    by request validation; truncated here as a hard safety net)."""
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time verify; False on malformed/legacy hashes."""
    try:
        return bcrypt.checkpw(password.encode()[:72], password_hash.encode())
    except ValueError:
        return False


class _PwdContextShim:
    """Drop-in for the old ``pwd_context`` (passlib CryptContext) surface."""

    @staticmethod
    def hash(password: str) -> str:
        return hash_password(password)

    @staticmethod
    def verify(password: str, password_hash: str) -> bool:
        return verify_password(password, password_hash)


pwd_context = _PwdContextShim()
