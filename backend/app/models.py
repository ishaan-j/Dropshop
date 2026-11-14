"""Shared API contract. Mirrored in frontend/src/types/index.ts.

Money is integer cents. Datetimes are UTC. data_origin says whether a record
came from a live service, a sandbox/testnet, or the labeled demo.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

PurchaseStatus = Literal["monitoring", "drop_detected", "claim_pending", "claimed", "expired"]
PurchaseSource = Literal["sentient", "email", "manual", "nessie", "demo_sample"]
ClaimStatus = Literal[
    "awaiting_approval",
    "submitting",
    "submitted",
    "refund_received",
    "rejected",
    "failed",
]
DataOrigin = Literal["demo", "live", "sandbox"]
IntegrationMode = Literal["live", "sandbox", "demo", "not_connected", "error"]
EligibilityState = Literal["unknown", "eligible", "ineligible", "needs_review"]
AgentName = Literal["receipt", "price", "eligibility", "claim"]
AgentEventKind = Literal[
    "purchase_found",
    "price_checked",
    "price_drop",
    "eligibility_checked",
    "claim_drafted",
    "claim_submitting",
    "claim_submitted",
    "refund_received",
    "vault_recorded",
    "error",
    "email_discovered",
    "agent_started",
    "tool_invoked",
    "decision",
    "approval_required",
    "approval_received",
    "savings_allocated",
]


class PurchaseCreate(BaseModel):
    retailer: str
    product_name: str
    product_url: str | None = None
    product_id: str | None = None
    price_paid_cents: int = Field(gt=0)
    purchased_at: datetime
    order_number: str | None = None


class Purchase(PurchaseCreate):
    id: str
    user_id: str
    product_id: str
    source: PurchaseSource = "manual"
    data_origin: DataOrigin = "demo"
    nessie_purchase_id: str | None = None
    adjustment_window_ends: datetime | None = None
    current_price_cents: int | None = None
    price_source: str | None = None
    price_observed_at: datetime | None = None
    status: PurchaseStatus = "monitoring"
    eligibility: EligibilityState = "unknown"
    eligibility_reason: str = ""
    eligibility_evidence: list[str] = Field(default_factory=list)
    policy_url: str | None = None
    final_sale: bool = False
    created_at: datetime
    updated_at: datetime


class PricePoint(BaseModel):
    time: datetime
    retailer: str
    price_cents: int
    source: str = "unknown"
    data_origin: DataOrigin = "demo"
    product_url: str | None = None
    collection_status: str = "recorded"
    currency: str = "USD"
    in_stock: bool | None = None


class ExtractedItem(BaseModel):
    retailer: str | None = None
    product_name: str | None = None
    product_url: str | None = None
    product_id: str | None = None
    price_paid_cents: int | None = None
    purchased_at: datetime | None = None
    order_number: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ExtractedReceipt(BaseModel):
    """Untrusted extractor output. Callers must validate it against the source text."""

    retailer: str | None = None
    order_number: str | None = None
    purchased_at: datetime | None = None
    items: list[ExtractedItem] = Field(default_factory=list)
    extractor: Literal["gemini", "deterministic", "none"] = "none"
    warnings: list[str] = Field(default_factory=list)


class RetailerPolicy(BaseModel):
    retailer: str
    policy_url: str | None = None
    window_days: int | None = None
    conditions: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    summary: str = ""
    source_text: str = ""
    verified_at: datetime | None = None
    data_origin: DataOrigin = "demo"
    parser: Literal["deterministic", "gemini", "none"] = "deterministic"


class EligibilityResult(BaseModel):
    eligible: bool
    needs_review: bool = False
    refund_cents: int = 0
    reason: str
    evidence: list[str] = Field(default_factory=list)
    policy_excerpt: str | None = None
    # Decision is always the deterministic rules engine. This is not proof.
    confidence: float = 0.0
    decided_by: Literal["rules"] = "rules"
    model_comment: str | None = None


class Claim(BaseModel):
    id: str
    user_id: str
    purchase_id: str
    retailer: str
    product_name: str = ""
    refund_cents: int
    price_paid_cents: int | None = None
    current_price_cents: int | None = None
    status: ClaimStatus = "awaiting_approval"
    explanation: str = ""
    explanation_source: Literal["template", "gemini"] = "template"
    data_origin: DataOrigin = "demo"
    created_at: datetime
    submitted_at: datetime | None = None
    refund_received_at: datetime | None = None
    nessie_deposit_id: str | None = None
    solana_tx_signature: str | None = None
    policy_url: str | None = None
    evidence: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    manual_packet: str | None = None
    submission_note: str | None = None
    screenshots: list[str] = Field(default_factory=list)
    demo_submission_id: str | None = None


class AgentEvent(BaseModel):
    id: str
    user_id: str
    time: datetime
    kind: AgentEventKind
    message: str
    agent: AgentName | None = None
    run_id: str | None = None
    purchase_id: str | None = None
    claim_id: str | None = None
    screenshot_url: str | None = None
    data_origin: DataOrigin = "demo"


class AgentRun(BaseModel):
    id: str
    user_id: str
    agent: AgentName
    status: Literal["running", "completed", "error"]
    task: str
    started_at: datetime
    finished_at: datetime | None = None
    result_summary: str = ""
    error: str | None = None
    data_origin: DataOrigin = "demo"


class AgentSnapshot(BaseModel):
    name: AgentName
    title: str
    responsibility: str
    status: Literal["idle", "running", "error"]
    current_task: str | None = None
    last_run_at: datetime | None = None
    last_result: str | None = None
    last_error: str | None = None
    data_origin: DataOrigin | None = None


class Refund(BaseModel):
    id: str
    user_id: str
    claim_id: str
    amount_cents: int
    status: Literal["expected", "matched", "unmatched"]
    data_origin: DataOrigin
    source: str
    external_id: str | None = None
    explanation: str
    created_at: datetime


class SavingsAllocation(BaseModel):
    id: str
    user_id: str
    amount_cents: int
    kind: Literal["savings_earmark", "devnet_test", "demo_earmark"]
    data_origin: DataOrigin
    network: str | None = None
    signature: str | None = None
    confirmed: bool = False
    vault_address: str | None = None
    lamports: int | None = None
    created_at: datetime
    note: str = ""


class UserApproval(BaseModel):
    id: str
    user_id: str
    claim_id: str
    action: Literal["approve", "reject", "cancel"]
    created_at: datetime
    detail: str = ""


class ReceiptRecord(BaseModel):
    id: str
    user_id: str
    source: Literal["gmail", "sentient_knowledge", "demo_sample", "manual"]
    data_origin: DataOrigin
    external_id: str | None = None
    subject: str | None = None
    body_text: str
    created_at: datetime


class Preferences(BaseModel):
    user_id: str
    notify_price_drop: bool = True
    notify_deadline: bool = True
    notify_claim: bool = True
    sentient_read_enabled: bool = False
    delivery: Literal["not_connected"] = "not_connected"


class IntegrationStatus(BaseModel):
    id: str
    name: str
    mode: IntegrationMode
    detail: str
    checked_at: datetime


class SavingsSummary(BaseModel):
    total_recovered_cents: int
    pending_cents: int
    potential_cents: int
    claims_submitted: int
    claims_won: int
    vault_address: str | None = None
    vault_balance_lamports: int | None = None
    vault_balance_verified: bool = False
    vault_network: str = "devnet"
    data_note: str = ""


class DeadlineItem(BaseModel):
    purchase_id: str
    product_name: str
    retailer: str
    deadline: datetime
    data_origin: DataOrigin


class SavingsPoint(BaseModel):
    time: datetime
    total_recovered_cents: int
    data_origin: DataOrigin


class Dashboard(BaseModel):
    total_recovered_cents: int
    pending_refund_cents: int
    potential_savings_cents: int
    purchases_monitored: int
    purchase_count: int = 0
    price_drops_detected: int
    upcoming_deadlines: list[DeadlineItem]
    recent_activity: list[AgentEvent]
    savings_series: list[SavingsPoint]
    includes_demo_data: bool
    persistence: str
    vault_address: str | None = None
    vault_balance_lamports: int | None = None
    vault_balance_verified: bool = False
    vault_network: str = "devnet"
    integrations: list[IntegrationStatus]


class Opportunity(BaseModel):
    purchase_id: str
    claim_id: str | None = None
    product_name: str
    retailer: str
    purchased_at: datetime
    price_paid_cents: int
    current_price_cents: int | None
    difference_cents: int
    eligibility: EligibilityState
    reason: str
    evidence: list[str]
    policy_url: str | None
    deadline: datetime | None
    claim_status: ClaimStatus | None = None
    price_source: str | None
    data_origin: DataOrigin
    missing_information: list[str] = Field(default_factory=list)


class SessionResponse(BaseModel):
    token: str
    user_id: str
    expires_in: int
    note: str


class ScenarioResult(BaseModel):
    data_origin: Literal["demo"] = "demo"
    note: str
    purchases: list[Purchase]
    claims: list[Claim]
    events: list[AgentEvent]


class ClaimActionResult(BaseModel):
    claim: Claim
    submitted: bool
    note: str
