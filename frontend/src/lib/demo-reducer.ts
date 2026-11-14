import type { AgentEvent, Claim, ClaimStatus, LedgerState, TrackedPurchase } from "../types";
import {
  DEMO_BANK_ID,
  DEMO_CLAIM_ID,
  DEMO_CURRENT_CENTS,
  DEMO_PAID_CENTS,
  DEMO_PURCHASE_ID,
  DEMO_REFUND_CENTS,
  DEMO_SIGNATURE,
  DEMO_VAULT_ID,
  USER_ID,
} from "./constants";
import { claimForPurchase } from "./metrics";
import { formatCents, priceGap, shiftDays } from "./utils";

const NIKE_EXPLANATION = `Demo policy: Nike allows a price adjustment within 14 days when the same shoe is listed for less. You paid ${formatCents(DEMO_PAID_CENTS)} and the current price is ${formatCents(DEMO_CURRENT_CENTS)}, so you qualify for ${formatCents(DEMO_REFUND_CENTS)}. This is simulated, not a live Gemini decision.`;

function withEvent(activity: AgentEvent[], entry: AgentEvent) {
  if (activity.some((item) => item.id === entry.id)) return activity;
  return [entry, ...activity];
}

function demoPurchase(): TrackedPurchase {
  const now = new Date().toISOString();
  return {
    id: DEMO_PURCHASE_ID,
    user_id: USER_ID,
    retailer: "Nike",
    product_name: "Nike Air Max 270",
    product_url: null,
    price_paid_cents: DEMO_PAID_CENTS,
    purchased_at: now,
    order_number: "NK-10482931",
    product_id: "nike:air-max-270",
    source: "sentient",
    nessie_purchase_id: null,
    adjustment_window_ends: shiftDays(14, 23),
    current_price_cents: DEMO_PAID_CENTS,
    status: "monitoring",
    art: "nike",
    policy_summary: "Nike's demo policy adjusts its own price within 14 days for the same shoe.",
    policy_window_days: 14,
    eligibility_explanation: "Waiting for Gemini to review this receipt against Nike's price-adjustment policy.",
    price_history: [{ time: now, retailer: "Nike", price_cents: DEMO_PAID_CENTS }],
    qualifies: false,
  };
}

function droppedHistory() {
  const prices = [16000, 16000, 15700, 15100, 14200, 13200, 12400, DEMO_CURRENT_CENTS];
  const end = Date.now();
  return prices.map((price, index) => ({
    time: new Date(end - (prices.length - 1 - index) * 60 * 60 * 1000).toISOString(),
    retailer: "Nike",
    price_cents: price,
  }));
}

function patchPurchase(state: LedgerState, patch: Partial<TrackedPurchase>): LedgerState {
  return {
    ...state,
    purchases: state.purchases.map((purchase) =>
      purchase.id === DEMO_PURCHASE_ID ? { ...purchase, ...patch } : purchase,
    ),
  };
}

export function resetDemoRun(state: LedgerState): LedgerState {
  return {
    ...state,
    purchases: state.purchases.filter((purchase) => purchase.id !== DEMO_PURCHASE_ID),
    claims: state.claims.filter((claim) => claim.purchase_id !== DEMO_PURCHASE_ID),
    activity: state.activity.filter((item) => item.purchase_id !== DEMO_PURCHASE_ID && !item.id.startsWith("demo-")),
    vaultTransactions: state.vaultTransactions.filter(
      (tx) => tx.id !== DEMO_VAULT_ID && tx.purchase_id !== DEMO_PURCHASE_ID,
    ),
    bankTransactions: state.bankTransactions.filter(
      (tx) => tx.id !== DEMO_BANK_ID && tx.purchase_id !== DEMO_PURCHASE_ID,
    ),
  };
}

function ensureReceipt(state: LedgerState): LedgerState {
  if (state.purchases.some((purchase) => purchase.id === DEMO_PURCHASE_ID)) return state;
  const now = new Date().toISOString();
  return {
    ...state,
    purchases: [demoPurchase(), ...state.purchases],
    activity: withEvent(state.activity, {
      id: "demo-evt-receipt",
      user_id: USER_ID,
      time: now,
      kind: "purchase_found",
      message: "Sentient OS discovered a purchase receipt: Nike Air Max 270, $160.00 at Nike.",
      purchase_id: DEMO_PURCHASE_ID,
      claim_id: null,
      screenshot_url: null,
    }),
  };
}

