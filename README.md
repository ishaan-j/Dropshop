# DropShop

DropShop finds price drops you would have missed, checks whether a retailer's adjustment window actually applies, and helps you recover the difference. You approve every claim. A Solana transfer is a separate step you sign.

A lower price is not a refund. Demo data is labeled demo. A missing API key is shown as not connected.

## How a run works

1. **Purchase.** Gmail (readonly), an opted-in Sentient OS note, a purchase you type, or the labeled demo emails.
2. **Monitor.** The price agent records an observation with a source. The only source shipped in this repo is the Harbor & Co demo catalog.
3. **Detect.** The latest market observation is compared with the price on the receipt.
4. **Verify.** Window, exclusions, and source are applied in code. Gemini may explain. It cannot overrule.
5. **Claim.** A packet is prepared. Nothing is submitted until you approve. Automation is allowed only for the in-app demo retailer.
6. **Recover.** A Nessie sandbox deposit can be matched, or you can record an explicitly labeled demo refund.
7. **Save.** You can earmark recovered dollars, then sign a Devnet SOL transfer in your own wallet.

## Stack

| Piece | Role |
|---|---|
| Next.js, React, TypeScript, Tailwind, Recharts | UI |
| FastAPI, Pydantic | API and orchestration |
| Gemini (`google-genai`) | Structured extraction and explanation when a key is set |
| MongoDB | Purchases, claims, events, approvals |
| TimescaleDB / Tiger Data | Price observations and drop events |
| Gmail API | Readonly order-mail discovery |
| Nessie | Sandbox accounts, purchases, deposits |
| Solana Devnet JSON-RPC | Balance and transfer verification |
| Playwright | Fills the Harbor & Co claim form |
| Sentient OS | Optional read of the local Markdown knowledge folder |

Cursor is the editor used to build this repo. It is not a runtime dependency.

## Run it locally

Python 3.9+ works. 3.12 is what the Docker image uses. Node 20+ for the frontend.

```bash
cp .env.example .env

cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

cd ../frontend
npm install
npm run dev
```

Open http://localhost:3000. The dashboard button **Run labeled demo scenario** needs no keys.

Optional services:

```bash
docker compose up -d          # Redis + TimescaleDB
docker compose --profile local-mongo up -d
```

This machine did not have Docker when the app was built. Without it, Mongo and Timescale show as not connected and records stay in memory, labeled demo.

Playwright, once you want the approve button to submit the demo form:

```bash
cd backend && source .venv/bin/activate
pip install playwright
playwright install chromium
```

## Environment

Names and safe placeholders are in [`.env.example`](.env.example). Nothing secret belongs in git.

| Variable | If empty |
|---|---|
| `GEMINI_API_KEY` | Labeled emails use the deterministic parser. Other mail is not guessed. |
| `MONGODB_URI` | Localhost down + `MOCK_MODE=true` → memory. A remote URI that fails → error, no silent fallback. |
| `TIMESCALE_URL` | Same rule for prices. |
| `NESSIE_API_KEY` | Banking screens say not connected. |
| `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` | Connect button explains that OAuth is not configured. |
| `SOLANA_VAULT_ADDRESS` | Deposits are disabled. The RPC must be Devnet. |
| `SESSION_SECRET` | Tokens die when the API process restarts. |

## Tests

```bash
cd backend && .venv/bin/python -m pytest -q
cd frontend && npx tsc --noEmit && npx next build
```

See [TESTING.md](TESTING.md) for the demo script and what was not run.

## Docs

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [PROJECT_STATUS.md](PROJECT_STATUS.md)
- [TESTING.md](TESTING.md)
- API reference while the server is up: http://localhost:8000/docs

## Limits you should say out loud

- Harbor & Co is a demo store inside this app. Its prices and policy are not another retailer's.
- Sample emails are not Gmail.
- A Nessie match is sandbox data, not a retailer payment into a real account.
- Devnet SOL is not the refund.
- No Anchor program is deployed.
- Sentient OS is not orchestrating the four agents. It can supply notes from its knowledge folder.
- The app is not deployed on Vultr, and no GoDaddy domain is registered.

## Deploy

`infra/Dockerfile.api` builds the API. `docker-compose.yml` is the local data stack. `infra/docker-compose.prod.yml` is a starting point for a host. Do not describe the app as live on Vultr until a host answers `/health`.
