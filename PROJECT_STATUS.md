# DropShop project status

Updated 14 Nov 2026. This file describes the code in the repo, not a plan.

## Architecture

Next.js talks to a FastAPI app. The API owns agent runs, eligibility rules, and external calls. MongoDB is the record store when it connects. TimescaleDB is the price store when it connects. If the default localhost databases are down and `MOCK_MODE=true`, records stay in memory and are labeled demo. A remote database that fails is reported as an error and is not replaced with memory.

The product name in the UI is DropShop. The existing database name `dropshot` is unchanged so the Docker Compose file still matches.

## Completed

- Landing page, dashboard, purchases, purchase detail, opportunities, agent center, activity, vault, and settings.
- Session tokens. Each browser gets its own user id. Purchases are filtered by that id.
- Labeled Harbor & Co demo scenario: three sample emails, catalog prices, a 14-day policy, one eligible claim, one Final Sale exclusion, one expired window.
- Deterministic eligibility. Gemini cannot flip the decision.
- Receipt extraction that drops any field not present in the source text.
- Price observations with a source. Receipt prices are `purchase_record`, not treated as a market check.
- Claim preparation. Approval is required. Only Harbor & Co can be automated, and only against this app's demo form.
- Playwright bot for that form. If the browser is missing, the claim stays unsubmitted.
- Nessie client for the documented customer endpoints. Sandbox deposits are matched only when the description contains `dropshop-claim:{id}` and the amount matches.
- Solana Devnet RPC health, balance read, and transfer verification. No Anchor program is deployed. Unconfirmed signatures are not stored as success.
- Gmail readonly OAuth structure. Tokens are encrypted and are not returned to the browser.
- Sentient OS: optional read of order-like Markdown in `~/Sentient OS - Knowledge Base`. It does not orchestrate the agents.
- Server-sent events for agent events that the backend actually emits.
- 23 backend tests passed on Python 3.9.6. `next build` succeeded.
- Browser pass on 14 Nov 2026: landing, dashboard demo, purchases search, opportunities, purchase chart, agent center, activity, vault, and settings. Solana Devnet `getHealth` returned `ok` from the running API. Approving the bag claim returned "Nothing was submitted. Playwright is not installed." and left the claim awaiting approval.

## In progress

Nothing is mid-edit. Live credentials are the remaining work.

## Blocked

| Integration | Status | Why | What you need to provide |
|---|---|---|---|
| Gemini | Key accepted | Auth key is in `.env`. `gemini-2.5-flash` is closed for this account. `gemini-3.8-flash` timed out under load. `gemini-3.1-flash-lite` generateContent returned `pong`. | None for the key. The dashboard stays "not connected" until an agent run in the app records a success. |
| MongoDB Atlas | Not connected | Nothing is listening on localhost, and no Atlas URI is set. | An Atlas connection string. |
| Tiger Data | Not connected | Docker is not installed, so Timescale is not running. No Tiger Cloud URL is set. | Docker, or a Tiger Cloud service URL. |
| Gmail | Not connected | No OAuth client. | Google Cloud OAuth client id and secret, redirect `http://localhost:8000/integrations/gmail/callback`, scope `gmail.readonly`. |
| Nessie | Sandbox, empty | Key is in `.env`. `GET /customers` over HTTPS returned an empty list. HTTP port 80 does not connect. | Create a sandbox account from Settings when you want deposits to reconcile. |
| Solana vault deposit | Address set, balance 0 | Devnet `getHealth` is ok. `7RacYpwoNQQGx59HXqMtzXtcqxsjTPqquvqQMy4c1T5q` reads as 0 lamports. No transfer has been signed. | Phantom on Devnet, plus faucet SOL, then authorize a deposit in the vault page. |
| Sentient OS | Not connected | The knowledge folder is not on this Mac, and the app is not installed. There is no cloud orchestration SDK in the project docs. | `brew install --cask sentient-os-labs/tap/sentient-os`, then opt in under Settings. |
| Playwright browsers | Not installed in this environment | `playwright` package and Chromium were not installed, so approval keeps the claim unsubmitted. | `pip install playwright` and `playwright install chromium` inside `backend/.venv`. |
| Vultr | Not deployed | No host, and Docker is not available locally. | A Vultr instance if you want it hosted. Do not claim it is deployed. |
| GoDaddy Registry | Not registered | The MLH prize is for registering a domain. No domain was purchased. | Register one through the sponsor flow at https://www.tech.study/. A name in the README does not qualify. |

## Integration modes in the product

- **Live:** Gmail after a token is stored. Sentient only after the folder exists and the user opts in. MongoDB Atlas when that host answers.
- **Sandbox:** Nessie. Solana Devnet. Local MongoDB or local TimescaleDB, which are labeled as local rather than Atlas or Tiger Cloud.
- **Demo:** Harbor & Co emails, catalog prices, demo refunds, demo earmarks, and in-memory storage when localhost databases are down.
- **Not connected:** missing keys, missing vault address, missing Sentient folder.
- **Error:** a configured remote service that fails. The app does not swap that failure for demo data.

## Tests

`cd backend && .venv/bin/python -m pytest -q` → 23 passed.

Covered: price difference, windows, eligibility, exclusions, duplicates, claim transitions, deposit matching, allocation limits, extraction scrubbing, demo scenario labels, user isolation, scan refusing to fake Gmail, approval without a browser, fake signatures, and demo refunds.

Called successfully: Devnet `getHealth`, Nessie `GET /customers` (empty list), Gemini `gemini-3.1-flash-lite` generateContent. Not run against credentials: Gmail, Atlas, Timescale, a Devnet transfer, Playwright, Sentient folder.

## Known limits

- One API process. Sessions and Gmail OAuth state are in memory unless `SESSION_SECRET` is set and Mongo is up. Restarting the API drops in-memory demo data.
- Python on this machine is 3.9.6. `eval_type_backport` is installed so Pydantic can read `X | Y` annotations. Docker uses Python 3.12.
- Notification toggles are stored. Nothing sends email.
- Redis workers are optional. The API runs the agents inline.
- The old mock file invented Best Buy prices. It is retired.

## Demo readiness

The labeled demo can be run from the dashboard without credentials. Say these sentences out loud:

1. Sample emails, not Gmail.
2. Harbor & Co catalog prices, not a scraped retailer.
3. The scarf is cheaper and still ineligible because it is Final Sale.
4. The lamp is cheaper and expired.
5. Approval does not submit until Playwright is installed, and even then it submits only to the demo form.
6. A demo refund is not a bank deposit.
7. Solana is a separate signature on Devnet.

## HackUMass prize notes

Sponsor prizes still have to be opted in on Devpost. Using a library is not the same as winning the category.

- Gemini: meaningful once a key is present. The call site is real.
- MongoDB Atlas and Tiger Data: meaningful once those URLs connect. The queries are real.
- Nessie: meaningful once a key is present. Endpoints follow the published customer API.
- Solana: a verified Devnet transfer is the bar. No program id is claimed.
- Sentient OS: the documented integration is the local knowledge folder. DropShop's own orchestrator is not Sentient OS.
- Vultr and GoDaddy: not claimed.
- SpaceXSI / Cursor + Grok Bot raffle: this repo was built in Cursor. A Grok Bot automation is not wired in. Do not claim that raffle unless you add one and describe it.
