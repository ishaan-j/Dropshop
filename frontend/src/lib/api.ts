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
 *   POST /api/eligibility/check    → no public route. Gemini runs in the backend job
 *                                    `evaluate_purchase`; its verdict is the drafted claim.
 *   GET  /api/claims               → GET /claims
 *   POST /api/claims               → POST /claims/:id/approve (the user approval).
 *                                    The backend drafts the claim. There is no create route.
 *   GET  /api/activity             → GET /activity?limit=
 *   GET  /api/refunds              → no public route. Nessie reconciliation is server-side;
 *                                    a refunded claim carries `nessie_deposit_id`.
 *   GET  /api/vault                → GET /savings
 *   POST /api/vault/deposit        → no public route. The backend records the vault credit
 *                                    after a refund; the claim carries `solana_tx_signature`.
 *
 * Where the real systems connect, behind the backend rather than this file:
 *   Sentient OS  — receipt discovery, POST /purchases/scan
 *   Tiger Data   — price history, GET /prices/:product_id
 *   Gemini       — eligibility and the claim explanation
 *   Grok Bot     — writes the claim message the bot submits after POST /claims/:id/approve,
 *                  and the nightly policy watch (POST /demo/jobs/watch_policies runs it now)
 *   Nessie       — refund verification inside reconcile_refunds
 *   Solana       — vault record and balance, GET /savings
 *   MongoDB      — purchases, claims, activity, and the user profile
 *
 * GET /health says which of these are live and which are simulated (`BackendStatus`).
 *
 * Do not put API keys, wallet secrets, or bank credentials in this client.
 */
import type {
  AgentEvent,
  BackendStatus,
  Claim,
  PricePoint,
  Purchase,
  RetailerPolicy,
  SavingsSummary,
} from "../types";
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
  health: () => request<BackendStatus>("/health"),
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
  policy: (retailer: string) => request<RetailerPolicy>(`/policies/${encodeURIComponent(retailer)}`),
  // Demo controls. They exist only when the backend runs with DEMO_MODE=true.
  demoReset: () => request<{ status: string; purchases: number; claims: number }>("/demo/reset", { method: "POST" }),
  demoPriceDrop: (body: { purchase_id?: string; percent?: number; new_price_cents?: number } = {}) =>
    request<{ purchase_id: string; product_name: string; old_price_cents: number; new_price_cents: number }>(
      "/demo/price-drop",
      { method: "POST", body: JSON.stringify(body) },
    ),
  runJob: (name: "scan_new_purchases" | "poll_prices" | "reconcile_refunds" | "watch_policies") =>
    request<{ job: string; job_id?: string; result?: { reviewed: number; changed: string[]; notes: string[] } }>(
      `/demo/jobs/${name}`,
      { method: "POST" },
    ),
};

export { formatCents } from "./utils";
