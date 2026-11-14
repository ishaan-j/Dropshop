# Demo store claim form: contract between Layer 1 and Layer 3

Layer 3's Playwright bot (`backend/agents/claim_bot.py`) fills this page. URL: `RETAILER_CLAIM_URL`
(default `http://localhost:3000/demo-store/claim`). Elements are found by `data-testid`:

| data-testid | Element | Bot fills |
|---|---|---|
| `order-number` | input | order number |
| `product-name` | input | product name |
| `price-paid` | input | price paid, dollars, e.g. `399.99` |
| `current-price` | input | new lower price, dollars |
| `message` | textarea | claim message |
| `submit` | button | clicked once |
| `claim-confirmation` | any element | appears after submit (reference number text) |

Keep the fields on one page with no login or captcha. The bot waits up to 10 s for `claim-confirmation`.

- **Ready flag (optional):** if the `<form>` renders `data-ready="false"`, the bot waits until it is anything else
  before typing. The page sets it once its submit handler is attached, so a click can't beat hydration.
- **Required fields:** if the browser's own validation refuses a field (for example a `required` order number
  left empty), the bot stops at once and the claim fails with that field named in the activity feed.
