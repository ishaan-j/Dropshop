"""Harbor & Co is DropShop's own demo retailer.

Prices and the policy below are authored for this demo store. They are not
prices or policies of any other merchant.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

POLICY_PATH = "/demo/retailer/policy"

POLICY_TEXT = """Harbor & Co Price Adjustment Policy
Source: this page, operated by the DropShop demo retailer. This is not a policy of any other store.

Window: 14 days from the purchase date.
The purchase date counts as day 0. A request must be submitted before the window ends.

Refund amount: the difference between the price paid and the current Harbor & Co catalog price, excluding tax and shipping.

Eligible: items sold by Harbor & Co that are still offered at a lower catalog price.

Exclusions:
- Items marked Final Sale
- Prices from other retailers
- Prices that require a membership or a coupon code

How to claim: submit the Harbor & Co price-adjustment form with the order number, product name, price paid, and current price.
"""

PRODUCTS: dict[str, dict] = {
    "harbor:linen-weekender": {
        "retailer": "Harbor & Co",
        "product_name": "Linen Weekender Bag",
        "paid_cents": 12800,
        "current_cents": 9900,
        "days_ago": 6,
        "order_prefix": "HCO-10428",
        "final_sale": False,
    },
    "harbor:wool-scarf": {
        "retailer": "Harbor & Co",
        "product_name": "Wool Scarf",
        "paid_cents": 4800,
        "current_cents": 3600,
        "days_ago": 4,
        "order_prefix": "HCO-10455",
        "final_sale": True,
    },
    "harbor:ceramic-lamp": {
        "retailer": "Harbor & Co",
        "product_name": "Ceramic Table Lamp",
        "paid_cents": 8600,
        "current_cents": 7200,
        "days_ago": 30,
        "order_prefix": "HCO-09811",
        "final_sale": False,
    },
}


def order_number(product_id: str, user_id: str) -> str:
    prefix = PRODUCTS[product_id]["order_prefix"]
    return f"{prefix}-{user_id[-4:]}"


def product_url(product_id: str) -> str:
    return f"/demo/retailer/products/{product_id}"


def sample_email(product_id: str, user_id: str, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    item = PRODUCTS[product_id]
    purchased = (now - timedelta(days=item["days_ago"])).date().isoformat()
    price = f"{item['paid_cents'] / 100:.2f}"
    return (
        "From: orders@harborandco.demo\n"
        f"Subject: Your Harbor & Co order {order_number(product_id, user_id)}\n"
        "This is a DropShop demo sample email. It did not come from Gmail.\n"
        "\n"
        "Retailer: Harbor & Co\n"
        f"Order number: {order_number(product_id, user_id)}\n"
        f"Order date: {purchased}\n"
        f"Product: {item['product_name']}\n"
        f"Product ID: {product_id}\n"
        f"Product URL: {product_url(product_id)}\n"
        f"Price: ${price}\n"
    )


def demo_emails(user_id: str, now: datetime | None = None) -> list[dict]:
    return [
        {
            "product_id": product_id,
            "subject": f"Your Harbor & Co order {order_number(product_id, user_id)}",
            "body": sample_email(product_id, user_id, now),
        }
        for product_id in PRODUCTS
    ]
