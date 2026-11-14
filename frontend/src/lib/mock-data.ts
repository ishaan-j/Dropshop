import type { AgentEvent, AgentEventKind, Claim, PricePoint, PurchaseStatus, PurchaseSource, TrackedPurchase } from "../types";
import type { ProductArt } from "../types";
import { USER_ID } from "./constants";
import { formatCents, shiftDays, shiftHours } from "./utils";

export interface UserSettings {
  autoTracking: boolean;
  autoClaims: boolean;
  refundNotifications: boolean;
  minRefundCents: number;
  shareAnonymizedUsage: boolean;
  marketingEmails: boolean;
}

export const defaultUser = {
  id: USER_ID,
  name: "Alex Rivera",
  email: "alex.rivera@gmail.com",
  bank_name: "Capital One",
  bank_mask: "4821",
  wallet_address: "DsV1Demo9kQ2mN4pR7sT8uV3wX6yZ1aB5cD8eF2gH4",
};

export const defaultSettings: UserSettings = {
  autoTracking: true,
  autoClaims: true,
  refundNotifications: true,
  minRefundCents: 500,
  shareAnonymizedUsage: false,
  marketingEmails: false,
};

const SIGNATURES: Record<string, string> = {
  "c-patagonia": "simPatagoniaNanoPuffVaultTx40d001",
  "c-adidas": "simAdidasSambaVaultTx16d000002",
  "c-allbirds": "simAllbirdsRunnerVaultTx4d00003",
};

interface SeedClaim {
  id: string;
  status: Claim["status"];
  createdHoursAgo?: number;
  createdDaysAgo?: number;
  submittedDaysAgo?: number;
  refundDaysAgo?: number;
}

interface SeedPurchase {
  id: string;
  name: string;
  retailer: string;
  art: ProductArt;
  paid: number;
  current: number;
  purchasedDays: number;
  windowDays: number | null;
  status: PurchaseStatus;
  source: PurchaseSource;
  order: string;
  productId: string;
  qualifies: boolean;
  dropDaysAgo: number | null;
  policyWindow: number | null;
  policy: string;
  explanation: string;
  claim?: SeedClaim;
}

function moneyLine(paid: number, current: number, window: number, retailer: string) {
  const gap = paid - current;
  if (gap <= 0) {
    return `Demo policy: ${retailer} checks price adjustments for ${window} days. The price has not dropped below what you paid. This is simulated, not a live Gemini decision.`;
  }
  return `Demo policy: ${retailer} allows a price adjustment within ${window} days when the same item is cheaper. You paid ${formatCents(paid)} and it is now ${formatCents(current)}, a difference of ${formatCents(gap)}. This is simulated, not a live Gemini decision.`;
}

