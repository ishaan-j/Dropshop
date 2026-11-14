"""Gmail readonly OAuth. Tokens stay encrypted on the server.

Flow and endpoints:
https://developers.google.com/identity/protocols/oauth2/web-server
https://developers.google.com/gmail/api/reference/rest/v1/users.messages
Scope is gmail.readonly. DropShop does not send or delete mail.
"""

from __future__ import annotations

import base64
import secrets
import time
from urllib.parse import urlencode

import httpx

from app.config import get_settings
from app.security import decrypt_secret, encrypt_secret
from data.repository import repo

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
PROFILE_URL = "https://gmail.googleapis.com/gmail/v1/users/me/profile"
LIST_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages"

_states: dict[str, tuple[str, float]] = {}


class GmailNotConfigured(RuntimeError):
    pass


class GmailError(RuntimeError):
    pass


def oauth_configured() -> bool:
    settings = get_settings()
    return bool(settings.gmail_client_id.strip() and settings.gmail_client_secret.strip())


def start_url(user_id: str) -> str:
    if not oauth_configured():
        raise GmailNotConfigured("Gmail OAuth client id and secret are not configured.")
    settings = get_settings()
    state = secrets.token_urlsafe(24)
    _states[state] = (user_id, time.time() + 600)
    query = urlencode(
        {
            "client_id": settings.gmail_client_id,
            "redirect_uri": settings.gmail_redirect_uri,
            "response_type": "code",
            "scope": GMAIL_SCOPE,
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state,
        }
    )
    return f"{AUTH_URL}?{query}"


def take_state(state: str) -> str | None:
    row = _states.pop(state, None)
    if not row or row[1] < time.time():
        return None
    return row[0]


async def exchange_code(user_id: str, code: str) -> str:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.gmail_client_id,
                "client_secret": settings.gmail_client_secret,
                "redirect_uri": settings.gmail_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    if response.status_code >= 400:
        raise GmailError(f"Google token exchange returned HTTP {response.status_code}.")
    payload = response.json()
    access = payload.get("access_token")
    if not access:
        raise GmailError("Google did not return an access token.")
    email = await _profile_email(access)
    stored = {
        "access_token_enc": encrypt_secret(access),
        "expires_at": time.time() + int(payload.get("expires_in") or 3600) - 30,
        "email": email,
    }
    if payload.get("refresh_token"):
        stored["refresh_token_enc"] = encrypt_secret(payload["refresh_token"])
    await repo.save_connection(user_id, {"gmail": stored})
    return email or ""


async def disconnect(user_id: str) -> None:
    current = await repo.get_connection(user_id)
    gmail = current.get("gmail") or {}
    token = _decrypt(gmail.get("access_token_enc")) or _decrypt(gmail.get("refresh_token_enc"))
    if token:
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                await client.post("https://oauth2.googleapis.com/revoke", params={"token": token})
        except httpx.HTTPError:
            pass
    await repo.save_connection(user_id, {"gmail": None})


async def connection_view(user_id: str) -> dict:
    gmail = (await repo.get_connection(user_id)).get("gmail") or {}
    return {
        "connected": bool(gmail.get("access_token_enc") or gmail.get("refresh_token_enc")),
        "email": gmail.get("email"),
        "oauth_configured": oauth_configured(),
    }


async def list_order_messages(user_id: str, limit: int = 10) -> list[dict]:
    token = await _access_token(user_id)
    query = "newer_than:30d (subject:order OR subject:receipt OR subject:shipped OR subject:confirmation)"
    async with httpx.AsyncClient(timeout=20) as client:
        listing = await client.get(LIST_URL, params={"q": query, "maxResults": limit}, headers=_auth(token))
        if listing.status_code >= 400:
            raise GmailError(f"Gmail list returned HTTP {listing.status_code}.")
        messages = listing.json().get("messages") or []
        found = []
        for item in messages:
            detail = await client.get(f"{LIST_URL}/{item['id']}", params={"format": "full"}, headers=_auth(token))
            if detail.status_code >= 400:
                continue
            payload = detail.json().get("payload") or {}
            headers = {h.get("name", "").lower(): h.get("value", "") for h in payload.get("headers") or []}
            found.append(
                {
                    "id": item["id"],
                    "subject": headers.get("subject", ""),
                    "text": _plain_text(payload)[:20000],
                }
            )
        return found


async def _access_token(user_id: str) -> str:
    gmail = (await repo.get_connection(user_id)).get("gmail") or {}
    access = _decrypt(gmail.get("access_token_enc"))
    if access and float(gmail.get("expires_at") or 0) > time.time():
        return access
    refresh = _decrypt(gmail.get("refresh_token_enc"))
    if not refresh:
        raise GmailError("Gmail is not connected.")
    settings = get_settings()
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "client_id": settings.gmail_client_id,
                "client_secret": settings.gmail_client_secret,
                "refresh_token": refresh,
                "grant_type": "refresh_token",
            },
        )
    if response.status_code >= 400:
        raise GmailError("Gmail refresh failed. Connect the account again.")
    payload = response.json()
    access = payload.get("access_token")
    if not access:
        raise GmailError("Gmail refresh did not return an access token.")
    gmail["access_token_enc"] = encrypt_secret(access)
    gmail["expires_at"] = time.time() + int(payload.get("expires_in") or 3600) - 30
    await repo.save_connection(user_id, {"gmail": gmail})
    return access


async def _profile_email(access_token: str) -> str | None:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(PROFILE_URL, headers=_auth(access_token))
    if response.status_code >= 400:
        return None
    return response.json().get("emailAddress")


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _decrypt(value: str | None) -> str | None:
    if not value:
        return None
    return decrypt_secret(value)


def _decode(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode()).decode("utf-8", errors="replace")


def _plain_text(payload: dict) -> str:
    mime = payload.get("mimeType") or ""
    data = (payload.get("body") or {}).get("data")
    chunks: list[str] = []
    if data and mime.startswith("text/plain"):
        chunks.append(_decode(data))
    for part in payload.get("parts") or []:
        chunks.append(_plain_text(part))
    if not chunks and data:
        chunks.append(_decode(data))
    return "\n".join(chunk for chunk in chunks if chunk)
