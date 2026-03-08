"""JWT authentication for ENLACE API.

Provides token creation, verification, and decoding.  Attempts to use
``python-jose`` first, then falls back to ``PyJWT``.  If neither is
installed, a simple HMAC-SHA256 token implementation is used so the
platform can run without extra dependencies during development.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY",
    "enlace-dev-secret-key-change-in-production",
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

# ---------------------------------------------------------------------------
# Select JWT backend
# ---------------------------------------------------------------------------
_BACKEND = "hmac"  # fallback

try:
    from jose import jwt as jose_jwt, JWTError as JoseJWTError  # type: ignore[import-untyped]
    _BACKEND = "jose"
    logger.info("JWT backend: python-jose")
except ImportError:
    try:
        import jwt as pyjwt  # type: ignore[import-untyped]
        _BACKEND = "pyjwt"
        logger.info("JWT backend: PyJWT")
    except ImportError:
        logger.warning(
            "Neither python-jose nor PyJWT installed. "
            "Using built-in HMAC-SHA256 tokens (development only)."
        )


# ---------------------------------------------------------------------------
# Built-in HMAC-SHA256 fallback
# ---------------------------------------------------------------------------

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def _hmac_sign(payload: dict) -> str:
    """Create a simple JWT-like token using HMAC-SHA256."""
    header = {"alg": "HS256", "typ": "JWT"}
    h = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    p = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    message = f"{h}.{p}"
    sig = hmac.new(
        SECRET_KEY.encode(),
        message.encode(),
        hashlib.sha256,
    ).digest()
    return f"{message}.{_b64url_encode(sig)}"


def _hmac_verify(token: str) -> dict | None:
    """Verify and decode an HMAC-SHA256 token."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        message = f"{parts[0]}.{parts[1]}"
        expected_sig = hmac.new(
            SECRET_KEY.encode(),
            message.encode(),
            hashlib.sha256,
        ).digest()
        actual_sig = _b64url_decode(parts[2])
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        payload = json.loads(_b64url_decode(parts[1]))
        # Check expiration
        if "exp" in payload and payload["exp"] < time.time():
            return None
        return payload
    except Exception:
        return None


def _hmac_decode(token: str) -> dict:
    """Decode an HMAC token without verification (for debugging)."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid token format")
        return json.loads(_b64url_decode(parts[1]))
    except Exception as e:
        raise ValueError(f"Token decode failed: {e}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token.

    Args:
        data: Payload data (typically contains ``sub``, ``email``,
              ``tenant_id``, ``role``).
        expires_delta: Optional custom expiration. Defaults to
                       ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({
        "exp": int(expire.timestamp()),
        "iat": int(datetime.utcnow().timestamp()),
    })

    if _BACKEND == "jose":
        return jose_jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    elif _BACKEND == "pyjwt":
        return pyjwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    else:
        return _hmac_sign(to_encode)


def verify_token(token: str) -> dict | None:
    """Verify and decode a JWT token.

    Args:
        token: Encoded JWT string.

    Returns:
        Decoded payload dict, or None if verification fails.
    """
    try:
        if _BACKEND == "jose":
            payload = jose_jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        elif _BACKEND == "pyjwt":
            payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        else:
            return _hmac_verify(token)
    except Exception as e:
        logger.debug(f"Token verification failed: {e}")
        return None


def decode_token(token: str) -> dict:
    """Decode a token without verification (for debugging).

    WARNING: This does NOT verify the signature. Use only for
    inspection/debugging purposes.

    Args:
        token: Encoded JWT string.

    Returns:
        Decoded payload dict.

    Raises:
        ValueError: If the token cannot be decoded.
    """
    try:
        if _BACKEND == "jose":
            return jose_jwt.decode(
                token, SECRET_KEY, algorithms=[ALGORITHM],
                options={"verify_signature": False, "verify_exp": False},
            )
        elif _BACKEND == "pyjwt":
            return pyjwt.decode(
                token, SECRET_KEY, algorithms=[ALGORITHM],
                options={"verify_signature": False, "verify_exp": False},
            )
        else:
            return _hmac_decode(token)
    except Exception as e:
        raise ValueError(f"Token decode failed: {e}")
