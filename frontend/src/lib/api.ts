/**
 * HTTP client for the DropShop backend.
 *
 * Contract: docs/api-contract.md and backend/app/models.py.
 * Money is integer cents. Times are ISO-8601 UTC.
 *
 * The names discussed for the hackathon map onto the routes that exist today:
 *   GET  /api/purchases            → GET /purchases
 *   GET  /api/purchases/:id        → GET /purchases/:id
 *   GET  /api/prices/:id           → GET /prices/:product_id?days=
 *   POST /api/eligibility/check    → no public route. Gemini runs in the worker
 *                                    (`evaluate_purchase`). The demo simulates it.
 *   GET  /api/claims               → GET /claims
 *   POST /api/claims               → POST /claims/:id/approve (the user approval).
 *                                    The worker drafts the claim. There is no create route.
 *   GET  /api/activity             → GET /activity?limit=
 *   GET  /api/refunds              → no public route. Nessie reconciliation is server-side.
 *                                    Demo bank rows live in the local ledger.
 *   GET  /api/vault                → GET /savings
 *   POST /api/vault/deposit        → no public route. The worker records the vault credit
 *                                    after a refund. The demo simulates the deposit.
 *
 * Where the real systems connect, behind the backend rather than this file:
 *   Sentient OS  — receipt discovery, POST /purchases/scan
 *   Tiger Data   — price history, GET /prices/:product_id
 *   Gemini       — eligibility inside the worker
 *   Grok Bot     — claim submission after POST /claims/:id/approve
 *   Nessie       — refund verification inside reconcile_refunds
 *   Solana       — vault balance on GET /savings
 *   MongoDB      — purchases, claims, activity, and the user profile
 *
 * Do not put API keys, wallet secrets, or bank credentials in this client.
 */
import type { AgentEvent, Claim, PricePoint, Purchase, SavingsSummary } from "../types";
import { config } from "./config";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${config.apiUrl}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`${init?.method ?? "GET"} ${path} failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  purchases: () => request<Purchase[]>("/purchases"),
  purchase: (id: string) => request<Purchase>(`/purchases/${id}`),
  scan: () => request<{ job_id: string }>("/purchases/scan", { method: "POST" }),
  prices: (productId: string, days = 30) =>
    request<PricePoint[]>(`/prices/${encodeURIComponent(productId)}?days=${days}`),
  claims: () => request<Claim[]>("/claims"),
  approveClaim: (id: string) => request<Claim>(`/claims/${id}/approve`, { method: "POST" }),
  rejectClaim: (id: string) => request<Claim>(`/claims/${id}/reject`, { method: "POST" }),
  activity: (limit = 50) => request<AgentEvent[]>(`/activity?limit=${limit}`),
  savings: () => request<SavingsSummary>("/savings"),
};

export { formatCents } from "./utils";
