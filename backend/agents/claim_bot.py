"""Playwright bot that submits a price-adjustment claim on a retailer site, only after user approval.

Demo strategy: real retailers will block automation, so build against our own mock retailer page
(price-adjustment form) for the live demo, and keep real-retailer flows as stretch goals.
Take a screenshot at every step; L2 attaches them to AgentEvents for the activity feed.
"""

from app.config import get_settings
from app.models import Claim, Purchase

settings = get_settings()


async def submit(claim: Claim, purchase: Purchase, message: str) -> list[str]:
    """Fill + submit the claim form. Returns screenshot file paths in step order.

    TODO(L3):
      from playwright.async_api import async_playwright
      async with async_playwright() as p:
          browser = await p.chromium.launch(headless=settings.playwright_headless)
          page = await browser.new_page()
          await page.goto(<mock retailer claim URL>)
          ... fill order number, product, new price, message ...
          await page.screenshot(path=...)
    """
    raise NotImplementedError