function ensureDrop(state: LedgerState): LedgerState {
  state = ensureReceipt(state);
  const purchase = state.purchases.find((item) => item.id === DEMO_PURCHASE_ID);
  if (purchase?.current_price_cents === DEMO_CURRENT_CENTS && state.activity.some((item) => item.id === "demo-evt-drop")) {
    return state;
  }
  const now = new Date().toISOString();
  const next = patchPurchase(state, {
    current_price_cents: DEMO_CURRENT_CENTS,
    status: purchase?.status === "monitoring" || purchase?.status === "drop_detected" ? "drop_detected" : purchase?.status,
    price_history: droppedHistory(),
  });
  return {
    ...next,
    activity: withEvent(next.activity, {
      id: "demo-evt-drop",
      user_id: USER_ID,
      time: now,
      kind: "price_drop",
      message: "Tiger Data detected a $40.00 price drop on Nike Air Max 270, from $160.00 to $120.00.",
      purchase_id: DEMO_PURCHASE_ID,
      claim_id: null,
      screenshot_url: null,
    }),
  };
}

function ensureEligibility(state: LedgerState): LedgerState {
  state = ensureDrop(state);
  const purchase = state.purchases.find((item) => item.id === DEMO_PURCHASE_ID);
  if (purchase?.qualifies && state.activity.some((item) => item.id === "demo-evt-eligibility")) return state;
  const now = new Date().toISOString();
  const next = patchPurchase(state, {
    qualifies: true,
    eligibility_explanation: NIKE_EXPLANATION,
    status: purchase?.status === "monitoring" ? "drop_detected" : purchase?.status,
  });
  return {
    ...next,
    activity: withEvent(next.activity, {
      id: "demo-evt-eligibility",
      user_id: USER_ID,
      time: now,
      kind: "eligibility_checked",
      message: "Gemini verified you qualify for a $40.00 Nike price adjustment.",
      purchase_id: DEMO_PURCHASE_ID,
      claim_id: null,
      screenshot_url: null,
    }),
  };
}

function openDemoClaim(state: LedgerState) {
  return state.claims.find(
    (claim) => claim.purchase_id === DEMO_PURCHASE_ID && claim.status !== "rejected" && claim.status !== "failed",
  );
}

function ensureClaim(state: LedgerState): LedgerState {
  state = ensureEligibility(state);
  const existing = openDemoClaim(state);
  if (existing && (existing.status === "submitted" || existing.status === "submitting" || existing.status === "refund_received")) {
    return state;
  }
  const now = new Date().toISOString();
  const purchase = state.purchases.find((item) => item.id === DEMO_PURCHASE_ID);
  const refund = purchase ? priceGap(purchase.price_paid_cents, purchase.current_price_cents) : DEMO_REFUND_CENTS;
  const claim: Claim = existing
    ? { ...existing, status: "submitted", submitted_at: existing.submitted_at ?? now, refund_cents: refund }
    : {
        id: DEMO_CLAIM_ID,
        user_id: USER_ID,
        purchase_id: DEMO_PURCHASE_ID,
        retailer: "Nike",
        refund_cents: refund,
        status: "submitted",
        explanation: NIKE_EXPLANATION,
        created_at: now,
        submitted_at: now,
        refund_received_at: null,
        nessie_deposit_id: null,
        solana_tx_signature: null,
      };
  return {
    ...state,
    claims: existing
      ? state.claims.map((item) => (item.id === existing.id ? claim : item))
      : [claim, ...state.claims],
    purchases: state.purchases.map((item) =>
      item.id === DEMO_PURCHASE_ID ? { ...item, status: "claim_pending" } : item,
    ),
    activity: withEvent(
      withEvent(state.activity, {
        id: "demo-evt-draft",
        user_id: USER_ID,
        time: now,
        kind: "claim_drafted",
        message: "Grok Bot prepared a $40.00 price-adjustment claim for Nike Air Max 270.",
        purchase_id: DEMO_PURCHASE_ID,
        claim_id: claim.id,
        screenshot_url: null,
      }),
      {
        id: "demo-evt-submitted",
        user_id: USER_ID,
        time: now,
        kind: "claim_submitted",
        message: "Grok Bot submitted the $40.00 Nike refund claim.",
        purchase_id: DEMO_PURCHASE_ID,
        claim_id: claim.id,
        screenshot_url: null,
      },
    ),
  };
}

