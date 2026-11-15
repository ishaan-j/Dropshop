"""Understand a retailer's price-adjustment / price-match policy."""

from __future__ import annotations

import asyncio
import json
import logging
import re

import httpx

from agents.gemini_client import GeminiUnavailable, generate_grounded_text, generate_structured
from app.config import get_settings
from app.models import RetailerPolicy

logger = logging.getLogger(__name__)

_LOOKUP_PROMPT = (
    "Find this retailer's published post-purchase price-adjustment policy: a refund of the "
    "difference when the retailer's OWN price on the same item drops after the customer already bought it. "
    "Use Google Search and the retailer's official help pages. Reply with JSON only, no markdown, keys: "
    "policy_url (string or null), window_days (integer or null), conditions (array of short strings), "
    "summary (one sentence). "
    "window_days is days after purchase or delivery in which that refund can be requested. "
    "Use null for window_days unless an official page states a number, or states that the window is the "
    "return period and states how many days that return period is. A competitor price-match that only "
    "applies before purchase is not a post-purchase adjustment. Never guess a number. "
    "policy_url must be the official page you used, or null.\n\nRetailer: {retailer}"
)

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
    # https://www.bhphotovideo.com/find/HelpCenter/priceMatch.jsp
    # A later drop in B&H's own price can be refunded inside the return period.
    # That period is 30 days from delivery for most items:
    # https://www.bhphotovideo.com/find/HelpCenter/ReturnExchange.jsp
    "b&h photo video": RetailerPolicy(
        retailer="B&H Photo Video",
        policy_url="https://www.bhphotovideo.com/find/HelpCenter/priceMatch.jsp",
        window_days=30,
        conditions=[
            "The lower price must be B&H's own later price on the same item, not a competitor's price.",
            "The request has to fall inside the return and exchange period, 30 days from delivery for most items.",
            "Some categories have a shorter return window than 30 days.",
            "The difference is credited to the original payment method.",
        ],
        summary="B&H may refund the difference if its own price on the same item drops within the return and exchange period, 30 days from delivery for most items.",
    ),
}

# Names that should resolve to a policy stored under another key.
_POLICY_ALIASES = {
    "b&h": "b&h photo video",
    "b&h photo": "b&h photo video",
    "bh photo": "b&h photo video",
    "bh photo video": "b&h photo video",
    "b and h": "b&h photo video",
    "b and h photo": "b&h photo video",
    "b and h photo video": "b&h photo video",
}


def _policy_key(retailer: str) -> str:
    key = retailer.strip().lower()
    return _POLICY_ALIASES.get(key, key)


def is_unset_policy(policy: RetailerPolicy | None) -> bool:
    """True when we never found a window, including the placeholder saved for an unknown retailer."""
    if policy is None:
        return True
    return policy.window_days is None and "no known price-adjustment policy" in policy.summary.lower()


def unset_policy(retailer: str) -> RetailerPolicy:
    return RetailerPolicy(
        retailer=retailer, summary="No known price-adjustment policy for this retailer."
    )


def _known_policy(retailer: str) -> RetailerPolicy | None:
    policy = POLICIES.get(_policy_key(retailer))
    if policy is None:
        return None
    found = policy.model_copy(deep=True)
    if retailer.strip().lower() == found.retailer.lower():
        found.retailer = retailer.strip()
    return found


_POLICY_PHRASES = (
    "price adjustment",
    "price protection",
    "price difference",
    "price drop",
    "price match",
    "price reduction",
    "price guarantee",
)


async def page_states_price_policy(url: str, window_days: int | None = None) -> bool | None:
    """Whether the page states the price adjustment.

    True means the page text includes it. False means the page loaded and does not say that.
    None means the page could not be read (a block or a network error), so the citation is
    unverified rather than contradicted.
    """
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            response = await client.get(url, headers={"User-Agent": "DropshotPolicyCheck/1.0"})
    except Exception:
        return None
    if response.status_code >= 400:
        return None
    text = response.text.lower()
    if not any(phrase in text for phrase in _POLICY_PHRASES):
        return False
    if window_days is not None and str(window_days) not in text:
        return False
    return True


_DAY_COUNT = re.compile(r"\b(\d{1,3})\s*(?:calendar\s+)?days?\b", re.I)


def stated_window_days(policy: RetailerPolicy) -> int | None:
    """The window the model stated, including a count that only appears in the summary."""
    if policy.window_days and policy.window_days > 0:
        return policy.window_days
    text = " ".join([policy.summary, *policy.conditions])
    counts = [int(match) for match in _DAY_COUNT.findall(text) if 1 <= int(match) <= 365]
    return min(counts) if counts else None


def _usable(policy: RetailerPolicy | None) -> bool:
    """A lookup only counts when it names a window and the official page it came from."""
    if policy is None or not policy.window_days or policy.window_days <= 0:
        return False
    url = (policy.policy_url or "").strip()
    return url.startswith("http://") or url.startswith("https://")


def parse_policy_json(retailer: str, text: str) -> RetailerPolicy | None:
    """Pull a RetailerPolicy out of a model reply. None when the reply is not that JSON."""
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    days = data.get("window_days")
    if isinstance(days, str) and days.strip().isdigit():
        data["window_days"] = int(days.strip())
    if not isinstance(data.get("conditions"), list):
        data["conditions"] = []
    data["conditions"] = [str(item) for item in data["conditions"] if str(item).strip()]
    data["retailer"] = retailer
    try:
        return RetailerPolicy.model_validate(data)
    except ValueError:
        return None


