"""Grok Bot (SpaceXSI "Make it Legendary" requirement). Two jobs, both through xAI's chat API:

1. Claim agent: `write_claim_message` drafts the message the Playwright bot submits on the
   retailer's price-adjustment form. `claim_writer.form_message` checks the draft against the
   claim's facts and falls back to Gemini, then a template, if Grok is off or gets a fact wrong.

2. Policy watch: retailers quietly change their price-adjustment policies (shorter windows, new
   exclusions), and Dropshot's eligibility checks depend on them. Each night L2 calls
   `watch_policy` per retailer:
  1. fetch the retailer's policy page,
  2. Grok reviews it against the policy we have stored and reports what changed (and whether that
     could cost users refunds),
  3. if it changed, Gemini re-extracts the structured RetailerPolicy for L2 to save in Mongo.

Grok is reached through xAI's OpenAI-compatible chat API (XAI_API_KEY). With no key, MOCK_MODE on, or
any failure, the routine reports "no change" and keeps the stored policy, so nothing breaks.
Agents never write to the DB: L2 persists the returned policy.
"""

from __future__ import annotations

import json
import logging

import httpx
from pydantic import BaseModel

from agents.policy_reader import summarize_policy_text
from app.config import get_settings
from app.models import RetailerPolicy

logger = logging.getLogger(__name__)

MAX_PAGE_CHARS = 30_000


class PolicyReview(BaseModel):
    """Grok's verdict on a policy page versus the stored policy."""

    changed: bool = False
    summary: str = "No change detected."
    user_impact: str | None = None  # e.g. "Window shortened from 15 to 14 days"


class PolicyWatchResult(BaseModel):
    retailer: str
    changed: bool
    note: str
    policy: RetailerPolicy  # updated if changed, otherwise the stored policy unchanged
    reviewed_by: str = "grok"  # "none" when skipped


_SYSTEM = (
    "You are Dropshot's policy watchdog. Compare a retailer's current price-adjustment policy page "
    "with the policy we have stored. Reply with JSON only: "
    '{"changed": bool, "summary": str, "user_impact": str|null}. '
    "`changed` is true only if the window length or a requirement/exclusion materially differs. "
    "Ignore wording, layout and marketing changes. Never guess beyond the page text."
)


def enabled() -> bool:
    settings = get_settings()
    return bool(settings.xai_api_key) and not settings.mock_mode


_CLAIM_SYSTEM = (
    "You are Dropshot's claim agent. Write the message a customer sends through a retailer's "
    "price-adjustment form. 3-4 polite, concise sentences in the first person. Include the order "
    "number, the product, the purchase date, the price paid, the current price and the exact "
    "refund amount requested, and cite the policy basis. Use only the facts given; never invent "
    "details. Plain text only: no markdown, no subject line, no placeholders."
)


async def write_claim_message(facts: str, *, client: httpx.AsyncClient | None = None) -> str | None:
    """Grok drafts the claim-form message from the claim's facts. Returns None when Grok is off or
    the call fails, so the caller can fall back. The caller verifies the facts in the draft."""
    if not enabled():
        return None
    settings = get_settings()
    own_client = client is None
    client = client or httpx.AsyncClient()
    try:
        response = await client.post(
            f"{settings.xai_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.xai_api_key}"},
            json={
                "model": settings.xai_model,
                "temperature": 0.2,
                "messages": [{"role": "system", "content": _CLAIM_SYSTEM}, {"role": "user", "content": facts}],
            },
            timeout=12,
        )
        response.raise_for_status()
        text = (response.json()["choices"][0]["message"]["content"] or "").strip()
        return text or None
    except Exception as exc:
        logger.warning("Grok claim draft failed (%s); falling back", type(exc).__name__)
        return None
    finally:
        if own_client:
            await client.aclose()


_POLICY_LOOKUP = (
    "Find this retailer's published post-purchase price-adjustment policy: a refund of the "
    "difference when the retailer's OWN price on the same item drops after the customer already bought it. "
    "Search the retailer's official help pages. Reply with JSON only, keys: "
    "policy_url (string or null), window_days (integer or null), conditions (array of short strings), "
    "summary (one sentence). "
    "window_days is days after purchase or delivery in which that refund can be requested. "
    "Use null for window_days unless an official page states a number or states that the window is the "
    "return period and states how many days that return period is. A competitor price-match that only "
    "applies before purchase is not a post-purchase adjustment. Never guess a number. "
    "policy_url must be the official page you used, or null."
)