function ensureRefund(state: LedgerState): LedgerState {
  state = ensureClaim(state);
  const claim = openDemoClaim(state);
  if (!claim) return state;
  const banked = state.bankTransactions.some((tx) => tx.purchase_id === DEMO_PURCHASE_ID);
  if (claim.status === "refund_received" && banked) return state;
  const now = new Date().toISOString();
  return {
    ...state,
    claims: state.claims.map((item) =>
      item.id === claim.id
        ? {
            ...item,
            status: "refund_received",
            refund_received_at: item.refund_received_at ?? now,
            nessie_deposit_id: item.nessie_deposit_id ?? "demo-nessie-nike",
          }
        : item,
    ),
    purchases: state.purchases.map((item) =>
      item.id === DEMO_PURCHASE_ID ? { ...item, status: "claimed" } : item,
    ),
    bankTransactions: banked
      ? state.bankTransactions
      : [
          {
            id: DEMO_BANK_ID,
            claim_id: claim.id,
            purchase_id: DEMO_PURCHASE_ID,
            posted_at: now,
            amount_cents: claim.refund_cents,
            description: "PRICE ADJUSTMENT · Nike Air Max 270",
            status: "posted",
            account_mask: "4821",
          },
          ...state.bankTransactions,
        ],
    activity: withEvent(state.activity, {
      id: "demo-evt-refund",
      user_id: USER_ID,
      time: now,
      kind: "refund_received",
      message: `Nessie confirmed a ${formatCents(claim.refund_cents)} refund for Nike Air Max 270.`,
      purchase_id: DEMO_PURCHASE_ID,
      claim_id: claim.id,
      screenshot_url: null,
    }),
  };
}

function ensureVault(state: LedgerState): LedgerState {
  state = ensureRefund(state);
  if (state.vaultTransactions.some((tx) => tx.id === DEMO_VAULT_ID || tx.purchase_id === DEMO_PURCHASE_ID)) {
    return state;
  }
  const claim = openDemoClaim(state);
  if (!claim) return state;
  const now = new Date().toISOString();
  return {
    ...state,
    claims: state.claims.map((item) =>
      item.id === claim.id ? { ...item, solana_tx_signature: item.solana_tx_signature ?? DEMO_SIGNATURE } : item,
    ),
    vaultTransactions: [
      {
        id: DEMO_VAULT_ID,
        claim_id: claim.id,
        purchase_id: DEMO_PURCHASE_ID,
        created_at: now,
        amount_cents: claim.refund_cents,
        status: "confirmed",
        signature: DEMO_SIGNATURE,
        description: "Savings deposit · Nike Air Max 270",
      },
      ...state.vaultTransactions,
    ],
    activity: withEvent(state.activity, {
      id: "demo-evt-vault",
      user_id: USER_ID,
      time: now,
      kind: "vault_recorded",
      message: `${formatCents(claim.refund_cents)} added to your savings vault.`,
      purchase_id: DEMO_PURCHASE_ID,
      claim_id: claim.id,
      screenshot_url: null,
    }),
  };
}

export type DemoStage = 1 | 2 | 3 | 4 | 5 | 6;

export function applyDemoStage(state: LedgerState, stage: DemoStage): LedgerState {
  switch (stage) {
    case 1:
      return ensureReceipt(state);
    case 2:
      return ensureDrop(state);
    case 3:
      return ensureEligibility(state);
    case 4:
      return ensureClaim(state);
    case 5:
      return ensureRefund(state);
    case 6:
      return ensureVault(state);
    default:
      return state;
  }
}

