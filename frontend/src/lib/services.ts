/**
 * The seam between the screens and the data source.
 * Pages call these functions. They do not fetch on their own.
 *
 * Demo: the Zustand ledger is the database. Reducers in demo-reducer.ts are the writes.
 * Live: once the backend has answered GET /health (`isLive()`), the same functions call
 * src/lib/api.ts and the ledger is a copy of the backend's state, refreshed by polling.
 */
import type {
  AgentEvent,
  Claim,
  LedgerState,
  PricePoint,
  ProductArt,
  Purchase,
  RetailerPolicy,
  TrackedPurchase,
} from "../types";
import { api } from "./api";
import { withClaimStatus, withFiledClaim } from "./demo-reducer";
import { claimForPurchase } from "./metrics";
import { delay, priceGap } from "./utils";
import { useAppStore } from "../store/app-store";

/** True once the backend has answered. From then on the screens read and write through it. */
export function isLive() {
  return useAppStore.getState().backend !== null;
}

function artForName(name: string): ProductArt {
  const value = name.toLowerCase();
  if (value.includes("air max") || value.includes("nike")) return "nike";
  if (value.includes("airpod")) return "airpods";
  if (value.includes("headphone") || value.includes("sony")) return "headphones";
  if (value.includes("dyson") || value.includes("airwrap")) return "dyson";
  if (value.includes("samba") || value.includes("adidas")) return "samba";
  if (value.includes("legging") || value.includes("lulu")) return "leggings";
  if (value.includes("kindle")) return "kindle";
  if (value.includes("fryer") || value.includes("ninja")) return "fryer";
  if (value.includes("patagonia") || value.includes("jacket") || value.includes("puff")) return "jacket";
  if (value.includes("breville") || value.includes("bambino") || value.includes("espresso")) return "espresso";
  if (value.includes("allbird") || value.includes("runner")) return "runner";
  if (value.includes("shirt") || value.includes("linen")) return "shirt";
  return "generic";
}

function policyText(policy: RetailerPolicy | undefined) {
  if (!policy || policy.window_days == null) {
    return "No price-adjustment policy is on file for this retailer, so drops here can't be claimed.";
  }
  const conditions = policy.conditions.length ? ` Conditions: ${policy.conditions.join(" ")}` : "";
  return `${policy.summary}${conditions}`;
}

function latestEligibility(activity: AgentEvent[], purchaseId: string) {
  return activity
    .filter((event) => event.purchase_id === purchaseId && event.kind === "eligibility_checked")
    .sort((a, b) => b.time.localeCompare(a.time))[0];
}

function enrich(
  purchase: Purchase,
  history: PricePoint[],
  claims: Claim[],
  policy: RetailerPolicy | undefined,
  activity: AgentEvent[],
): TrackedPurchase {
  const claim = claimForPurchase(claims, purchase.id);
  const gap = priceGap(purchase.price_paid_cents, purchase.current_price_cents);
  const decision = latestEligibility(activity, purchase.id);
  const notEligible = decision?.message.startsWith("Not eligible") ?? false;
  const checkedEligible = decision?.message.startsWith("Eligible") ?? false;
  const blocked = claim?.status === "rejected" || claim?.status === "failed" || purchase.status === "expired";
  const waiting = purchase.status === "drop_detected" && !decision;
  return {
    ...purchase,
    art: artForName(purchase.product_name),
    policy_summary: policyText(policy),
    policy_window_days: policy?.window_days ?? null,
    eligibility_explanation:
      decision?.message
      ?? (waiting
        ? "Checking this price drop against the retailer's policy."
        : claim?.explanation || "No claim has been drafted for this purchase yet."),
    price_history: history,
    // A lower price is not enough. Eligible means the policy check passed.
    qualifies: gap > 0 && !blocked && checkedEligible && !notEligible,
  };
}

// Retailer policies change rarely (the nightly Grok watch), so they are re-read every few polls.
const policyCache = new Map<string, RetailerPolicy>();
const POLICY_REFRESH_EVERY = 8;
let hydrations = 0;

async function policiesFor(retailers: string[]) {
  const refresh = hydrations % POLICY_REFRESH_EVERY === 0;
  await Promise.all(
    retailers
      .filter((retailer) => refresh || !policyCache.has(retailer))
      .map(async (retailer) => {
        try {
          policyCache.set(retailer, await api.policy(retailer));
        } catch {
          // Keep whatever we had; the purchase page says when no policy is on file.
        }
      }),
  );
  hydrations += 1;
}

