"""Generate the human-readable explanation + form text for a claim."""

from app.models import EligibilityResult, Purchase


async def explain(purchase: Purchase, result: EligibilityResult) -> str:
    """TODO(L3): short, friendly explanation shown on the claim card in the dashboard
    (e.g. 'Best Buy matches its own lower price within 15 days… you're owed $50.00')."""
    raise NotImplementedError


async def form_message(purchase: Purchase, result: EligibilityResult) -> str:
    """TODO(L3): the message the bot pastes into the retailer's claim/chat form."""
    raise NotImplementedError
