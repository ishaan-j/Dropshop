import type { Claim, ClaimStatus, TrackedPurchase, VaultTransaction } from "../types";
import { addDays, priceGap, startOfDay } from "./utils";

export type DisplayStatus =
  | "eligible"
  | "completed"
  | "pending"
  | "processing"
  | "submitted"
  | "monitoring"
  | "ineligible"
  | "expired";

export type SavingsRange = "7d" | "30d" | "all";

export interface SavingsPoint {
  label: string;
  balance: number;
  iso: string;
}

const ACTIVE_CLAIM = new Set<ClaimStatus>(["awaiting_approval", "submitting", "submitted"]);

export function claimForPurchase(claims: Claim[], purchaseId: string) {
  return claims
    .filter((claim) => claim.purchase_id === purchaseId)
    .sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
}

export function isVaulted(claim: Claim, vault: VaultTransaction[]) {
  if (claim.refund_cents <= 0) return false;
  const deposited = vault
    .filter((tx) => tx.claim_id === claim.id && tx.status === "confirmed")
    .reduce((sum, tx) => sum + tx.amount_cents, 0);
  return deposited >= claim.refund_cents;
}

/** Eligible drop that has not been confirmed, declined, or already deposited. */
export function isPotential(purchase: TrackedPurchase, claim?: Claim) {
  if (priceGap(purchase.price_paid_cents, purchase.current_price_cents) <= 0) return false;
  if (!purchase.qualifies) return false;
  if (purchase.status === "expired" || purchase.status === "claimed") return false;
  if (!claim) return true;
  if (claim.status === "refund_received" || claim.status === "rejected" || claim.status === "failed") {
    return false;
  }
  return true;
}

export function displayStatus(purchase: TrackedPurchase, claim?: Claim): DisplayStatus {
  if (purchase.status === "expired") return "expired";
  if (claim?.status === "rejected" || claim?.status === "failed") return "ineligible";
  if (claim?.status === "refund_received" || purchase.status === "claimed") return "completed";
  if (claim?.status === "submitted") return "submitted";
  if (claim?.status === "submitting") return "processing";
  if (claim?.status === "awaiting_approval") return "pending";
  const gap = priceGap(purchase.price_paid_cents, purchase.current_price_cents);
  if (gap > 0 && !purchase.qualifies) return "pending";
  if (gap > 0 && purchase.qualifies) return "eligible";
  return "monitoring";
}

export function computeMetrics(
  purchases: TrackedPurchase[],
  claims: Claim[],
  vault: VaultTransaction[],
) {
  const recoveredCents = claims
    .filter((claim) => claim.status === "refund_received")
    .reduce((sum, claim) => sum + claim.refund_cents, 0);

  const vaultBalanceCents = vault
    .filter((tx) => tx.status === "confirmed")
    .reduce((sum, tx) => sum + tx.amount_cents, 0);

  const potentialCents = purchases.reduce((sum, purchase) => {
    const claim = claimForPurchase(claims, purchase.id);
    if (!isPotential(purchase, claim)) return sum;
    return sum + priceGap(purchase.price_paid_cents, purchase.current_price_cents);
  }, 0);

  const pendingDepositCents = claims
    .filter((claim) => claim.status === "refund_received")
    .reduce((sum, claim) => {
      const deposited = vault
        .filter((tx) => tx.claim_id === claim.id && tx.status === "confirmed")
        .reduce((inner, tx) => inner + tx.amount_cents, 0);
      return sum + Math.max(0, claim.refund_cents - deposited);
    }, 0);

  const inProgressCents = claims
    .filter((claim) => claim.status === "submitting" || claim.status === "submitted")
    .reduce((sum, claim) => sum + claim.refund_cents, 0);

  const activeClaims = claims.filter((claim) => ACTIVE_CLAIM.has(claim.status)).length;

  return {
    recoveredCents,
    vaultBalanceCents,
    potentialCents,
    pendingDepositCents,
    inProgressCents,
    activeClaims,
    trackedCount: purchases.length,
  };
}

export function depositedThisMonth(vault: VaultTransaction[], now = new Date()) {
  return vault
    .filter((tx) => {
      if (tx.status !== "confirmed") return false;
      const date = new Date(tx.created_at);
      return date.getMonth() === now.getMonth() && date.getFullYear() === now.getFullYear();
    })
    .reduce((sum, tx) => sum + tx.amount_cents, 0);
}

export function savingsSeries(vault: VaultTransaction[], range: SavingsRange, now = new Date()): SavingsPoint[] {
  const confirmed = vault
    .filter((tx) => tx.status === "confirmed")
    .map((tx) => ({ ...tx, at: new Date(tx.created_at).getTime() }))
    .sort((a, b) => a.at - b.at);

  const today = startOfDay(now);
  let start = range === "7d" ? addDays(today, -6) : range === "30d" ? addDays(today, -29) : addDays(today, -29);
  if (range === "all" && confirmed[0]) {
    start = addDays(startOfDay(new Date(confirmed[0].at)), -1);
  }

  let running = confirmed.filter((tx) => tx.at < start.getTime()).reduce((sum, tx) => sum + tx.amount_cents, 0);
  const points: SavingsPoint[] = [];

  for (let day = start, guard = 0; day.getTime() <= today.getTime() && guard < 800; day = addDays(day, 1), guard += 1) {
    const from = day.getTime();
    const to = addDays(day, 1).getTime();
    for (const tx of confirmed) {
      if (tx.at >= from && tx.at < to) running += tx.amount_cents;
    }
    points.push({
      label: day.toLocaleDateString("en-US", range === "7d" ? { weekday: "short" } : { month: "short", day: "numeric" }),
      balance: running,
      iso: day.toISOString(),
    });
  }

  return points;
}

export function claimStageLabel(claim: Claim, vaulted: boolean) {
  switch (claim.status) {
    case "awaiting_approval":
      return "Claim prepared";
    case "submitting":
      return "Submitting claim";
    case "submitted":
      return "Waiting on retailer";
    case "refund_received":
      return vaulted ? "Savings vault credited" : "Refund confirmed";
    case "rejected":
      return "Ineligible";
    case "failed":
      return "Filing failed";
    default:
      return claim.status;
  }
}

/** How many claim-timeline steps are finished. `failedAt` is 1-based when a step failed. */
export function claimTimelineProgress(claim: Claim, vaulted: boolean) {
  if (claim.status === "rejected" || claim.status === "failed") return { done: 1, failedAt: 2 };
  if (claim.status === "awaiting_approval" || claim.status === "submitting") return { done: 3, failedAt: null };
  if (claim.status === "submitted") return { done: 4, failedAt: null };
  if (claim.status === "refund_received") return { done: vaulted ? 6 : 5, failedAt: null };
  return { done: 1, failedAt: null };
}
