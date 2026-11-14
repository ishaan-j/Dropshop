"""Playwright fills the DropShop demo retailer form. It does not open other retailers."""

from __future__ import annotations

import os
from pathlib import Path

from app.config import get_settings
from app.models import Claim, Purchase

SHOT_DIR = Path(__file__).resolve().parent / "screenshots"


class AutomationUnavailable(RuntimeError):
    pass


async def submit(claim: Claim, purchase: Purchase) -> dict:
    if os.getenv("DROP_SKIP_BROWSER") == "1":
        raise AutomationUnavailable("Browser automation is skipped in this process.")
    settings = get_settings()
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise AutomationUnavailable("Playwright is not installed.") from exc

    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    url = settings.public_base_url.rstrip("/") + "/demo/retailer/claim"
    names: list[str] = []
    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(headless=settings.playwright_headless)
        except Exception as exc:  # noqa: BLE001
            raise AutomationUnavailable(f"Could not launch Chromium: {exc.__class__.__name__}") from exc
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=15000)
            await page.fill("#order_number", purchase.order_number or "")
            await page.fill("#product_name", purchase.product_name)
            await page.fill("#price_paid", f"{(purchase.price_paid_cents / 100):.2f}")
            await page.fill("#current_price", f"{((purchase.current_price_cents or 0) / 100):.2f}")
            await page.fill("#refund_amount", f"{(claim.refund_cents / 100):.2f}")
            await page.fill("#message", claim.manual_packet or claim.explanation)
            filled = f"{claim.id}-filled.png"
            await page.screenshot(path=str(SHOT_DIR / filled))
            names.append(filled)
            await page.click("#submit-claim")
            await page.wait_for_selector("#confirmation[data-submission-id]", timeout=10000)
            submitted = f"{claim.id}-submitted.png"
            await page.screenshot(path=str(SHOT_DIR / submitted))
            names.append(submitted)
            submission_id = await page.get_attribute("#confirmation", "data-submission-id")
        finally:
            await browser.close()
    if not submission_id:
        raise AutomationUnavailable("The demo retailer page did not return a submission id.")
    return {"submission_id": submission_id, "screenshots": names}
