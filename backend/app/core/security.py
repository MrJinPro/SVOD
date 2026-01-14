from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import os
from secrets import compare_digest
from typing import Any

from app.core.config import settings


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def _sign(message: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    return _b64url_encode(sig)


def create_access_token(subject: str, role: str, expires_in_seconds: int = 60 * 60 * 8) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + expires_in_seconds,
    }

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")

    secret = getattr(settings, "jwt_secret", None) or "dev-secret-change-me"
    signature_b64 = _sign(signing_input, secret)
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def decode_token(token: str) -> dict[str, Any]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError:
        raise ValueError("Invalid token format")

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    secret = getattr(settings, "jwt_secret", None) or "dev-secret-change-me"

    expected_sig = _sign(signing_input, secret)
    if not hmac.compare_digest(expected_sig, signature_b64):
        raise ValueError("Invalid signature")

    payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    exp = int(payload.get("exp", 0))
    if exp and int(time.time()) > exp:
        raise ValueError("Token expired")

    return payload


def hash_password(password: str, *, iterations: int = 210_000) -> str:
    """Хэширует пароль через PBKDF2-SHA256.

    Формат хранения: pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>
    """
    if password is None:
        raise ValueError("Password is required")
    salt = hashlib.sha256(str(time.time()).encode("utf-8") + os.urandom(16)).digest()[:16]
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    salt_b64 = _b64url_encode(salt)
    dk_b64 = _b64url_encode(dk)
    return f"pbkdf2_sha256${iterations}${salt_b64}${dk_b64}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algo, iters_s, salt_b64, dk_b64 = stored_hash.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iters_s)
        salt = _b64url_decode(salt_b64)
        expected = _b64url_decode(dk_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return compare_digest(actual, expected)
    except Exception:
        return False
