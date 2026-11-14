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
