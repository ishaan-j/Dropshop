# Layer 1: Frontend

**Owner:** _TBD_ · **Stack:** Next.js (App Router) + React + TypeScript, Tailwind CSS, shadcn/ui, Recharts

## You own
The web app: dashboard, purchase cards, claim approval, AI activity feed, price-history and savings charts.

## You consume
The REST API in [`docs/api-contract.md`](../docs/api-contract.md). Types are in `src/types/index.ts` and the fetch helpers in `src/lib/api.ts`.
The backend serves **mock data** by default, so you can build the whole UI right away.

## Setup
```bash
npm install
npx shadcn@latest init        # pick defaults; then add components as needed:
npx shadcn@latest add card button badge table dialog sonner
npm run dev                   # http://localhost:3000  (backend at NEXT_PUBLIC_API_URL)
```

## First tasks
- [ ] Dashboard layout: savings header (`/savings`), purchase grid (`/purchases`), activity feed (`/activity`)
- [ ] Purchase card: product, paid vs. current price, days left in window, status badge
- [ ] Price history chart (Recharts line) from `/prices/{product_id}`, with a reference line at the price paid
- [ ] Claim card with the Gemini explanation and **Approve / Reject** buttons (`POST /claims/{id}/approve`)
- [ ] Activity feed that polls every ~3s and shows screenshot thumbnails when `screenshot_url` is set
- [ ] Savings panel: total recovered, vault balance, Solana Explorer link
- [ ] Stretch: the **mock retailer claim page** the bot submits to in the demo (coordinate with L3), e.g. `src/app/demo-store/`