def combine_policy_findings(
    retailer: str,
    findings: list[tuple[str, RetailerPolicy | None]],
    *,
    failures: int,
) -> RetailerPolicy:
    """Merge independent lookups. A published window from either bot is enough.

    When the windows disagree, keep the shorter one. When every bot that answered found nothing,
    that negative result is final. When every bot failed to answer, return the placeholder so the
    next check tries again.
    """
    usable = [(name, policy) for name, policy in findings if _usable(policy)]
    if not usable:
        if findings or failures == 0:
            who = " and ".join(name for name, _ in findings) or "the policy check"
            return RetailerPolicy(
                retailer=retailer,
                summary=f"{who} found no published price-adjustment window for this retailer.",
            )
        return unset_policy(retailer)

    usable.sort(key=lambda item: item[1].window_days or 0)
    name, chosen = usable[0]
    chosen = chosen.model_copy(deep=True)
    chosen.retailer = retailer.strip() or retailer
    others = [days for _, policy in usable[1:] if (days := policy.window_days) and days != chosen.window_days]
    notes = list(chosen.conditions)
    if others:
        notes.append(
            f"A second check reported a {max(others)}-day window; using the shorter {chosen.window_days}-day window."
        )
    found_by = ", ".join(source for source, _ in usable)
    notes.append(f"Policy found by {found_by}.")
    chosen.conditions = notes
    if name and not chosen.summary.lower().startswith("found by"):
        chosen.summary = chosen.summary.strip()
    return chosen


async def _gemini_find(retailer: str) -> tuple[RetailerPolicy | None, bool]:
    """(policy or None, failed). None with failed False means Gemini answered and found nothing.

    Google Search is preferred. When that quota is exhausted, ask the same question without
    search. A window still has to come with an official page URL or it is discarded.
    """
    prompt = _LOOKUP_PROMPT.format(retailer=retailer)
    try:
        text = await generate_grounded_text(prompt)
        return parse_policy_json(retailer, text), False
    except GeminiUnavailable:
        return None, True
    except Exception as exc:
        logger.warning("Gemini search failed for %s (%s); asking without search", retailer, type(exc).__name__)
    try:
        policy = await generate_structured(prompt, RetailerPolicy, mock=None)
        policy.retailer = retailer
        return policy, False
    except Exception as exc:
        logger.warning("Gemini policy lookup failed for %s (%s)", retailer, type(exc).__name__)
        return None, True


async def _grok_find(retailer: str) -> tuple[RetailerPolicy | None, bool] | None:
    """None when Grok is off. Otherwise (policy or None, failed)."""
    from agents import grok_bot

    if not grok_bot.enabled():
        return None
    text = await grok_bot.find_policy(retailer)
    if not text:
        return None, True
    return parse_policy_json(retailer, text), False


async def discover_published_policy(retailer: str) -> RetailerPolicy:
    """Ask Gemini and Grok, separately, for a published price-adjustment policy."""
    gemini, grok = await asyncio.gather(_gemini_find(retailer), _grok_find(retailer))
    findings: list[tuple[str, RetailerPolicy | None]] = []
    failures = 0
    explicit_no = False
    checks: list[tuple[str, tuple[RetailerPolicy | None, bool] | None]] = [("Gemini", gemini), ("Grok", grok)]
    for name, result in checks:
        if result is None:
            continue
        policy, failed = result
        if failed:
            failures += 1
            continue
        if policy is not None and stated_window_days(policy) is None:
            explicit_no = True
        if policy is not None and not policy.window_days:
            days = stated_window_days(policy)
            if days:
                policy = policy.model_copy(update={"window_days": days})
        if not _usable(policy):
            findings.append((name, None))
            continue
        verdict = await page_states_price_policy(policy.policy_url or "", policy.window_days)
        if verdict is False or (verdict is None and name != "Grok"):
            # A readable page that talks about something else is a bad citation. An unread page
            # is accepted only from Grok, which actually searched for it.
            logger.info("%s cited %s but it could not be confirmed on the page", name, policy.policy_url)
            findings.append((name, None))
            continue
        findings.append((name, policy))
    if not any(_usable(policy) for _, policy in findings):
        # A cited page that doesn't say this is not proof the retailer has no policy.
        if explicit_no and failures == 0:
            found = combine_policy_findings(retailer, findings, failures=0)
        else:
            found = unset_policy(retailer)
    else:
        found = combine_policy_findings(retailer, findings, failures=failures)
    logger.info(
        "Policy lookup for %s: window=%s url=%s",
        retailer, found.window_days, found.policy_url,
    )
    return found


async def get_policy(retailer: str) -> RetailerPolicy:
    """Return the policy for `retailer`.

    Known retailers come from their published pages. Anyone else is looked up by Gemini and Grok
    when those APIs are on. Mock mode, and a lookup that never gets an answer, return a no-window
    policy so eligibility can try again later. L2 caches the result.
    """
    known = _known_policy(retailer)
    if known is not None:
        return known
    if get_settings().mock_mode or not get_settings().gemini_api_key:
        return unset_policy(retailer)
    return await discover_published_policy(retailer)


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
