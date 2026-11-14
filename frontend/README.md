# DropShop frontend

You shop. Prices drop. You save.

This is the DropShop web app: a Next.js dashboard for recovering money when a price drops after a purchase. It runs entirely in the browser with sample data, including a six-stage live demo. No API keys, email account, bank, or wallet are required.

The monorepo backend still uses the team name Dropshot in shared docs. This app is DropShop.

## Run it

From this folder:

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Present the demo

1. On the landing page, choose **Start Saving**.
2. Choose **Skip to Demo**, or connect email, bank, and vault. Connections are simulated.
3. On the dashboard, choose **Run Live Demo**.
4. The sequence takes about 27 seconds:
   - Sentient OS finds a Nike Air Max 270 receipt for $160.
   - Tiger Data drops the price to $120.
   - Gemini marks a $40 refund eligible.
   - Grok Bot fills a simulated retailer form and submits it.
   - Nessie shows a $40 bank refund.
   - Solana records a $40 vault deposit.
5. Minimize the panel to watch the dashboard, tracker, claims, activity, and vault update.
6. Pause, resume, replay, or reset from the panel. Replay removes the Nike refund before running again, so the $40 is not counted twice.
7. **Reset demo** in Settings restores the original sample account.

The sample account starts at **$60 recovered**, **$171 in potential refunds**, and **$60 in the vault**. After a full demo those become **$100 recovered** and **$100 in the vault**. Potential returns to **$171** because the Nike refund is confirmed, not still potential.

## What the numbers mean

Totals are calculated from the purchases, claims, and vault deposits. They are not typed in by hand.

- **Recovered** is the sum of claims whose refund has been confirmed.
- **Potential** is the price gap on purchases that qualify and have not been refunded, declined, or expired.
- **Vault balance** is the sum of confirmed vault deposits.
- **Pending deposits** are confirmed refunds that are not in the vault yet. That is the gap you see between the bank stage and the vault stage.

## Connect the backend

Copy `.env.example` to `.env.local` when you want the real API:

```bash
NEXT_PUBLIC_DATA_MODE=api
NEXT_PUBLIC_API_URL=http://localhost:8000
```

`demo` is the default and ignores the network. `api` loads purchases, claims, activity, prices, and savings from the contract in `docs/api-contract.md`.

The HTTP client is `src/lib/api.ts`. Screen actions go through `src/lib/services.ts`. The live demo keeps writing to the local ledger so it still works if the API is down.

| System | Where it connects |
| --- | --- |
| Sentient OS | `POST /purchases/scan` discovers receipts |
| Tiger Data | `GET /prices/:product_id` is the price history |
| Gemini | Eligibility runs in the backend worker. There is no public check route yet. |
| Grok Bot | `POST /claims/:id/approve` asks the bot to file |
| Nessie | Refund confirmation is server-side. The demo shows it locally. |
| Solana | `GET /savings` returns the vault balance and address |
| MongoDB | Purchases, claims, activity, and the user profile |

Do not put API keys, bank credentials, or wallet secrets in frontend code. The backend owns those.

## Scripts

```bash
npm run dev
npm run lint
npm run build
```
