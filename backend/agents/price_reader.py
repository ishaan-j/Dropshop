"""Read a product's current price from its public product page.

Most retail product pages publish the price as structured data for search engines: a schema.org
`Product` in JSON-LD, or `product:price:amount` / `itemprop="price"` tags. This reads that, so it
needs no per-retailer scraper and no model call.

It identifies itself honestly and does not try to get around bot protection: a retailer that
blocks automated requests simply yields no price, and the caller keeps its last known one. A host
that fails is left alone for a while (`HOST_BACKOFF_SECONDS`).
"""

from __future__ import annotations

import json
import logging
import re
import time
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = "Dropshot-PriceWatch/0.1 (price-adjustment tracker; hackathon project)"
TIMEOUT = httpx.Timeout(8.0, connect=4.0)
MAX_PAGE_BYTES = 3_000_000
HOST_BACKOFF_SECONDS = 30 * 60

_blocked_until: dict[str, float] = {}  # host -> monotonic time before which we don't retry

_JSON_LD_RE = re.compile(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.S | re.I)
_META_RES = [
    re.compile(r"<meta[^>]+(?:property|name)=[\"'](?:product:price:amount|og:price:amount)[\"'][^>]*content=[\"']([^\"']+)[\"']", re.I),
    re.compile(r"<meta[^>]+content=[\"']([^\"']+)[\"'][^>]*(?:property|name)=[\"'](?:product:price:amount|og:price:amount)[\"']", re.I),
    re.compile(r"<[^>]+itemprop=[\"']price[\"'][^>]*content=[\"']([^\"']+)[\"']", re.I),
    re.compile(r"<[^>]+content=[\"']([^\"']+)[\"'][^>]*itemprop=[\"']price[\"']", re.I),
]


def _to_cents(value) -> int | None:
    """'1,299.00', '$349.99', 349.99 or 349 → cents. None if it isn't a positive price."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        cleaned = re.sub(r"[^\d.,]", "", str(value))
        if not cleaned:
            return None
        if "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(",", "")  # 1,299.00
        elif "," in cleaned:
            # 1,299 is a thousands separator; 349,99 is a decimal comma
            cleaned = cleaned.replace(",", "") if re.search(r",\d{3}$", cleaned) else cleaned.replace(",", ".")
        try:
            number = float(cleaned)
        except ValueError:
            return None
    cents = round(number * 100)
    return cents if cents > 0 else None


def _is_type(node: dict, name: str) -> bool:
    kind = node.get("@type")
    return name in kind if isinstance(kind, list) else kind == name


def _offer_price(offers) -> int | None:
    for offer in offers if isinstance(offers, list) else [offers]:
        if not isinstance(offer, dict):
            continue
        spec = offer.get("priceSpecification")
        candidates = [offer.get("price"), offer.get("lowPrice")]
        if isinstance(spec, dict):
            candidates.append(spec.get("price"))
        for candidate in candidates:
            cents = _to_cents(candidate)
            if cents:
                return cents
    return None


def _product_price(node) -> int | None:
    """Depth-first search of a JSON-LD document for a Product's offer price."""
    if isinstance(node, list):
        for item in node:
            found = _product_price(item)
            if found:
                return found
        return None
    if not isinstance(node, dict):
        return None
    if _is_type(node, "Product") and "offers" in node:
        found = _offer_price(node["offers"])
        if found:
            return found
    for key in ("@graph", "mainEntity", "itemListElement", "item"):
        found = _product_price(node.get(key))
        if found:
            return found
    return None


def extract_price_cents(html: str) -> int | None:
    """The product's price from a page's structured data, in cents. None if the page has none."""
    for block in _JSON_LD_RE.findall(html):
        try:
            found = _product_price(json.loads(block.strip()))
        except (ValueError, TypeError):
            continue
        if found:
            return found
    for pattern in _META_RES:
        match = pattern.search(html)
        if match:
            cents = _to_cents(match.group(1))
            if cents:
                return cents
    return None


async def fetch_price_cents(url: str, *, client: httpx.AsyncClient | None = None) -> int | None:
    """Fetch a product page and read its price. Returns None when the page can't be read: blocked,
    slow, no structured price, or a host that failed recently."""
    host = urlparse(url).netloc.lower()
    if not host or time.monotonic() < _blocked_until.get(host, 0.0):
        return None
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True)
    try:
        response = await client.get(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
        response.raise_for_status()
        price = extract_price_cents(response.text[:MAX_PAGE_BYTES])
        if price is None:
            logger.info("No structured price on %s", host)
            _blocked_until[host] = time.monotonic() + HOST_BACKOFF_SECONDS
        return price
    except Exception as exc:
        logger.info("Couldn't read a price from %s (%s); leaving it alone for a while", host, type(exc).__name__)
        _blocked_until[host] = time.monotonic() + HOST_BACKOFF_SECONDS
        return None
    finally:
        if own_client:
            await client.aclose()
