export type DataOrigin = "demo" | "live" | "sandbox";
export type IntegrationMode = "live" | "sandbox" | "demo" | "not_connected" | "error";
export type PurchaseStatus = "monitoring" | "drop_detected" | "claim_pending" | "claimed" | "expired";
export type Eligibility = "unknown" | "eligible" | "ineligible" | "needs_review";
export type ClaimStatus =
  | "awaiting_approval"
  | "submitting"
  | "submitted"
  | "refund_received"
  | "rejected"
  | "failed";

export interface Purchase {
  id: string;
  user_id: string;
  retailer: string;
  product_name: string;
  product_url?: string | null;
  product_id: string;
  price_paid_cents: number;
  purchased_at: string;
  order_number?: string | null;
  source: string;
  data_origin: DataOrigin;
  current_price_cents: number | null;
  price_source: string | null;
  price_observed_at: string | null;
  adjustment_window_ends: string | null;
  status: PurchaseStatus;
  eligibility: Eligibility;
  eligibility_reason: string;
  eligibility_evidence: string[];
  policy_url: string | null;
  final_sale: boolean;
}

export interface PricePoint {
  time: string;
  retailer: string;
  price_cents: number;
  source: string;
  data_origin: DataOrigin;
  collection_status: string;
}

export interface Claim {
  id: string;
  user_id: string;
  purchase_id: string;
  retailer: string;
  product_name: string;
  refund_cents: number;
  price_paid_cents: number | null;
  current_price_cents: number | null;
  status: ClaimStatus;
  explanation: string;
  explanation_source: "template" | "gemini";
  data_origin: DataOrigin;
  created_at: string;
  submitted_at: string | null;
  policy_url: string | null;
  evidence: string[];
  missing_information: string[];
  manual_packet: string | null;
  submission_note: string | null;
  screenshots: string[];
  nessie_deposit_id: string | null;
  solana_tx_signature: string | null;
}

export interface AgentEvent {
  id: string;
  user_id: string;
  time: string;
  kind: string;
  message: string;
  agent: string | null;
  run_id: string | null;
  purchase_id: string | null;
  claim_id: string | null;
  screenshot_url: string | null;
  data_origin: DataOrigin;
}

export interface AgentSnapshot {
  name: string;
  title: string;
  responsibility: string;
  status: "idle" | "running" | "error";
  current_task: string | null;
  last_run_at: string | null;
  last_result: string | null;
  last_error: string | null;
  data_origin: DataOrigin | null;
}

export interface IntegrationStatus {
  id: string;
  name: string;
  mode: IntegrationMode;
  detail: string;
  checked_at: string;
}

export interface DeadlineItem {
  purchase_id: string;
  product_name: string;
  retailer: string;
  deadline: string;
  data_origin: DataOrigin;
}

export interface SavingsPoint {
  time: string;
  total_recovered_cents: number;
  data_origin: DataOrigin;
}

export interface Dashboard {
  total_recovered_cents: number;
  pending_refund_cents: number;
  potential_savings_cents: number;
  purchases_monitored: number;
  purchase_count: number;
  price_drops_detected: number;
  upcoming_deadlines: DeadlineItem[];
  recent_activity: AgentEvent[];
  savings_series: SavingsPoint[];
  includes_demo_data: boolean;
  persistence: string;
  vault_address: string | null;
  vault_balance_lamports: number | null;
  vault_balance_verified: boolean;
  vault_network: string;
  integrations: IntegrationStatus[];
}

export interface Opportunity {
  purchase_id: string;
  claim_id: string | null;
  product_name: string;
  retailer: string;
  purchased_at: string;
  price_paid_cents: number;
  current_price_cents: number | null;
  difference_cents: number;
  eligibility: Eligibility;
  reason: string;
  evidence: string[];
  policy_url: string | null;
  deadline: string | null;
  claim_status: ClaimStatus | null;
  price_source: string | null;
  data_origin: DataOrigin;
  missing_information: string[];
}

export interface Allocation {
  id: string;
  amount_cents: number;
  kind: string;
  data_origin: DataOrigin;
  network: string | null;
  signature: string | null;
  confirmed: boolean;
  vault_address: string | null;
  lamports: number | null;
  created_at: string;
  note: string;
}

export interface VaultView {
  network: string;
  mode: IntegrationMode;
  detail: string;
  rpc_url: string | null;
  vault_address: string | null;
  wallet_address: string | null;
  balance_lamports: number | null;
  balance_verified: boolean;
  program_deployed: boolean;
  allocations: Allocation[];
}

export interface Preferences {
  user_id: string;
  notify_price_drop: boolean;
  notify_deadline: boolean;
  notify_claim: boolean;
  sentient_read_enabled: boolean;
  delivery: "not_connected";
}

export interface Refund {
  id: string;
  claim_id: string;
  amount_cents: number;
  status: string;
  data_origin: DataOrigin;
  source: string;
  external_id: string | null;
  explanation: string;
  created_at: string;
}