const SEED: SeedPurchase[] = [
  {
    id: "p-sony",
    name: "Sony WH-1000XM5 Headphones",
    retailer: "Best Buy",
    art: "headphones",
    paid: 39900,
    current: 34900,
    purchasedDays: 8,
    windowDays: 15,
    status: "drop_detected",
    source: "sentient",
    order: "BBY-884221",
    productId: "bestbuy:wh1000xm5",
    qualifies: true,
    dropDaysAgo: 2,
    policyWindow: 15,
    policy: "Best Buy matches its own lower price for 15 days when the item and seller match.",
    explanation: moneyLine(39900, 34900, 15, "Best Buy"),
  },
  {
    id: "p-airpods",
    name: "Apple AirPods Pro",
    retailer: "Apple",
    art: "airpods",
    paid: 24900,
    current: 21900,
    purchasedDays: 5,
    windowDays: 14,
    status: "claim_pending",
    source: "email",
    order: "W-104928",
    productId: "apple:airpods-pro",
    qualifies: true,
    dropDaysAgo: 1,
    policyWindow: 14,
    policy: "Apple considers a price drop on the same product within 14 days of purchase.",
    explanation: moneyLine(24900, 21900, 14, "Apple"),
    claim: { id: "c-airpods", status: "awaiting_approval", createdHoursAgo: 5 },
  },
  {
    id: "p-dyson",
    name: "Dyson Airwrap",
    retailer: "Dyson",
    art: "dyson",
    paid: 59900,
    current: 54900,
    purchasedDays: 11,
    windowDays: 30,
    status: "claim_pending",
    source: "sentient",
    order: "DYS-229184",
    productId: "dyson:airwrap",
    qualifies: true,
    dropDaysAgo: 3,
    policyWindow: 30,
    policy: "Dyson accepts a price adjustment within 30 days for the same model bought from Dyson.",
    explanation: moneyLine(59900, 54900, 30, "Dyson"),
    claim: { id: "c-dyson", status: "submitted", createdDaysAgo: 1, submittedDaysAgo: 1 },
  },
  {
    id: "p-adidas",
    name: "Adidas Samba",
    retailer: "Adidas",
    art: "samba",
    paid: 10000,
    current: 9000,
    purchasedDays: 22,
    windowDays: 30,
    status: "claimed",
    source: "nessie",
    order: "AD-339120",
    productId: "adidas:samba",
    qualifies: true,
    dropDaysAgo: 18,
    policyWindow: 30,
    policy: "Adidas adjusts its own price within 30 days of the original order.",
    explanation: moneyLine(10000, 9000, 30, "Adidas"),
    claim: { id: "c-adidas", status: "refund_received", createdDaysAgo: 17, submittedDaysAgo: 17, refundDaysAgo: 16 },
  },
  {
    id: "p-lulu",
    name: "Lululemon Align Leggings",
    retailer: "Lululemon",
    art: "leggings",
    paid: 9800,
    current: 9800,
    purchasedDays: 3,
    windowDays: 14,
    status: "monitoring",
    source: "email",
    order: "LL-882110",
    productId: "lululemon:align",
    qualifies: false,
    dropDaysAgo: null,
    policyWindow: 14,
    policy: "Lululemon reviews a lower price within 14 days for the same color and size.",
    explanation: moneyLine(9800, 9800, 14, "Lululemon"),
  },
  {
    id: "p-kindle",
    name: "Kindle Paperwhite",
    retailer: "Amazon",
    art: "kindle",
    paid: 14900,
    current: 12900,
    purchasedDays: 4,
    windowDays: 30,
    status: "drop_detected",
    source: "sentient",
    order: "112-4482911",
    productId: "amazon:kindle-paperwhite",
    qualifies: true,
    dropDaysAgo: 1,
    policyWindow: 30,
    policy: "Amazon price protection in this demo covers the same item within 30 days.",
    explanation: moneyLine(14900, 12900, 30, "Amazon"),
  },
  {
    id: "p-ninja",
    name: "Ninja Air Fryer",
    retailer: "Target",
    art: "fryer",
    paid: 12000,
    current: 9900,
    purchasedDays: 6,
    windowDays: 14,
    status: "claim_pending",
    source: "email",
    order: "TGT-190284",
    productId: "target:ninja-air-fryer",
    qualifies: true,
    dropDaysAgo: 2,
    policyWindow: 14,
    policy: "Target matches a lower Target price within 14 days of purchase.",
    explanation: moneyLine(12000, 9900, 14, "Target"),
    claim: { id: "c-ninja", status: "submitting", createdHoursAgo: 3 },
  },
  {
    id: "p-patagonia",
    name: "Patagonia Nano Puff",
    retailer: "REI",
    art: "jacket",
    paid: 22900,
    current: 19900,
    purchasedDays: 48,
    windowDays: 30,
    status: "claimed",
    source: "nessie",
    order: "REI-552190",
    productId: "rei:nano-puff",
    qualifies: true,
    dropDaysAgo: 30,
    policyWindow: 30,
    policy: "REI's demo policy adjusts a lower REI price within 30 days.",
    explanation: moneyLine(22900, 19900, 30, "REI"),
    claim: { id: "c-patagonia", status: "refund_received", createdDaysAgo: 41, submittedDaysAgo: 41, refundDaysAgo: 40 },
  },
  {
    id: "p-breville",
    name: "Breville Bambino",
    retailer: "Williams Sonoma",
    art: "espresso",
    paid: 39900,
    current: 34900,
    purchasedDays: 40,
    windowDays: 14,
    status: "expired",
    source: "email",
    order: "WS-100293",
    productId: "williams-sonoma:bambino",
    qualifies: false,
    dropDaysAgo: 3,
    policyWindow: 14,
    policy: "Williams Sonoma's demo window is 14 days. This drop landed after it closed.",
    explanation:
      "Demo policy: Williams Sonoma's 14-day window closed before this price drop. The lower price is in the demo history, but the adjustment period has expired. Simulated, not a live Gemini decision.",
  },
  {
    id: "p-allbirds",
    name: "Allbirds Tree Runner",
    retailer: "Allbirds",
    art: "runner",
    paid: 9800,
    current: 7800,
    purchasedDays: 12,
    windowDays: 30,
    status: "claimed",
    source: "sentient",
    order: "AB-448211",
    productId: "allbirds:tree-runner",
    qualifies: true,
    dropDaysAgo: 6,
    policyWindow: 30,
    policy: "Allbirds adjusts its own price within 30 days of the original order.",
    explanation: moneyLine(9800, 7800, 30, "Allbirds"),
    claim: { id: "c-allbirds", status: "refund_received", createdDaysAgo: 5, submittedDaysAgo: 5, refundDaysAgo: 4 },
  },
  {
    id: "p-hm",
    name: "H&M Linen Shirt",
    retailer: "H&M",
    art: "shirt",
    paid: 4999,
    current: 2999,
    purchasedDays: 2,
    windowDays: null,
    status: "drop_detected",
    source: "email",
    order: "HM-229100",
    productId: "hm:linen-shirt",
    qualifies: false,
    dropDaysAgo: 1,
    policyWindow: null,
    policy: "H&M does not offer a post-purchase price adjustment in this demo.",
    explanation:
      "Demo policy: H&M does not offer post-purchase price adjustments. The shirt is cheaper now, but this purchase does not qualify. Simulated, not a live Gemini decision.",
    claim: { id: "c-hm", status: "rejected", createdHoursAgo: 20 },
  },
];

