import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi import Header, HTTPException

from app.core.config import settings

TOKEN_LIFETIME = 8 * 60 * 60


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode(), salt=salt, n=16384, r=8, p=1
    )
    return f"{salt.hex()}:{derived.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, expected_hex = stored.split(":", 1)
        derived = hashlib.scrypt(
            password.encode(),
            salt=bytes.fromhex(salt_hex),
            n=16384, r=8, p=1,
        )
        return hmac.compare_digest(derived, bytes.fromhex(expected_hex))
    except (ValueError, TypeError):
        return False


def _secret() -> bytes:
    value = settings.organizer_auth_secret
    if len(value) < 32:
        raise RuntimeError(
            "ORGANIZER_AUTH_SECRET must contain at least 32 characters"
        )
    return value.encode()


def create_token(role: str) -> str:
    if role not in ("organizer", "ta"):
        raise ValueError("Invalid role")

    payload = json.dumps(
        {
            "role": role,
            "exp": int(time.time()) + TOKEN_LIFETIME,
            "nonce": secrets.token_hex(16),
        },
        separators=(",", ":"),
    ).encode()

    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=")
    signature = hmac.new(_secret(), encoded, hashlib.sha256).hexdigest()
    return f"{encoded.decode()}.{signature}"


def verify_token(token: str) -> str:
    try:
        encoded, signature = token.split(".", 1)
        expected = hmac.new(
            _secret(), encoded.encode(), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid signature")

        payload = json.loads(
            base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        )

        if payload.get("role") not in ("organizer", "ta"):
            raise ValueError("Invalid role")

        if not isinstance(payload.get("exp"), int):
            raise ValueError("Invalid expiry")

        if payload["exp"] <= time.time():
            raise ValueError("Expired token")

        return payload["role"]
    except (ValueError, TypeError, UnicodeError, KeyError) as exc:
        raise HTTPException(
            status_code=401, detail="Invalid or expired organizer token"
        ) from exc


def require_staff(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")

    return verify_token(authorization.removeprefix("Bearer ").strip())
