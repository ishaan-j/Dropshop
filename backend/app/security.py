"""Session tokens and redaction. No private keys and no API keys leave this module."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

_RUNTIME_SECRET = secrets.token_hex(32)
_RUNTIME_FERNET = Fernet(Fernet.generate_key())
_SECRET_RE = re.compile(
    r"(mongodb(\+srv)?://\S+|postgres(?:ql)?://\S+|api[_-]?key=\S+|key=[A-Za-z0-9]+|Bearer\s+\S+)",
    re.IGNORECASE,
)


def session_secret() -> str:
    configured = get_settings().session_secret.strip()
    return configured or _RUNTIME_SECRET


def session_secret_is_ephemeral() -> bool:
    return not get_settings().session_secret.strip()


def issue_token(user_id: str, ttl_seconds: int = 60 * 60 * 24 * 3) -> str:
    exp = int(time.time()) + ttl_seconds
    payload = f"{user_id}.{exp}"
    sig = hmac.new(session_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def read_token(token: str) -> str | None:
    try:
        user_id, exp, sig = token.rsplit(".", 2)
        payload = f"{user_id}.{exp}"
        expected = hmac.new(session_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        if int(exp) < time.time():
            return None
        if not user_id.startswith("usr_"):
            return None
        return user_id
    except (ValueError, TypeError):
        return None


def fernet() -> Fernet:
    raw = get_settings().token_encryption_key.strip()
    if not raw:
        return _RUNTIME_FERNET
    return Fernet(raw.encode())


def encrypt_secret(value: str) -> str:
    return fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str | None:
    try:
        return fernet().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError):
        return None


def safe_detail(exc: BaseException) -> str:
    text = _SECRET_RE.sub("[redacted]", str(exc))
    return text[:300] or exc.__class__.__name__
