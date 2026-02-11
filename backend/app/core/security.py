from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import os
from secrets import compare_digest
from typing import Any
from uuid import uuid4

from app.core.config import settings


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def _sign(message: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    return _b64url_encode(sig)


def _secret() -> str:
    return getattr(settings, "jwt_secret", None) or "dev-secret-change-me"


def hash_token(token: str, *, purpose: str = "refresh") -> str:
    """Deterministically hash a token for DB storage (never store raw refresh tokens)."""
    msg = f"{purpose}:{token}".encode("utf-8")
    digest = hmac.new(_secret().encode("utf-8"), msg, hashlib.sha256).digest()
    return _b64url_encode(digest)


def _create_jwt(payload: dict[str, Any]) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature_b64 = _sign(signing_input, _secret())
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def _now_ts() -> int:
    return int(time.time())


def create_refresh_token(subject: str, expires_in_seconds: int | None = None) -> str:
    ttl = int(expires_in_seconds or getattr(settings, "refresh_token_ttl_seconds", 60 * 60 * 24 * 30))

    if getattr(settings, "insecure_auth", False):
        # Insecure mode: return a simple unsigned token (subject|refresh|exp)
        exp = _now_ts() + ttl
        return f"{subject}|refresh|{exp}"

    now = _now_ts()
    payload: dict[str, Any] = {
        "sub": subject,
        "typ": "refresh",
        "jti": str(uuid4()),
        "iss": getattr(settings, "jwt_issuer", "svod-api"),
        "iat": now,
        "exp": now + ttl,
    }
    return _create_jwt(payload)


def create_access_token(subject: str, role: str, expires_in_seconds: int = 60 * 60 * 8) -> str:
    ttl = int(expires_in_seconds or getattr(settings, "access_token_ttl_seconds", 60 * 60 * 8))

    # Insecure mode: return a simple unsigned token (subject|role|exp)
    if getattr(settings, "insecure_auth", False):
        exp = _now_ts() + ttl
        return f"{subject}|{role}|{exp}"

    now = _now_ts()
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "typ": "access",
        "jti": str(uuid4()),
        "iss": getattr(settings, "jwt_issuer", "svod-api"),
        "iat": now,
        "exp": now + ttl,
    }
    return _create_jwt(payload)


def decode_token(token: str, *, expected_type: str | None = "access") -> dict[str, Any]:
    # Insecure mode: token is expected as "<sub>|<role>|<exp>" or "<sub>|refresh|<exp>"
    if getattr(settings, "insecure_auth", False) and "|" in token and "." not in token:
        try:
            parts = token.split("|")
            if len(parts) != 3:
                raise ValueError("Invalid token format")
            sub, second, exp_s = parts
            exp = int(exp_s)
            if exp and _now_ts() > exp:
                raise ValueError("Token expired")

            if second == "refresh":
                payload = {"sub": sub, "typ": "refresh", "exp": exp}
            else:
                payload = {"sub": sub, "role": second, "typ": "access", "exp": exp}

            if expected_type is not None and payload.get("typ") != expected_type:
                raise ValueError("Invalid token type")
            return payload
        except Exception as e:
            raise ValueError("Invalid token format") from e

    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError:
        raise ValueError("Invalid token format")

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    secret = _secret()

    expected_sig = _sign(signing_input, secret)
    if not hmac.compare_digest(expected_sig, signature_b64):
        raise ValueError("Invalid signature")

    payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    exp = int(payload.get("exp", 0))
    if exp and int(time.time()) > exp:
        raise ValueError("Token expired")

    if expected_type is not None:
        typ = str(payload.get("typ") or "")
        if typ != expected_type:
            raise ValueError("Invalid token type")

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
