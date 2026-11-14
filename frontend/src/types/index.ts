// Mirror of backend/app/models.py, so change both together. Money is integer cents; dates are ISO strings.

export type PurchaseStatus = "monitoring" | "drop_detected" | "claim_pending" | "claimed" | "expired";
export type PurchaseSource = "sentient" | "email" | "manual" | "nessie";
export type ClaimStatus =
  | "awaiting_approval"
  | "submitting"
  | "submitted"
  | "refund_received"
  | "rejected"
  | "failed";
export type AgentEventKind =
  | "purchase_found"
  | "price_checked"
  | "price_drop"
  | "eligibility_checked"
  | "claim_drafted"
  | "claim_submitting"
  | "claim_submitted"
  | "refund_received"
  | "vault_recorded"
  | "error";

export interface PurchaseCreate {
  retailer: string;
  product_name: string;
  product_url?: string | null;
  price_paid_cents: number;
  purchased_at: string;
  order_number?: string | null;
}

export interface Purchase extends PurchaseCreate {
  id: string;
  user_id: string;
  product_id: string;
  source: PurchaseSource;
  nessie_purchase_id: string | null;
  adjustment_window_ends: string | null;
  current_price_cents: number | null;
  status: PurchaseStatus;
}

export interface PricePoint {
  time: string;
  retailer: string;
  price_cents: number;
}

export interface Claim {
  id: string;
  user_id: string;
  purchase_id: string;
  retailer: string;
  refund_cents: number;
  status: ClaimStatus;
  explanation: string;
  created_at: string;
  submitted_at: string | null;
  refund_received_at: string | null;
  nessie_deposit_id: string | null;
  solana_tx_signature: string | null;
}

export interface AgentEvent {
  id: string;
  user_id: string;
  time: string;
  kind: AgentEventKind;
  message: string;
  purchase_id: string | null;
  claim_id: string | null;
  screenshot_url: string | null;
}

export interface SavingsSummary {
  total_recovered_cents: number;
  pending_cents: number;
  claims_submitted: number;
  claims_won: number;
  vault_address: string | null;
  vault_balance_cents: number;
}

// --- Frontend models. The block above mirrors backend/app/models.py. ---

export type AgentActivity = AgentEvent;

export type ProductArt =
  | "nike"
  | "headphones"
  | "airpods"
  | "dyson"
  | "samba"
  | "leggings"
  | "kindle"
  | "fryer"
  | "jacket"
  | "espresso"
  | "runner"
  | "shirt"
  | "generic";

export interface User {
  id: string;
  name: string;
  email: string;
  bank_name: string;
  bank_mask: string;
  wallet_address: string;
}

/** Tiger Data price history for one product. */
export interface PriceHistory {
  product_id: string;
  points: PricePoint[];
}

/** Gemini eligibility decision. `simulated` is true when the demo produced it. */
export interface RefundEligibility {
  purchase_id: string;
  eligible: boolean;
  refund_cents: number;
  reason: string;
  policy_excerpt: string | null;
  confidence: number;
  simulated: boolean;
}

/** Nessie bank transaction. Amounts are integer cents. */
export interface BankTransaction {
  id: string;
  claim_id: string | null;
  purchase_id: string | null;
  posted_at: string;
  amount_cents: number;
  description: string;
  status: "pending" | "posted";
  account_mask: string;
}

/** Solana vault deposit. Amounts are integer cents. Signatures in demo mode are simulated. */
export interface VaultTransaction {
  id: string;
  claim_id: string | null;
  purchase_id: string | null;
  created_at: string;
  amount_cents: number;
  status: "pending" | "confirmed";
  signature: string;
  description: string;
}

/** A purchase plus the fields the UI needs that the API purchase does not carry. */
export interface TrackedPurchase extends Purchase {
  art: ProductArt;
  policy_summary: string;
  policy_window_days: number | null;
  eligibility_explanation: string;
  price_history: PricePoint[];
  /** True when the price-adjustment policy (demo or Gemini) says the user qualifies. */
  qualifies: boolean;
}

export interface LedgerState {
  purchases: TrackedPurchase[];
  claims: Claim[];
  activity: AgentEvent[];
  vaultTransactions: VaultTransaction[];
  bankTransactions: BankTransaction[];
}
