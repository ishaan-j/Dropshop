/**
 * The seam between the screens and the data source.
 * Pages call these functions. They do not fetch on their own.
 *
 * In demo mode the Zustand ledger is the database. Reducers in demo-reducer.ts
 * are the writes. In api mode the same functions call src/lib/api.ts.
 */
import type { Claim, PricePoint, ProductArt, Purchase, TrackedPurchase } from "../types";
import { api } from "./api";
import { config } from "./config";
import { withClaimStatus, withFiledClaim } from "./demo-reducer";
import { claimForPurchase } from "./metrics";
import { delay, priceGap } from "./utils";
import { useAppStore } from "../store/app-store";

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

function enrich(purchase: Purchase, history: PricePoint[], claims: Claim[]): TrackedPurchase {
  const claim = claimForPurchase(claims, purchase.id);
  const gap = priceGap(purchase.price_paid_cents, purchase.current_price_cents);
  const blocked = claim?.status === "rejected" || claim?.status === "failed" || purchase.status === "expired";
  return {
    ...purchase,
    art: artForName(purchase.product_name),
    policy_summary: "Gemini's policy summary will appear here once the eligibility worker is connected.",
    policy_window_days: null,
    eligibility_explanation: claim?.explanation || "Eligibility has not been explained for this purchase yet.",
    price_history: history,
    qualifies: gap > 0 && !blocked,
  };
}

export async function hydrateFromBackend() {
  const [purchases, claims, activity, savings] = await Promise.all([
    api.purchases(),
    api.claims(),
    api.activity(50),
    api.savings(),
  ]);
  const tracked = await Promise.all(
    purchases.map(async (purchase) => {
      let history: PricePoint[] = [];
      try {
        history = await api.prices(purchase.product_id, 30);
      } catch {
        history = [];
      }
      return enrich(purchase, history, claims);
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

  useAppStore.getState().applyLedger({
    purchases: tracked,
    claims,
    activity,
    vaultTransactions,
    bankTransactions,
  });
  if (savings.vault_address) {
    useAppStore.getState().patchUser({ wallet_address: savings.vault_address });
  }
}

export async function fileClaim(purchaseId: string) {
  const before = useAppStore.getState();
  if (config.dataMode === "api") {
    const claim = claimForPurchase(before.claims, purchaseId);
    if (!claim) {
      throw new Error("The backend drafts claims after a price drop. There is no claim to approve for this purchase yet.");
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
  if (config.dataMode === "api") {
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
  if (config.dataMode === "api") {
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
  if (config.dataMode === "api") {
    // Gemini runs in the backend worker. This returns the latest local explanation
    // until a public eligibility route exists.
  }
  await delay(400);
  const gap = priceGap(purchase.price_paid_cents, purchase.current_price_cents);
  return {
    purchase_id: purchaseId,
    eligible: purchase.qualifies && gap > 0,
    refund_cents: purchase.qualifies ? gap : 0,
    reason: purchase.eligibility_explanation,
    policy_excerpt: purchase.policy_summary,
    confidence: purchase.qualifies ? 0.86 : 0.74,
    simulated: config.dataMode === "demo",
  };
}