export function buildHistory(retailer: string, paid: number, current: number, dropDaysAgo: number | null): PricePoint[] {
  const points: PricePoint[] = [];
  for (let day = 30; day >= 0; day -= 2) {
    let price = paid;
    if (dropDaysAgo != null && current < paid && day <= dropDaysAgo) {
      const t = (dropDaysAgo - day) / Math.max(dropDaysAgo, 1);
      price = Math.round(paid + (current - paid) * Math.min(1, Math.max(0, t)));
    }
    points.push({ time: shiftDays(-day, 12), retailer, price_cents: price });
  }
  return points;
}

function event(
  id: string,
  time: string,
  kind: AgentEventKind,
  message: string,
  purchaseId: string | null,
  claimId: string | null = null,
): AgentEvent {
  return {
    id,
    user_id: USER_ID,
    time,
    kind,
    message,
    purchase_id: purchaseId,
    claim_id: claimId,
    screenshot_url: null,
  };
}

function buildActivity(): AgentEvent[] {
  return [
    event("a-check", shiftHours(-1), "price_checked", "Tiger Data checked current prices for your tracked purchases.", null),
    event("a-kindle-elig", shiftHours(-2), "eligibility_checked", "Gemini verified the Kindle Paperwhite qualifies for a $20.00 Amazon adjustment.", "p-kindle"),
    event("a-kindle-drop", shiftHours(-3), "price_drop", "Tiger Data detected a price drop: Kindle Paperwhite fell from $149.00 to $129.00.", "p-kindle"),
    event("a-ninja-sub", shiftHours(-3), "claim_submitting", "Grok Bot is filing the $21.00 Target claim for the Ninja Air Fryer.", "p-ninja", "c-ninja"),
    event("a-sony-elig", shiftHours(-4), "eligibility_checked", "Gemini verified the Sony WH-1000XM5 qualifies for a $50.00 Best Buy adjustment.", "p-sony"),
    event("a-airpods-draft", shiftHours(-5), "claim_drafted", "Grok Bot prepared a $30.00 Apple claim for AirPods Pro and is waiting for approval.", "p-airpods", "c-airpods"),
    event("a-sony-drop", shiftHours(-6), "price_drop", "Tiger Data detected a price drop: Sony WH-1000XM5 fell from $399.00 to $349.00.", "p-sony"),
    event("a-hm", shiftHours(-20), "eligibility_checked", "Gemini marked the H&M Linen Shirt ineligible. This demo policy has no price adjustment.", "p-hm", "c-hm"),
    event("a-dyson-sub", shiftDays(-1, 16), "claim_submitted", "Grok Bot submitted the $50.00 Dyson Airwrap claim.", "p-dyson", "c-dyson"),
    event("a-dyson-draft", shiftDays(-1, 15), "claim_drafted", "Grok Bot prepared the Dyson Airwrap price-adjustment claim.", "p-dyson", "c-dyson"),
    event("a-dyson-drop", shiftDays(-3, 15), "price_drop", "Tiger Data detected a price drop: Dyson Airwrap fell from $599.00 to $549.00.", "p-dyson"),
    event("a-lulu", shiftDays(-3, 9), "purchase_found", "Sentient OS discovered a purchase receipt: Lululemon Align Leggings, $98.00.", "p-lulu"),
    event("a-kindle-found", shiftDays(-4, 8), "purchase_found", "Sentient OS discovered a purchase receipt: Kindle Paperwhite, $149.00.", "p-kindle"),
    event("a-allbirds-vault", shiftDays(-4, 11), "vault_recorded", "Solana vault was credited $20.00 from the Allbirds Tree Runner refund.", "p-allbirds", "c-allbirds"),
    event("a-allbirds-refund", shiftDays(-4, 10), "refund_received", "Nessie confirmed a $20.00 refund for the Allbirds Tree Runner.", "p-allbirds", "c-allbirds"),
    event("a-ninja-found", shiftDays(-6, 18), "purchase_found", "Sentient OS discovered a purchase receipt: Ninja Air Fryer, $120.00 at Target.", "p-ninja"),
    event("a-sony-found", shiftDays(-8, 13), "purchase_found", "Sentient OS discovered a purchase receipt: Sony WH-1000XM5, $399.00 at Best Buy.", "p-sony"),
    event("a-breville", shiftDays(-10, 12), "price_checked", "The Williams Sonoma adjustment window for the Breville Bambino closed before the price drop.", "p-breville"),
    event("a-adidas-vault", shiftDays(-16, 15), "vault_recorded", "Solana vault was credited $10.00 from the Adidas Samba refund.", "p-adidas", "c-adidas"),
    event("a-adidas-refund", shiftDays(-16, 14), "refund_received", "Nessie confirmed a $10.00 refund for the Adidas Samba.", "p-adidas", "c-adidas"),
    event("a-patagonia-vault", shiftDays(-40, 12), "vault_recorded", "Solana vault was credited $30.00 from the Patagonia Nano Puff refund.", "p-patagonia", "c-patagonia"),
    event("a-patagonia-refund", shiftDays(-40, 11), "refund_received", "Nessie confirmed a $30.00 refund for the Patagonia Nano Puff.", "p-patagonia", "c-patagonia"),
  ];
}

