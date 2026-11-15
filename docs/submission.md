# Submission notes

Working notes for the hackathon submission: what to check first, a draft description, the Grok Bot
routine, and a demo script. Everything here should stay true to what the app actually does, so
check the "live or simulated" table before you paste anything.

## Before you submit
- [ ] **Cursor section written by the team.** The Make it Legendary raffle asks for Cursor as the core
      AI coding agent, described in the project description. Only the team knows how Cursor was used,
      so that paragraph is a blank below. Don't submit it empty, and don't claim more than happened.
- [ ] **Grok Bot automation created** in a Grok Bot account (see "Grok Bot routine"). The code in this
      repo calls the xAI API, which is not the Grok Bot product. Confirm with the organizers what counts.
- [ ] **Raffle opt-in** ticked on the submission form.
- [ ] **Solana wallet funded**, so vault records are real devnet transactions (`python -m finance.solana_setup`).
- [ ] **Sponsor claims match the table below.** Tiger Data and MongoDB Atlas are not integrated until
      Layer 4 is built; Sentient OS has not run on a real Mac; nothing is deployed to Vultr yet.
- [ ] Run the demo script once end to end on the machine you'll present from.

## Live or simulated (as of 2026-11-14)
| Technology | Its job | State with `MOCK_MODE=false` |
|---|---|---|
| Gemini API | Reads receipts, judges eligibility, writes the claim explanation, extracts changed policies | **Live** |
| Grok (xAI API) | Drafts the claim message the bot submits; reviews retailer policy pages for changes | **Live** |
| Grok Bot (the product) | Would browse retailer policy pages and send them to `POST /automations/policy-page` | **Not set up.** Endpoint is ready; the bot has to be created |
| Playwright | Files the claim on the demo store's price-adjustment form, with screenshots | **Live**, on our own demo store, not a real retailer |
| Capital One Nessie | Confirms a purchase against a card charge; the refund lands as a deposit | **Live** against the sandbox |
| Solana devnet | Records each recovered refund on chain | **Ready, not yet used.** Needs a funded wallet; until then entries are marked simulated |
| Anchor program | The vault as a custom program | **Source only**, never compiled or deployed |
| Sentient OS | Finds purchases in its on-device knowledge base | **Untested.** Reader follows the README; the demo uses sample receipts |
| Tiger Data / TimescaleDB | Price history | **Not integrated** (Layer 4). Prices are held in memory |
| MongoDB Atlas | Purchases, claims, activity | **Not integrated** (Layer 4). State is held in memory and resets on restart |
| Vultr | Hosting | **Not deployed.** Docker files are written but have never been built |
| Price source | Current prices | Read from the product page for purchases with a URL; the demo items drop on cue |

## Project description (draft)
> **Dropshot: your purchases keep getting cheaper. Now so do you.**
>
> Retailers will refund the difference when something you bought drops in price, but only if you notice
> inside a short window and file a claim. Dropshot does that for you. It finds your purchases from receipts,
> watches their prices, and when one drops inside the retailer's price-adjustment window, Gemini checks the
> retailer's policy and decides whether you qualify and for how much. You approve the drafted claim with one
> click. Grok writes the claim message, a Playwright bot files it on the retailer's price-adjustment form, the
> refund is detected as a deposit in a Capital One Nessie account, and the recovered amount is recorded in a
> savings vault on Solana devnet.
>
> **How we used each technology:** _trim this list to the rows marked Live in the table above._
> - **Gemini API:** receipt extraction, eligibility decisions against the retailer policy, the plain-language
>   explanation of each claim, and re-reading a policy when it changes. Deterministic checks run first, and the
>   refund amount is always computed in code, never by the model.
> - **Grok:** drafts the claim message (checked against the claim's facts before it is used), and reviews
>   retailer policy pages so a shortened refund window is caught before it costs a user a claim.
> - **Playwright:** fills in and submits the claim form, and screenshots each step into the activity feed.
> - **Capital One Nessie:** confirms a discovered purchase against a card charge and detects the refund deposit.
> - **Solana:** every recovered refund is a devnet transaction the dashboard links to.
>
> **Built with Cursor:** _to be written by the team: how Cursor was used as the core coding agent._
>
> **Grok Bot automation:** _describe the bot once it exists: what it checks, how often, and what it sends
> to Dropshot. See the routine below._

## Grok Bot routine
Grok Bot is SpaceXAI's hosted agent product. Retailer policy pages often block scripts, which is exactly
where a browsing agent helps, so the routine below gives it a real job: fetch the pages our backend can't.
This was written without access to Grok Bot, so adjust it to what the product can actually do.

**Needs first:** the API reachable from the internet (deploy it, see `infra/LAYER.md`), `MOCK_MODE=false`,
and `AUTOMATION_TOKEN` set to a long random string in `.env`.

**Brief to give the bot:**
> Every night, check three retailer price-adjustment policies for Dropshot.
> For each retailer, open the page, copy the full text of the policy, and send it to Dropshot with a POST
> request to `<PUBLIC_API_URL>/automations/policy-page`, with the header
> `Authorization: Bearer <AUTOMATION_TOKEN>` and a JSON body
> `{"retailer": "<name>", "page_text": "<the policy text>", "source_url": "<the page URL>"}`.
> Then tell me which retailers changed: the response's `changed` and `note` fields say so.
> - Best Buy: https://www.bestbuy.com/site/help-topics/price-match-guarantee/pcmcat290300050002.c
> - Target: https://www.target.com/c/price-match-guarantee/-/N-4tdkg
> - Amazon: https://www.amazon.com/gp/help/customer/display.html?nodeId=GQ6N6QGZ9FSS7JYM

If the bot can only use a browser, it can make the same call from the API's own page at `<PUBLIC_API_URL>/docs`.
A changed policy shows up in the activity feed and is used for every eligibility check after that.

## Demo script (about 3 minutes)
Setup: `MOCK_MODE=false` and `PLAYWRIGHT_HEADLESS=false` in `.env`, then start the backend and the frontend.
The sidebar should say "Live backend". All the controls are under **Demo controls** in the top bar.

1. **Dashboard.** Purchases being watched and $82.50 already recovered.
2. **Scan for receipts.** About 15 seconds later two purchases appear, each confirmed against a Nessie card charge.
3. **Trigger a price drop.** The AirPods fall 15%. The activity feed shows the drop, "Eligible: $37.50 back",
   and a drafted claim.
4. **Claims → Approve and file.** A browser opens and the bot fills in the demo store's form. The claim
   dialog then shows the screenshot of what was submitted.
5. **Refund and vault.** A few seconds later the refund lands in Nessie and the claim reaches
   "Savings vault credited". With a funded wallet, open the signature on the Savings Vault page in Solana Explorer.
6. **Reset backend demo** before the next run.

If something stalls, `GET /health` on the API shows which systems are live or being covered by a simulation.
