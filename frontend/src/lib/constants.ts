export const USER_ID = "demo-user";

export const DEMO_PURCHASE_ID = "demo-nike-air-max";
export const DEMO_CLAIM_ID = "demo-nike-claim";
export const DEMO_VAULT_ID = "demo-nike-vault";
export const DEMO_BANK_ID = "demo-nike-bank";
export const DEMO_SIGNATURE = "simNikeAirMax270VaultTx0000004";
export const DEMO_PAID_CENTS = 16000;
export const DEMO_CURRENT_CENTS = 12000;
export const DEMO_REFUND_CENTS = 4000;

export const PIPELINE = [
  { id: "receipt", title: "Receipt found", agent: "Sentient OS" },
  { id: "drop", title: "Price drop detected", agent: "Tiger Data" },
  { id: "eligible", title: "Eligibility verified", agent: "Gemini" },
  { id: "submitted", title: "Claim submitted", agent: "Grok Bot" },
  { id: "refund", title: "Refund confirmed", agent: "Nessie" },
  { id: "vault", title: "Vault credited", agent: "Solana" },
] as const;

export const CLAIM_TIMELINE = [
  "Price drop detected",
  "Eligibility verified",
  "Claim prepared",
  "Claim submitted",
  "Refund confirmed",
  "Savings vault credited",
] as const;

export const DEMO_POLICY_NOTE =
  "Simulated retailer policy for this hackathon demo. Not a verified policy statement.";