export function withFiledClaim(state: LedgerState, purchaseId: string): LedgerState {
  const purchase = state.purchases.find((item) => item.id === purchaseId);
  if (!purchase || !purchase.qualifies) return state;
  const gap = priceGap(purchase.price_paid_cents, purchase.current_price_cents);
  if (gap <= 0) return state;
  const existing = claimForPurchase(state.claims, purchaseId);
  if (existing && existing.status !== "failed") return state;
  const now = new Date().toISOString();
  const claim: Claim = {
    id: `claim-${purchaseId}`,
    user_id: USER_ID,
    purchase_id: purchaseId,
    retailer: purchase.retailer,
    refund_cents: gap,
    status: "submitted",
    explanation: purchase.eligibility_explanation,
    created_at: now,
    submitted_at: now,
    refund_received_at: null,
    nessie_deposit_id: null,
    solana_tx_signature: null,
  };
  return {
    ...state,
    claims: [claim, ...state.claims],
    purchases: state.purchases.map((item) =>
      item.id === purchaseId ? { ...item, status: "claim_pending" } : item,
    ),
    activity: withEvent(
      withEvent(state.activity, {
        id: `act-${claim.id}-draft`,
        user_id: USER_ID,
        time: now,
        kind: "claim_drafted",
        message: `Grok Bot prepared a ${formatCents(gap)} claim for ${purchase.product_name}.`,
        purchase_id: purchaseId,
        claim_id: claim.id,
        screenshot_url: null,
      }),
      {
        id: `act-${claim.id}-submitted`,
        user_id: USER_ID,
        time: now,
        kind: "claim_submitted",
        message: `Grok Bot submitted a ${formatCents(gap)} claim for ${purchase.product_name}.`,
        purchase_id: purchaseId,
        claim_id: claim.id,
        screenshot_url: null,
      },
    ),
  };
}

const FORWARD: ClaimStatus[] = ["awaiting_approval", "submitting", "submitted", "refund_received"];

export function withClaimStatus(state: LedgerState, claimId: string, status: ClaimStatus): LedgerState {
  const claim = state.claims.find((item) => item.id === claimId);
  if (!claim || claim.status === status) return state;
  if (claim.status === "refund_received") return state;
  if (status !== "rejected" && status !== "failed") {
    const from = FORWARD.indexOf(claim.status);
    const to = FORWARD.indexOf(status);
    if (from === -1 || to === -1 || to < from) return state;
  }
  const now = new Date().toISOString();
  const nextClaim: Claim = {
    ...claim,
    status,
    submitted_at: status === "submitted" || status === "refund_received" ? claim.submitted_at ?? now : claim.submitted_at,
    refund_received_at: status === "refund_received" ? claim.refund_received_at ?? now : claim.refund_received_at,
  };
  const purchaseStatus = status === "refund_received"
    ? "claimed"
    : status === "rejected" || status === "failed"
      ? undefined
      : "claim_pending";
  const message =
    status === "submitting"
      ? `Grok Bot is filing the ${formatCents(claim.refund_cents)} ${claim.retailer} claim.`
      : status === "submitted"
        ? `Grok Bot submitted the ${formatCents(claim.refund_cents)} ${claim.retailer} claim.`
        : status === "rejected"
          ? `You declined the ${formatCents(claim.refund_cents)} ${claim.retailer} claim.`
          : `Claim updated to ${status}.`;
  return {
    ...state,
    claims: state.claims.map((item) => (item.id === claimId ? nextClaim : item)),
    purchases: purchaseStatus
      ? state.purchases.map((item) => (item.id === claim.purchase_id ? { ...item, status: purchaseStatus } : item))
      : state.purchases,
    activity: withEvent(state.activity, {
      id: `act-${claimId}-${status}`,
      user_id: USER_ID,
      time: now,
      kind: status === "rejected" ? "error" : status === "submitting" ? "claim_submitting" : "claim_submitted",
      message,
      purchase_id: claim.purchase_id,
      claim_id: claimId,
      screenshot_url: null,
    }),
  };
}
