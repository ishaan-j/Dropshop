"""HTML for Harbor & Co, the demo retailer DropShop operates itself."""

from __future__ import annotations

from app.services.catalog import POLICY_TEXT, PRODUCTS, product_url


def layout(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{title}</title>
  <style>
    body {{ font-family: Georgia, serif; margin: 0; background: #f4f0e6; color: #221e18; }}
    main {{ max-width: 720px; margin: 0 auto; padding: 32px 20px 64px; }}
    .banner {{ background: #3f2f16; color: #f8f1e4; padding: 10px 16px; font-family: sans-serif; font-size: 14px; }}
    a {{ color: #0f6e56; }}
    input, textarea {{ width: 100%; padding: 10px; margin: 6px 0 14px; box-sizing: border-box; }}
    button {{ background: #0f6e56; color: white; border: 0; padding: 12px 16px; cursor: pointer; }}
    .price {{ font-size: 28px; }}
  </style>
</head>
<body>
  <div class="banner">DropShop demo retailer. These prices and this policy are not from a live store.</div>
  <main>{body}</main>
</body>
</html>"""


def home() -> str:
    cards = []
    for product_id, item in PRODUCTS.items():
        cards.append(
            f"<p><a href='{product_url(product_id)}'>{item['product_name']}</a> "
            f"— demo catalog ${item['current_cents'] / 100:.2f}"
            f"{' · Final Sale' if item['final_sale'] else ''}</p>"
        )
    body = "<h1>Harbor &amp; Co</h1><p>A storefront that exists only inside DropShop.</p>" + "".join(cards)
    body += "<p><a href='/demo/retailer/policy'>Price adjustment policy</a> · <a href='/demo/retailer/claim'>Claim form</a></p>"
    return layout("Harbor & Co", body)


def product(product_id: str) -> str | None:
    item = PRODUCTS.get(product_id)
    if not item:
        return None
    sale = "<p><strong>Final Sale.</strong> This item is excluded from price adjustments.</p>" if item["final_sale"] else ""
    body = (
        f"<h1>{item['product_name']}</h1>"
        f"<p class='price'>${item['current_cents'] / 100:.2f}</p>"
        "<p>Source: demo catalog. This number is not scraped from another retailer.</p>"
        f"{sale}"
        f"<p>Product ID: {product_id}</p>"
    )
    return layout(item["product_name"], body)


def policy() -> str:
    return layout("Harbor & Co policy", f"<h1>Price adjustment policy</h1><pre>{POLICY_TEXT}</pre>")


def claim_form() -> str:
    return layout(
        "Harbor & Co claim",
        """
        <h1>Price adjustment form</h1>
        <p>Submitting here tells the demo retailer, not a live merchant.</p>
        <form id="claim-form">
          <label>Order number <input id="order_number" name="order_number" required /></label>
          <label>Product <input id="product_name" name="product_name" required /></label>
          <label>Price paid <input id="price_paid" name="price_paid" required /></label>
          <label>Current price <input id="current_price" name="current_price" required /></label>
          <label>Requested difference <input id="refund_amount" name="refund_amount" required /></label>
          <label>Message <textarea id="message" name="message"></textarea></label>
          <button type="submit" id="submit-claim">Submit price adjustment</button>
        </form>
        <p id="confirmation" hidden></p>
        <script>
          document.getElementById("claim-form").addEventListener("submit", async (event) => {
            event.preventDefault();
            const body = {
              order_number: document.getElementById("order_number").value,
              product_name: document.getElementById("product_name").value,
              price_paid: document.getElementById("price_paid").value,
              current_price: document.getElementById("current_price").value,
              refund_amount: document.getElementById("refund_amount").value,
              message: document.getElementById("message").value
            };
            const response = await fetch("/demo/retailer/submissions", {
              method: "POST",
              headers: {"Content-Type": "application/json"},
              body: JSON.stringify(body)
            });
            const payload = await response.json();
            const note = document.getElementById("confirmation");
            note.hidden = false;
            note.textContent = payload.detail || "Request finished.";
            if (payload.accepted && payload.id) note.dataset.submissionId = payload.id;
          });
        </script>
        """,
    )