def _response_text(payload: dict) -> str:
    parts = []
    for item in payload.get("output") or []:
        if item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(content["text"])
    return "\n".join(parts).strip()


async def find_policy(retailer: str, *, client: httpx.AsyncClient | None = None) -> str | None:
    """Ask Grok, with web search, for a retailer's policy. Returns the reply text, or None when
    Grok is off or the call fails."""
    if not enabled():
        return None
    settings = get_settings()
    own_client = client is None
    client = client or httpx.AsyncClient()
    try:
        response = await client.post(
            f"{settings.xai_base_url.rstrip('/')}/responses",
            headers={"Authorization": f"Bearer {settings.xai_api_key}"},
            json={
                "model": settings.xai_model,
                "tools": [{"type": "web_search"}],
                "input": f"{_POLICY_LOOKUP}\n\nUse web search. Retailer: {retailer}",
            },
            timeout=60,
        )
        response.raise_for_status()
        return _response_text(response.json()) or None
    except Exception as exc:
        logger.warning("Grok policy lookup failed for %s (%s)", retailer, type(exc).__name__)
        return None
    finally:
        if own_client:
            await client.aclose()


async def _grok_review(
    stored: RetailerPolicy, page_text: str, client: httpx.AsyncClient
) -> PolicyReview:
    s = get_settings()
    stored_json = stored.model_dump_json(exclude={"policy_url"})
    resp = await client.post(
        f"{s.xai_base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {s.xai_api_key}"},
        json={
            "model": s.xai_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {
                    "role": "user",
                    "content": f"Stored policy:\n{stored_json}\n\nCurrent page text:\n---\n"
                    f"{page_text[:MAX_PAGE_CHARS]}\n---",
                },
            ],
        },
        timeout=60,
    )
    resp.raise_for_status()
    return PolicyReview.model_validate(json.loads(resp.json()["choices"][0]["message"]["content"]))


async def watch_policy(
    stored: RetailerPolicy,
    *,
    page_text: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> PolicyWatchResult:
    """Check one retailer's policy for changes. Pass `page_text` to skip the fetch (tests, or when
    the Playwright layer already has the page). Never raises; failures mean 'no change'."""
    s = get_settings()
    unchanged = lambda note, by="none": PolicyWatchResult(  # noqa: E731
        retailer=stored.retailer, changed=False, note=note, policy=stored, reviewed_by=by
    )
    if s.mock_mode or not s.xai_api_key:
        return unchanged("Grok disabled (mock mode or no XAI_API_KEY); keeping stored policy.")

    own_client = client is None
    client = client or httpx.AsyncClient(follow_redirects=True)
    try:
        if page_text is None:
            if not stored.policy_url:
                return unchanged("No policy URL to check.")
            page = await client.get(stored.policy_url, timeout=30, headers={"User-Agent": "Dropshot-PolicyWatch"})
            page.raise_for_status()
            page_text = page.text
        review = await _grok_review(stored, page_text, client)
        if not review.changed:
            return unchanged(review.summary, by="grok")
        note = review.summary + (f" Impact: {review.user_impact}" if review.user_impact else "")
        try:
            updated = await summarize_policy_text(
                stored.retailer, page_text, stored.policy_url, allow_mock=False
            )
        except Exception as exc:
            # Don't pass off the stored policy as an update: flag it for manual review instead.
            logger.warning("Policy re-extraction failed for %s: %s", stored.retailer, type(exc).__name__)
            return PolicyWatchResult(
                retailer=stored.retailer, changed=True, policy=stored, reviewed_by="grok",
                note=f"{note} (Could not re-extract the new policy; stored policy kept, review manually.)",
            )
        return PolicyWatchResult(
            retailer=stored.retailer, changed=True, note=note, policy=updated, reviewed_by="grok"
        )
    except Exception as exc:
        logger.exception("Policy watch failed for %s", stored.retailer)
        return unchanged(f"Policy check failed ({type(exc).__name__}); keeping stored policy.")
    finally:
        if own_client:
            await client.aclose()