export async function hydrateFromBackend() {
  const [status, purchases, claims, activity, savings] = await Promise.all([
    api.health(),
    api.purchases(),
    api.claims(),
    api.activity(200),
    api.savings(),
  ]);
  await policiesFor([...new Set(purchases.map((purchase) => purchase.retailer))]);
  const tracked = await Promise.all(
    purchases.map(async (purchase) => {
      let history: PricePoint[] = [];
      try {
        history = await api.prices(purchase.product_id, 30);
      } catch {
        history = [];
      }
      return enrich(purchase, history, claims, policyCache.get(purchase.retailer), activity);
    }),
  );
  const vaultTransactions = claims
    .filter((claim) => claim.status === "refund_received")
    .map((claim) => ({
      id: `vault-${claim.id}`,
      claim_id: claim.id,
      purchase_id: claim.purchase_id,
      created_at: claim.refund_received_at ?? claim.created_at,
      amount_cents: claim.refund_cents,
      status: "confirmed" as const,
      signature: claim.solana_tx_signature ?? "pending-signature",
      description: `Savings deposit · ${claim.retailer}`,
    }));
  const bankTransactions = claims
    .filter((claim) => claim.status === "refund_received")
    .map((claim) => ({
      id: `bank-${claim.id}`,
      claim_id: claim.id,
      purchase_id: claim.purchase_id,
      posted_at: claim.refund_received_at ?? claim.created_at,
      amount_cents: claim.refund_cents,
      description: `PRICE ADJUSTMENT · ${claim.retailer}`,
      status: "posted" as const,
      account_mask: "4821",
    }));

  const next: LedgerState = { purchases: tracked, claims, activity, vaultTransactions, bankTransactions };
  const state = useAppStore.getState();
  const current: LedgerState = {
    purchases: state.purchases,
    claims: state.claims,
    activity: state.activity,
    vaultTransactions: state.vaultTransactions,
    bankTransactions: state.bankTransactions,
  };
  // Polled every few seconds: skip the writes when nothing changed so charts don't re-render.
  if (JSON.stringify(next) !== JSON.stringify(current)) state.applyLedger(next);
  if (JSON.stringify(status) !== JSON.stringify(state.backend)) state.setBackend(status);
  if (savings.vault_address && savings.vault_address !== state.user.wallet_address) {
    useAppStore.getState().patchUser({ wallet_address: savings.vault_address });
  }
}

/**
 * Keep the screens in step with the backend. Its jobs run in the background (receipt scans,
 * price drops, the claim bot, refunds, vault records), so the app polls instead of waiting for
 * a reload. Until the backend first answers, each tick is just a connection attempt, which is
 * how `auto` mode picks up a backend that was started after the page. Returns a stop function.
 */
export function startBackendSync(intervalMs = 4000) {
  let busy = false;
  const tick = async () => {
    if (busy || document.hidden) return;
    busy = true;
    try {
      await hydrateFromBackend();
    } catch {
      // Backend unreachable: keep showing the last good state and try again next tick.
    } finally {
      busy = false;
    }
  };
  const timer = window.setInterval(tick, intervalMs);
  return () => window.clearInterval(timer);
}

export async function fileClaim(purchaseId: string) {
  const before = useAppStore.getState();
  if (isLive()) {
    const claim = claimForPurchase(before.claims, purchaseId);
    if (!claim) {
      const purchase = before.purchases.find((item) => item.id === purchaseId);
      const reason = purchase?.eligibility_explanation;
      if (reason?.startsWith("Not eligible")) throw new Error(reason);
      throw new Error("This price drop is still being checked. A claim shows up here only after the policy check says it qualifies.");
    }
    const updated = await api.approveClaim(claim.id);
    useAppStore.getState().upsertClaim(updated);
    return updated;
  }
  await delay(700);
  if (useAppStore.getState().epoch !== before.epoch) return null;
  const next = withFiledClaim(useAppStore.getState(), purchaseId);
  useAppStore.getState().applyLedger(next);
  return claimForPurchase(next.claims, purchaseId) ?? null;
}

export async function approveClaim(claimId: string) {
  const epoch = useAppStore.getState().epoch;
  if (isLive()) {
    const updated = await api.approveClaim(claimId);
    useAppStore.getState().upsertClaim(updated);
    return;
  }
  useAppStore.getState().applyLedger(withClaimStatus(useAppStore.getState(), claimId, "submitting"));
  await delay(900);
  if (useAppStore.getState().epoch !== epoch) return;
  useAppStore.getState().applyLedger(withClaimStatus(useAppStore.getState(), claimId, "submitted"));
}

export async function rejectClaim(claimId: string) {
  const epoch = useAppStore.getState().epoch;
  if (isLive()) {
    const updated = await api.rejectClaim(claimId);
    useAppStore.getState().upsertClaim(updated);
    return;
  }
  await delay(250);
  if (useAppStore.getState().epoch !== epoch) return;
  useAppStore.getState().applyLedger(withClaimStatus(useAppStore.getState(), claimId, "rejected"));
}

export async function checkEligibility(purchaseId: string) {
  const purchase = useAppStore.getState().purchases.find((item) => item.id === purchaseId);
  if (!purchase) throw new Error("Purchase not found");
  // Live: Gemini runs in the backend's evaluate_purchase job, and its verdict arrives as the
  // drafted claim's explanation. This returns that latest explanation.
  await delay(400);
  const gap = priceGap(purchase.price_paid_cents, purchase.current_price_cents);
  return {
    purchase_id: purchaseId,
    eligible: purchase.qualifies && gap > 0,
    refund_cents: purchase.qualifies ? gap : 0,
    reason: purchase.eligibility_explanation,
    policy_excerpt: purchase.policy_summary,
    confidence: purchase.qualifies ? 0.86 : 0.74,
    simulated: !isLive(),
  };
}

// --- Backend controls (live only). Each starts a background job; the poll shows its results. ---

/** Look for new purchases in receipts. */
export async function scanForPurchases() {
  await api.scan();
}

/** Demo: drop a monitored product's price now, so the agents have something to catch. */
export async function triggerPriceDrop() {
  return api.demoPriceDrop();
}

/** Run the nightly Grok policy watch now. */
export async function runPolicyWatch() {
  return (await api.runJob("watch_policies")).result;
}

/** Reseed the backend's demo state and reload it. */
export async function resetBackendDemo() {
  await api.demoReset();
  await hydrateFromBackend();
}

