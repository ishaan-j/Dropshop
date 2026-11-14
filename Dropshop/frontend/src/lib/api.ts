// Typed client for the Dropshot API. See docs/api-contract.md.
import type { AgentEvent, Claim, PricePoint, Purchase, SavingsSummary } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`${init?.method ?? "GET"} ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
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

export const formatCents = (cents: number) =>
  (cents / 100).toLocaleString("en-US", { style: "currency", currency: "USD" });
