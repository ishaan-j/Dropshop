"""Grok Bot: the nightly policy-watch routine (SpaceXSI "Make it Legendary" requirement).

Job: retailers quietly change their price-adjustment policies (shorter windows, new exclusions), and
Dropshot's eligibility checks depend on them. Each night L2 calls `watch_policy` per retailer:
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
