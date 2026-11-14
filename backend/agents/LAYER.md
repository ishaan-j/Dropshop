# Layer 3: AI and agentic intelligence

**Owner:** _TBD_ · **Stack:** Gemini API, Sentient OS, Playwright

## You own
| Module | Job |
|---|---|
| `gemini_client.py` | Shared Gemini client plus a structured-output (JSON schema → Pydantic) helper |
| `receipt_extractor.py` | Receipt email/photo → `ExtractedReceipt` |
| `policy_reader.py` | Retailer policy page → `RetailerPolicy` (window, conditions) |
| `eligibility.py` | Purchase + current price + policy → `EligibilityResult` |
| `claim_writer.py` | Friendly explanation plus the claim-form message |
| `sentient.py` | Purchase discovery via Sentient OS (with fixture fallback) |
| `claim_bot.py` | Playwright: fill in and submit the claim form, screenshot each step |

## Contract
Functions take and return models from `app/models.py`. **Don't touch the database.** L2 persists whatever you return.

## First tasks
- [ ] `gemini_client.generate_structured` working with one schema
- [ ] Put 3 sample receipt emails in `agents/fixtures/` and make `receipt_extractor` parse all 3
- [ ] Hardcode policies for 3 demo retailers, then `eligibility.check` with deterministic pre-checks plus Gemini
- [ ] `claim_bot.submit` against a **mock retailer claim page** (coordinate with L1), headful for the live demo
- [ ] Sentient OS: confirm with the sponsor what counts as an integration. Note that it's a Mac app, so test on a Mac.

## Raffle note
The Make it Legendary raffle requires a **Grok Bot** automation. Consider using Grok Bot for a piece of the
workflow, such as a routine that checks retailer policy pages or runs the nightly scan, and document it for the submission.
