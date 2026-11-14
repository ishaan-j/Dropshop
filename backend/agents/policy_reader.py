"""Understand a retailer's price-adjustment / price-match policy."""

from __future__ import annotations

from agents.gemini_client import generate_structured
from app.models import RetailerPolicy

# Hardcoded demo policies. Windows match backend/app/mock_data.py. These are simplified for the
# demo and are not legal summaries of the real retailer policies.
POLICIES: dict[str, RetailerPolicy] = {
    "best buy": RetailerPolicy(
        retailer="Best Buy",
        policy_url="https://www.bestbuy.com/site/help-topics/price-match-guarantee/pcmcat290300050002.c",
        window_days=15,
        conditions=[
            "The lower price must be on the same item at Best Buy (bestbuy.com or in store).",
            "Open-box, clearance and marketplace-seller prices do not qualify.",
            "Membership-only or limited-time doorbuster prices do not qualify.",
        ],
        summary="Best Buy adjusts the price if the same item drops within 15 days of purchase.",
    ),
    "target": RetailerPolicy(
        retailer="Target",
        policy_url="https://www.target.com/c/price-match-guarantee/-/N-4tdkg",
        window_days=14,
        conditions=[
            "The lower price must be on the same item sold by Target (target.com or in store).",
            "Third-party marketplace sellers (Target Plus) do not qualify.",
            "Final-sale and clearance items do not qualify.",
        ],
        summary="Target adjusts the price if the same item drops within 14 days of purchase.",
    ),
    "amazon": RetailerPolicy(
        retailer="Amazon",
        policy_url="https://www.amazon.com/gp/help/customer/display.html?nodeId=GQ6N6QGZ9FSS7JYM",
        window_days=15,
        conditions=[
            "The lower price must be on an item sold and shipped by Amazon.",
            "Third-party marketplace seller prices do not qualify.",
            "Lightning Deals and Prime-member-only prices do not qualify.",
        ],
        summary="Amazon (demo policy) adjusts the price if the same item drops within 15 days of purchase.",
    ),
}


async def get_policy(retailer: str) -> RetailerPolicy:
    """Return the policy for `retailer`. Demo retailers are hardcoded; others get a no-window
    policy (which `eligibility` treats as not eligible). L2 caches the result in Mongo."""
    policy = POLICIES.get(retailer.strip().lower())
    if policy:
        return policy.model_copy(deep=True)
    return RetailerPolicy(
        retailer=retailer, summary="No known price-adjustment policy for this retailer."
    )


async def summarize_policy_text(
    retailer: str, page_text: str, policy_url: str | None = None, *, allow_mock: bool = True
) -> RetailerPolicy:
    """Have Gemini turn raw policy-page text into a RetailerPolicy (for retailers beyond the
    hardcoded demo set, or the Grok Bot policy-refresh routine). Falls back to the hardcoded
    policy, or an empty one, when Gemini is unavailable."""
    prompt = (
        "Extract this retailer's price-adjustment / price-match policy into the schema.\n"
        "- `window_days`: days after purchase in which a price drop can be claimed, or null if not stated.\n"
        "- `conditions`: short, separate exclusions and requirements.\n"
        "- `summary`: one sentence. Never guess; use null/empty for anything not in the text.\n\n"
        f"Retailer: {retailer}\nPolicy page text:\n---\n{page_text}\n---"
    )
    fallback = POLICIES.get(retailer.strip().lower()) or RetailerPolicy(retailer=retailer)
    result = await generate_structured(
        prompt, RetailerPolicy, mock=fallback if allow_mock else None
    )
    if policy_url and not result.policy_url:
        result.policy_url = policy_url
    return result
