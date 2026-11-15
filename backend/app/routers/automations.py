"""Endpoints for an outside automation to call, such as a Grok Bot routine.

Grok Bot (SpaceXAI's hosted agent) can browse retailer sites that block scripts. Its routine opens
a retailer's price-adjustment policy page and posts the page text here; Dropshot then compares it
with the stored policy and updates it if it changed. See docs/submission.md for the bot's brief.

Protected by a shared secret: send `Authorization: Bearer <AUTOMATION_TOKEN>`. With no token
configured the endpoints are off.
"""

import hmac

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from agents import grok_bot
from app.config import get_settings
from app.store import get_store
from app.workers import tasks

router = APIRouter(prefix="/automations", tags=["automations"])


def _authorize(authorization: str | None) -> None:
    token = get_settings().automation_token
    if not token:
        raise HTTPException(503, "Automation endpoints are off. Set AUTOMATION_TOKEN to enable them.")
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied.encode(), token.encode()):
        raise HTTPException(401, "Missing or wrong automation token")


class PolicyPage(BaseModel):
    retailer: str = Field(min_length=1, max_length=80)
    page_text: str = Field(min_length=40, max_length=200_000)
    source_url: str | None = Field(None, max_length=500)


@router.post("/policy-page")
async def submit_policy_page(body: PolicyPage, authorization: str | None = Header(None)) -> dict:
    """Review a retailer's current policy page against the stored policy; store it if it changed."""
    _authorize(authorization)
    stored = await tasks.policy_for(body.retailer)
    if body.source_url and not stored.policy_url:
        stored = stored.model_copy(update={"policy_url": body.source_url})
    result = await grok_bot.watch_policy(stored, page_text=body.page_text)  # never raises
    if result.changed:
        await get_store().save_policy(result.policy)
        await tasks.log_event(
            "eligibility_checked",
            f"Grok Bot policy watch: {body.retailer}'s price-adjustment policy changed. {result.note}",
        )
    elif result.reviewed_by == "grok":
        await tasks.log_event(
            "eligibility_checked", f"Grok Bot policy watch checked {body.retailer}'s policy: no change."
        )
    return {
        "retailer": result.retailer,
        "changed": result.changed,
        "note": result.note,
        "window_days": result.policy.window_days,
        "reviewed_by": result.reviewed_by,
    }
