# Layer 3: AI and agentic intelligence

**Owner:** _TBD_ · **Stack:** Gemini API, Grok (xAI API), Sentient OS, Playwright

## You own
| Module | Job |
|---|---|
| `gemini_client.py` | Shared Gemini client: structured output (JSON schema → Pydantic), a model fallback chain, a mock fallback |
| `receipt_extractor.py` | Receipt email/photo → `ExtractedReceipt` |
| `policy_reader.py` | Retailer policy → `RetailerPolicy` (window, conditions). Demo policies are hardcoded; `summarize_policy_text` reads a real page |
| `eligibility.py` | Purchase + current price + policy → `EligibilityResult`. Deterministic checks first, Gemini only for the fuzzy conditions |
| `claim_writer.py` | The dashboard explanation, and the claim-form message (Grok drafts it; Gemini, then a template, are the fallbacks) |
| `grok_bot.py` | Grok through the xAI API: drafts the claim message, and reviews retailer policy pages for changes |
| `price_reader.py` | Reads a product's price from the structured data on its public page (no model call) |
| `sentient.py` | Purchase discovery from Sentient OS's Markdown knowledge base (with a fixture fallback) |
| `claim_bot.py` | Playwright: fill in and submit the claim form, screenshot each step |

## Contract
Functions take and return models from `app/models.py`. **Don't touch the database.** L2 persists whatever you return.
Every model call has an offline fallback, so `MOCK_MODE=true` makes no network calls.
Tests: `python -m pytest agents` from `backend/` (offline; the bot tests need `playwright install chromium`).

## Models and speed
- Gemini: `GEMINI_MODEL` then each of `GEMINI_FALLBACK_MODELS`, 4 s per attempt, the chain tried twice, 20 s overall,
  then the offline fallback. `gemini-3.5-flash-lite` and `gemini-3.1-flash-lite` answer in about 1 s but each failed
  about one call in four at the event (a 503, or a request that hangs), which is why the chain is tried twice. The
  full flash models were overloaded: 503s, or 18 s and more per answer.
- Grok: `XAI_MODEL=grok-4.7` answers in about 2 s. The `grok-4` alias took about 17 s.

## Status
- [x] `gemini_client.generate_structured`, live and mocked
- [x] 4 sample receipts in `agents/fixtures/`, all parsed
- [x] Policies for 3 demo retailers; `eligibility.check` with pre-checks plus Gemini
- [x] `claim_bot.submit` against the demo store page (`frontend/src/app/demo-store/claim`, contract in `docs/demo-store-contract.md`)
- [x] `price_reader` reads a real product page (verified on one Shopify store; Best Buy blocks automated requests)
- [ ] Sentient OS on a real Mac. The reader follows the README (a folder of Markdown notes at
      `~/Sentient OS - Knowledge Base/`), but it has never run against a real knowledge base, and the sponsor
      hasn't confirmed that reading it counts as the integration.

## Grok Bot and the raffle
"Grok Bot" is a SpaceXAI / Cursor product: hosted agents ("AI teammates") that work inside websites and apps.
It is **not** the xAI API. `grok_bot.py` here calls the xAI API (the Grok model), which is a real integration
but probably not what the Make it Legendary raffle means by "a Grok Bot automation".

To meet the raffle, someone with Grok Bot access has to create a bot and give it a job in this workflow.
The backend is ready for one: `POST /automations/policy-page` (enable it with `AUTOMATION_TOKEN`) takes a
retailer's policy page text, compares it with the stored policy, and updates eligibility if it changed.
A Grok Bot can browse the retailer sites that block our own fetches. The bot's brief is in `docs/submission.md`.
Confirm the exact requirement with the organizers.
