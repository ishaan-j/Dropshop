"""Read a retailer policy we actually have. Unknown retailers are not invented."""

from __future__ import annotations

from datetime import datetime, timezone

from app.models import RetailerPolicy
from app.services.catalog import POLICY_PATH, POLICY_TEXT, PRODUCTS
from app.services.rules import parse_policy_text


class PolicyNotFound(LookupError):
    pass


async def get_policy(retailer: str) -> RetailerPolicy:
    if retailer != "Harbor & Co":
        raise PolicyNotFound(
            f"No verified price-adjustment policy is stored for {retailer}. "
            "DropShop will not guess one."
        )
    parsed = parse_policy_text(POLICY_TEXT)
    return RetailerPolicy(
        retailer=retailer,
        policy_url=POLICY_PATH,
        window_days=parsed["window_days"],
        conditions=["Item must still be offered in the Harbor & Co catalog."],
        exclusions=parsed["exclusions"],
        summary=(
            "Harbor & Co, the DropShop demo retailer, allows a price adjustment for "
            f"{parsed['window_days']} days except Final Sale items. This policy is not a live merchant policy."
            if parsed["window_days"] is not None
            else "The demo policy text did not contain a parseable window."
        ),
        source_text=POLICY_TEXT,
        verified_at=datetime.now(timezone.utc),
        data_origin="demo",
        parser="deterministic",
    )


def product_facts(product_id: str | None) -> dict | None:
    if not product_id:
        return None
    return PRODUCTS.get(product_id)