export function createSeed() {
  const purchases: TrackedPurchase[] = SEED.map((item) => ({
    id: item.id,
    user_id: USER_ID,
    retailer: item.retailer,
    product_name: item.name,
    product_url: null,
    price_paid_cents: item.paid,
    purchased_at: shiftDays(-item.purchasedDays, 10),
    order_number: item.order,
    product_id: item.productId,
    source: item.source,
    nessie_purchase_id: item.source === "nessie" ? `nessie-${item.id}` : null,
    adjustment_window_ends: item.windowDays == null ? null : shiftDays(-item.purchasedDays + item.windowDays, 23),
    current_price_cents: item.current,
    status: item.status,
    art: item.art,
    policy_summary: item.policy,
    policy_window_days: item.policyWindow,
    eligibility_explanation: item.explanation,
    price_history: buildHistory(item.retailer, item.paid, item.current, item.dropDaysAgo),
    qualifies: item.qualifies,
  }));

  const claims: Claim[] = SEED.flatMap((item) => {
    if (!item.claim) return [];
    const created = item.claim.createdHoursAgo != null
      ? shiftHours(-item.claim.createdHoursAgo)
      : shiftDays(-(item.claim.createdDaysAgo ?? 1), 15);
    const submitted = item.claim.submittedDaysAgo != null ? shiftDays(-item.claim.submittedDaysAgo, 16) : null;
    const refundAt = item.claim.refundDaysAgo != null ? shiftDays(-item.claim.refundDaysAgo, 11) : null;
    const claim: Claim = {
      id: item.claim.id,
      user_id: USER_ID,
      purchase_id: item.id,
      retailer: item.retailer,
      refund_cents: Math.max(0, item.paid - item.current),
      status: item.claim.status,
      explanation: item.explanation,
      created_at: created,
      submitted_at: submitted,
      refund_received_at: refundAt,
      nessie_deposit_id: refundAt ? `nessie-${item.claim.id}` : null,
      solana_tx_signature: refundAt ? SIGNATURES[item.claim.id] ?? null : null,
    };
    return [claim];
  });

  const vaultTransactions = claims
    .filter((claim) => claim.status === "refund_received")
    .map((claim) => {
      const purchase = purchases.find((item) => item.id === claim.purchase_id);
      const created = new Date(new Date(claim.refund_received_at ?? claim.created_at).getTime() + 60 * 60 * 1000).toISOString();
      return {
        id: `vault-${claim.id}`,
        claim_id: claim.id,
        purchase_id: claim.purchase_id,
        created_at: created,
        amount_cents: claim.refund_cents,
        status: "confirmed" as const,
        signature: claim.solana_tx_signature ?? `sim-${claim.id}`,
        description: `Savings deposit · ${purchase?.product_name ?? claim.retailer}`,
      };
    });

  const bankTransactions = claims
    .filter((claim) => claim.status === "refund_received")
    .map((claim) => {
      const purchase = purchases.find((item) => item.id === claim.purchase_id);
      return {
        id: `bank-${claim.id}`,
        claim_id: claim.id,
        purchase_id: claim.purchase_id,
        posted_at: claim.refund_received_at ?? claim.created_at,
        amount_cents: claim.refund_cents,
        description: `PRICE ADJUSTMENT · ${purchase?.product_name ?? claim.retailer}`,
        status: "posted" as const,
        account_mask: "4821",
      };
    });

  return {
    purchases,
    claims,
    activity: buildActivity(),
    vaultTransactions,
    bankTransactions,
  };
}
