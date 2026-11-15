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
npm run dev                   # http://localhost:3000
```

The app runs in demo mode with no backend. Set `NEXT_PUBLIC_DATA_MODE=api` to use `NEXT_PUBLIC_API_URL`. See `README.md` for the live demo and the API seam.

## Shipped
- [x] Landing, onboarding, dashboard, tracker, claims, vault, AI activity, settings
- [x] Purchase cards, price history, claim approval, and savings chart
- [x] Six-stage live demo that updates the shared ledger without double-counting refunds
- [x] Typed client in `src/lib/api.ts` for the contract in `docs/api-contract.md`
