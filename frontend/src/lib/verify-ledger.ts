import type { LedgerState } from "../types";
import { applyDemoStage, resetDemoRun, withFiledClaim } from "./demo-reducer";
import { computeMetrics, savingsSeries } from "./metrics";
import { createSeed } from "./mock-data";

function unique(ids: string[], label: string) {
  if (new Set(ids).size !== ids.length) throw new Error(`Duplicate ${label}`);
}

function assertSeries(vault: Parameters<typeof savingsSeries>[0], expected: number) {
  for (const range of ["7d", "30d", "all"] as const) {
    const series = savingsSeries(vault, range);
    const last = series[series.length - 1]?.balance ?? 0;
    if (last !== expected) throw new Error(`${range} chart ends at ${last}, expected ${expected}`);
    for (let i = 1; i < series.length; i += 1) {
      if (series[i].balance < series[i - 1].balance) throw new Error(`${range} chart went backwards`);
    }
  }
}

function assertRefundsMatchVault(state: LedgerState) {
  for (const claim of state.claims.filter((item) => item.status === "refund_received")) {
    const txs = state.vaultTransactions.filter((tx) => tx.claim_id === claim.id && tx.status === "confirmed");
    if (txs.length !== 1) throw new Error(`Claim ${claim.id} has ${txs.length} vault deposits`);
    if (txs[0].amount_cents !== claim.refund_cents) throw new Error(`Claim ${claim.id} vault amount mismatch`);
  }
}

/** Throws if the demo ledger double-counts money or drifts from the scripted totals. */
export function verifyLedger() {
  const seed = createSeed();
  unique(seed.purchases.map((item) => item.id), "purchase ids");
  unique(seed.claims.map((item) => item.id), "claim ids");
  unique(seed.vaultTransactions.map((item) => item.id), "vault ids");
  assertRefundsMatchVault(seed);

  const initial = computeMetrics(seed.purchases, seed.claims, seed.vaultTransactions);
  if (initial.recoveredCents !== 6000) throw new Error(`recovered ${initial.recoveredCents}`);
  if (initial.vaultBalanceCents !== 6000) throw new Error(`vault ${initial.vaultBalanceCents}`);
  if (initial.potentialCents !== 17100) throw new Error(`potential ${initial.potentialCents}`);
  if (initial.pendingDepositCents !== 0) throw new Error(`pending ${initial.pendingDepositCents}`);
  if (initial.activeClaims !== 3) throw new Error(`active ${initial.activeClaims}`);
  if (initial.trackedCount !== 11) throw new Error(`tracked ${initial.trackedCount}`);
  if (seed.purchases.some((item) => item.id.startsWith("demo-"))) throw new Error("seed includes the live-demo purchase");
  assertSeries(seed.vaultTransactions, 6000);

  const eligible = applyDemoStage(seed, 3);
  const afterGemini = computeMetrics(eligible.purchases, eligible.claims, eligible.vaultTransactions);
  if (afterGemini.potentialCents !== 21100) throw new Error(`stage 3 potential ${afterGemini.potentialCents}`);
  if (afterGemini.recoveredCents !== 6000) throw new Error("stage 3 changed recovered money");

  const refunded = applyDemoStage(seed, 5);
  const afterBank = computeMetrics(refunded.purchases, refunded.claims, refunded.vaultTransactions);
  if (afterBank.recoveredCents !== 10000) throw new Error(`stage 5 recovered ${afterBank.recoveredCents}`);
  if (afterBank.vaultBalanceCents !== 6000) throw new Error(`stage 5 vault ${afterBank.vaultBalanceCents}`);
  if (afterBank.pendingDepositCents !== 4000) throw new Error(`stage 5 pending ${afterBank.pendingDepositCents}`);
  if (afterBank.potentialCents !== 17100) throw new Error(`stage 5 potential ${afterBank.potentialCents}`);

  let done = applyDemoStage(seed, 6);
  done = applyDemoStage(done, 6);
  const finalMetrics = computeMetrics(done.purchases, done.claims, done.vaultTransactions);
  if (finalMetrics.recoveredCents !== 10000) throw new Error(`final recovered ${finalMetrics.recoveredCents}`);
  if (finalMetrics.vaultBalanceCents !== 10000) throw new Error(`final vault ${finalMetrics.vaultBalanceCents}`);
  if (finalMetrics.pendingDepositCents !== 0) throw new Error(`final pending ${finalMetrics.pendingDepositCents}`);
  if (finalMetrics.potentialCents !== 17100) throw new Error(`final potential ${finalMetrics.potentialCents}`);
  if (finalMetrics.trackedCount !== 12) throw new Error(`final tracked ${finalMetrics.trackedCount}`);
  assertSeries(done.vaultTransactions, 10000);
  assertRefundsMatchVault(done);

  const replayed = applyDemoStage(resetDemoRun(done), 6);
  const replayMetrics = computeMetrics(replayed.purchases, replayed.claims, replayed.vaultTransactions);
  if (replayMetrics.recoveredCents !== 10000 || replayMetrics.vaultBalanceCents !== 10000) {
    throw new Error("replay duplicated the $40 refund");
  }
  if (replayed.claims.filter((claim) => claim.purchase_id === "demo-nike-air-max").length !== 1) {
    throw new Error("replay created more than one demo claim");
  }

  const filed = withFiledClaim(seed, "p-sony");
  const filedAgain = withFiledClaim(filed, "p-sony");
  if (filed.claims.length !== seed.claims.length + 1) throw new Error("file claim did not add one claim");
  if (filedAgain.claims.length !== filed.claims.length) throw new Error("file claim duplicated a claim");
  const filedMetrics = computeMetrics(filed.purchases, filed.claims, filed.vaultTransactions);
  if (filedMetrics.recoveredCents !== 6000) throw new Error("filing a claim counted it as recovered");
  if (filedMetrics.potentialCents !== 17100) throw new Error("filing a claim changed potential refunds");
}

verifyLedger();
