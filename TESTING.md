# Testing

## Unit and API tests

From `backend/`, with the virtualenv:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
```

On this machine that command reported **23 passed** (Python 3.9.6).

The tests cover:

- price difference, adjustment windows, and time zones
- eligibility, including Final Sale and a closed window
- duplicate purchase keys
- claim state transitions and duplicate-claim blocking
- Nessie-style deposit matching and unmatched explanations
- savings allocation limits
- extraction that rejects values missing from the email
- the demo scenario labels, user isolation, and the refusal to treat a scan as Gmail
- approval when the browser is skipped: the claim stays unsubmitted
- a fake Solana signature is not stored
- a demo refund stays `data_origin: demo` and has no external id

`DROP_SKIP_BROWSER=1` and `DROP_SKIP_NETWORK=1` are set in `tests/conftest.py` so the suite does not launch Chromium or call Devnet.

## Frontend

```bash
cd frontend
npm install
npx tsc --noEmit
npx next build
```

`next build` succeeded after these pages were added.

## Not run here

These need credentials or services this machine does not have:

- Gemini with a real key
- Gmail consent
- Nessie sandbox
- MongoDB Atlas
- TimescaleDB / Tiger Cloud
- a signed Devnet transfer
- Playwright against the demo form
- a Sentient OS knowledge folder

## Repeatable demo

1. Start the API: `cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000`
2. Start the UI: `cd frontend && npm run dev`
3. Open http://localhost:3000 and go to the dashboard.
4. Click **Run labeled demo scenario**.
5. Confirm the banner says the rows are sample emails and Harbor & Co prices.
6. Open Purchases. The bag is eligible. The scarf is not, because it is Final Sale. The lamp is expired.
7. Open the bag's price chart. Points are labeled `purchase_record` or `demo_catalog`.
8. On Opportunities, approve the bag. Without Playwright installed, the note says nothing was submitted.
9. After `playwright install chromium`, approve again. The claim should move to submitted and name the demo retailer.
10. **Record demo refund** only if you want a labeled demo ledger entry. **Post Nessie sandbox deposit** only after a Nessie key and sandbox account exist.
11. The vault page stays separate. A demo earmark has no signature. A Devnet deposit appears only after the API verifies it.

## Failure behavior already coded

- Missing Gmail on Scan returns 409 and does not load sample mail.
- A remote Mongo or Timescale URL that fails returns 503 instead of memory data.
- Gemini output that names a dollar amount not in the source, or says "guaranteed", is discarded.
- A deposit with the right amount but without the claim marker is not matched.
- A Solana signature Devnet cannot confirm is rejected and not stored.
