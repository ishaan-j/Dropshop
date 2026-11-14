"""Playwright bot that submits a price-adjustment claim on a retailer site, only after user approval.

Demo strategy: real retailers will block automation, so build against our own mock retailer page
(price-adjustment form) for the live demo, and keep real-retailer flows as stretch goals.
Take a screenshot at every step; L2 attaches them to AgentEvents for the activity feed.

Form contract the demo-store page (L1) must satisfy; see docs/demo-store-contract.md.
Elements are found by `data-testid`:
  order-number, product-name, price-paid, current-price  (inputs; current-price is in dollars)
  message                                                 (textarea)
  submit                                                  (button)
  claim-confirmation                                      (shown after submit; its text is the reference)
Optional: a form that renders `data-ready="false"` until its scripts are attached is waited for.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

from app.config import get_settings
from app.models import Claim, Purchase

SCREENSHOT_ROOT = Path("artifacts/claim_screenshots")
CONFIRMATION_TIMEOUT_MS = 10_000


class ClaimSubmissionError(RuntimeError):
    """The bot couldn't complete the form. `screenshots` holds whatever it captured so far."""

    def __init__(self, message: str, screenshots: list[str]):
        super().__init__(message)
        self.screenshots = screenshots


def _dollars(cents: int) -> str:
    return f"{cents / 100:.2f}"


# Server-rendered forms can be clicked before their script is attached; a page may flag that.
_FORM_READY_JS = "() => document.querySelector('form')?.dataset.ready !== 'false'"

# After submit: the first field the browser's own validation refused, as "Label: message".
_INVALID_FIELD_JS = """() => {
  const bad = document.querySelector('form :invalid');
  if (!bad) return null;
  const label = bad.closest('label')?.innerText?.split('\\n')[0]
    || bad.getAttribute('aria-label') || bad.name || bad.dataset.testid || 'A field';
  return `${label.trim()}: ${bad.validationMessage}`;
}"""


def _loop_cannot_start_browser() -> bool:
    """Playwright launches its driver as a subprocess. On Windows only the Proactor event loop can
    do that, and `uvicorn --reload` runs the app on a Selector loop."""
    return sys.platform == "win32" and not isinstance(asyncio.get_running_loop(), asyncio.ProactorEventLoop)


def _run_on_proactor_loop(coro):
    loop = asyncio.ProactorEventLoop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def submit(
    claim: Claim,
    purchase: Purchase,
    message: str,
    *,
    claim_url: str | None = None,
    screenshot_dir: Path | None = None,
) -> list[str]:
    """Fill + submit the claim form. Returns screenshot file paths in step order.

    Raises ClaimSubmissionError (carrying the screenshots taken so far) on failure so L2 can mark
    the claim `failed` and still show what happened. Runs headful when PLAYWRIGHT_HEADLESS=false,
    which is what the live demo uses.
    """
    run = _submit(claim, purchase, message, claim_url=claim_url, screenshot_dir=screenshot_dir)
    if _loop_cannot_start_browser():
        # Give the bot a thread with an event loop that can spawn the browser.
        return await asyncio.to_thread(_run_on_proactor_loop, run)
    return await run


async def _submit(
    claim: Claim,
    purchase: Purchase,
    message: str,
    *,
    claim_url: str | None,
    screenshot_dir: Path | None,
) -> list[str]:
    settings = get_settings()
    url = claim_url or settings.retailer_claim_url
    out = screenshot_dir or SCREENSHOT_ROOT / claim.id
    out.mkdir(parents=True, exist_ok=True)
    shots: list[str] = []

    async def snap(page, name: str) -> None:
        path = out / f"{len(shots) + 1:02d}_{name}.png"
        await page.screenshot(path=str(path), full_page=True)
        shots.append(str(path))

    new_price = purchase.price_paid_cents - claim.refund_cents

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=settings.playwright_headless, slow_mo=0 if settings.playwright_headless else 250
        )
        try:
            page = await browser.new_page(viewport={"width": 1280, "height": 900})
            page.set_default_timeout(CONFIRMATION_TIMEOUT_MS)
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_function(_FORM_READY_JS)
            await snap(page, "form_loaded")

            field = lambda tid: page.get_by_test_id(tid)  # noqa: E731
            await field("order-number").fill(purchase.order_number or "")
            await field("product-name").fill(purchase.product_name)
            await field("price-paid").fill(_dollars(purchase.price_paid_cents))
            await field("current-price").fill(_dollars(new_price))
            await field("message").fill(message)
            await snap(page, "form_filled")

            await field("submit").click()
            rejected = await page.evaluate(_INVALID_FIELD_JS)
            if rejected:  # say so now instead of waiting for a confirmation that can't come
                raise ValueError(f"the form rejected a field ({rejected})")
            confirmation = field("claim-confirmation")
            await confirmation.wait_for(state="visible", timeout=CONFIRMATION_TIMEOUT_MS)
            await snap(page, "confirmation")
            return shots
        except Exception as exc:
            try:
                await snap(page, "error")
            except Exception:
                pass
            raise ClaimSubmissionError(f"Claim submission failed: {exc}", shots) from exc
        finally:
            await browser.close()
