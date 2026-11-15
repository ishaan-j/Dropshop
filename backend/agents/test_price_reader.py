"""Run: cd backend && python -m pytest agents/test_price_reader.py  (offline; pages are inline HTML)."""

import asyncio

import httpx
import pytest

from agents import price_reader

JSON_LD_PRODUCT = """
<html><head>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[]}</script>
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "Product", "name": "Sony WH-1000XM6",
 "offers": {"@type": "Offer", "price": "349.99", "priceCurrency": "USD"}}
</script></head><body>$399.99 was the old price</body></html>
"""
JSON_LD_GRAPH = """
<script type='application/ld+json'>{"@graph": [{"@type": "WebPage"},
 {"@type": ["Product", "Thing"], "offers": [{"@type": "Offer", "price": 1299.0}, {"price": 1399}]}]}</script>
"""
AGGREGATE = '<script type="application/ld+json">{"@type":"Product","offers":{"@type":"AggregateOffer","lowPrice":"1,049.50"}}</script>'
META = '<meta property="product:price:amount" content="129.99"><meta property="product:price:currency" content="USD">'
ITEMPROP = '<span content="24.5" itemprop="price">$24.50</span>'


@pytest.fixture(autouse=True)
def no_backoff():
    price_reader._blocked_until.clear()
    yield
    price_reader._blocked_until.clear()


@pytest.mark.parametrize(
    "html, cents",
    [
        (JSON_LD_PRODUCT, 34999),
        (JSON_LD_GRAPH, 129900),
        (AGGREGATE, 104950),
        (META, 12999),
        (ITEMPROP, 2450),
        ("<html><body><p>Now only $19.99!</p></body></html>", None),  # no structured data: don't guess
        ('<script type="application/ld+json">{not json</script>', None),
        ('<script type="application/ld+json">{"@type":"Product","offers":{"price":"0"}}</script>', None),
    ],
)
def test_extract_price(html, cents):
    assert price_reader.extract_price_cents(html) == cents


def test_number_formats():
    assert price_reader._to_cents("$1,299.00") == 129900
    assert price_reader._to_cents("349,99") == 34999  # decimal comma
    assert price_reader._to_cents("1,299") == 129900  # thousands separator
    assert price_reader._to_cents(True) is None and price_reader._to_cents("call us") is None


def test_fetch_reads_the_page_and_backs_off_after_a_failure():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.host)
        assert "Dropshot-PriceWatch" in request.headers["user-agent"]  # identifies itself honestly
        if request.url.host == "shop.test":
            return httpx.Response(200, text=JSON_LD_PRODUCT)
        return httpx.Response(403, text="Access denied")

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            assert await price_reader.fetch_price_cents("https://shop.test/p/1", client=client) == 34999
            assert await price_reader.fetch_price_cents("https://blocked.test/p/1", client=client) is None
            assert await price_reader.fetch_price_cents("https://blocked.test/p/2", client=client) is None
            assert await price_reader.fetch_price_cents("not a url", client=client) is None

    asyncio.run(scenario())
    assert calls == ["shop.test", "blocked.test"]  # the blocked host was only asked once
