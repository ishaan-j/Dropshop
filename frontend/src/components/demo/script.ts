export const DEMO_STAGES = [
  { id: 1, agent: "Sentient OS", role: "Receipt Hunter", title: "Receipt discovery", duration: 4200 },
  { id: 2, agent: "Tiger Data", role: "Price Tracker", title: "Price drop detection", duration: 4500 },
  { id: 3, agent: "Gemini", role: "Eligibility Analyzer", title: "Eligibility verification", duration: 4200 },
  { id: 4, agent: "Grok Bot", role: "Claim Agent", title: "Automated claim filing", duration: 5600 },
  { id: 5, agent: "Nessie", role: "Refund Verifier", title: "Refund confirmation", duration: 4000 },
  { id: 6, agent: "Solana", role: "Savings Vault", title: "Vault deposit", duration: 4800 },
] as const;

export const DEMO_TOTAL = DEMO_STAGES.reduce((sum, stage) => sum + stage.duration, 0);
export const COMMIT_AT = 0.72;

export const STAGE_TOASTS: Record<number, string> = {
  1: "Purchase discovered: Nike Air Max 270",
  2: "Price drop detected: $40.00",
  3: "You qualify for a $40 refund",
  4: "Refund claim submitted",
  5: "Refund received",
  6: "$40 added to your savings vault",
};

export function demoPosition(elapsed: number) {
  let cursor = 0;
  for (const stage of DEMO_STAGES) {
    if (elapsed < cursor + stage.duration) {
      return { stage: stage.id, progress: (elapsed - cursor) / stage.duration };
    }
    cursor += stage.duration;
  }
  return { stage: 6 as const, progress: 1 };
}

export function demoHeadline(stage: number, progress: number, phase: string) {
  if (phase === "complete" || (stage === 6 && progress > 0.9)) {
    return "Success! DropShop just recovered $40 for you.";
  }
  if (stage === 1 && progress > 0.55) return "Purchase discovered!";
  if (stage === 2 && progress > 0.6) return "Price drop detected!";
  if (stage === 3 && progress > 0.62) return "You qualify for a $40 refund!";
  if (stage === 4 && progress > 0.78) return "Refund claim submitted successfully!";
  if (stage === 5 && progress > 0.6) return "Refund received!";
  if (stage === 6 && progress > 0.72) return "$40 added to your savings vault!";
  const current = DEMO_STAGES.find((item) => item.id === stage);
  return current ? `${current.agent} is working` : "Press start to run the live demo";
}
