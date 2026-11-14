"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import { PageHeader, Panel, DemoNote } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { SavingsChart } from "@/components/charts/savings-chart";
import { useCountUp } from "@/components/use-count-up";
import { computeMetrics, depositedThisMonth, savingsSeries, type SavingsRange } from "@/lib/metrics";
import { formatCents, formatDate, shorten } from "@/lib/utils";
import { useAppStore } from "@/store/app-store";

export function VaultView() {
  const vault = useAppStore((state) => state.vaultTransactions);
  const claims = useAppStore((state) => state.claims);
  const purchases = useAppStore((state) => state.purchases);
  const connected = useAppStore((state) => state.walletConnected);
  const address = useAppStore((state) => state.user.wallet_address);
  const setConnected = useAppStore((state) => state.setWalletConnected);
  const [range, setRange] = useState<SavingsRange>("all");
  const [pending, setPending] = useState(false);
  const metrics = useMemo(() => computeMetrics(purchases, claims, vault), [purchases, claims, vault]);
  const month = useMemo(() => depositedThisMonth(vault), [vault]);
  const series = useMemo(() => savingsSeries(vault, range), [vault, range]);
  const balance = useCountUp(metrics.vaultBalanceCents);
  const txs = [...vault].sort((a, b) => b.created_at.localeCompare(a.created_at));
  const waiting = claims.filter((claim) => claim.status === "submitted" || claim.status === "submitting");

  async function toggleWallet() {
    if (connected) {
      setConnected(false);
      toast.success("Wallet disconnected");
      return;
    }
    setPending(true);
    await new Promise((resolve) => setTimeout(resolve, 700));
    setConnected(true);
    setPending(false);
    toast.success("Wallet connected (simulated)");
  }

  return (
    <div>
      <PageHeader
        eyebrow="Savings vault"
        title="Recovered money, kept in one place"
        description="Think of this as a savings balance. The Solana signatures show how an on-chain record would look. None of these transfers were broadcast."
      />
      <div className="rounded-xl bg-[#12372A] p-6 text-white sm:p-8">
        <div className="flex items-start justify-between gap-4">
          <p className="text-sm text-white/70">Vault balance</p>
          <span className="rounded-full bg-[#C8F55A] px-2 py-1 text-xs font-semibold text-[#12372A]">Simulated</span>
        </div>
        <p className="mt-3 text-5xl font-semibold tabular-nums tracking-tight">{formatCents(balance)}</p>
        <p className="mt-2 max-w-lg text-sm text-white/70">Confirmed refunds that have been deposited. You do not need a crypto wallet to understand the balance.</p>
        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Button variant="lime" onClick={toggleWallet} disabled={pending}>
            {pending ? "Connecting…" : connected ? "Disconnect wallet" : "Connect wallet"}
          </Button>
          {connected ? <p className="font-mono text-xs text-white/80">{shorten(address, 6, 4)} · simulated</p> : <p className="text-sm text-white/70">No wallet connected</p>}
        </div>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <Panel>
          <p className="text-sm text-[#5E6B63]">Total lifetime refunds</p>
          <p className="mt-2 text-2xl font-semibold tabular-nums">{formatCents(metrics.recoveredCents)}</p>
        </Panel>
        <Panel>
          <p className="text-sm text-[#5E6B63]">Deposited this month</p>
          <p className="mt-2 text-2xl font-semibold tabular-nums">{formatCents(month)}</p>
        </Panel>
        <Panel>
          <p className="text-sm text-[#5E6B63]">Pending deposits</p>
          <p className="mt-2 text-2xl font-semibold tabular-nums">{formatCents(metrics.pendingDepositCents)}</p>
          <p className="mt-1 text-xs text-[#5E6B63]">Confirmed by the bank, not in the vault yet.</p>
        </Panel>
      </div>

      <Panel className="mt-4">
        <SavingsChart data={series} range={range} onRange={setRange} />
      </Panel>

      <div className="mt-4"><DemoNote>Balances, deposits, and blockchain signatures on this page are simulated for the hackathon.</DemoNote></div>

      {waiting.length > 0 ? (
        <Panel className="mt-4">
          <h2 className="font-semibold text-[#12372A]">Claims still in progress</h2>
          <p className="mt-1 text-sm text-[#5E6B63]">These amounts are not in the vault balance.</p>
          <ul className="mt-3 divide-y divide-[#E4E7DC]">
            {waiting.map((claim) => (
              <li key={claim.id} className="flex justify-between py-3 text-sm">
                <span>{claim.retailer}</span>
                <span className="tabular-nums">{formatCents(claim.refund_cents)}</span>
              </li>
            ))}
          </ul>
        </Panel>
      ) : null}

      <Panel className="mt-4">
        <h2 className="font-semibold text-[#12372A]">Recent vault transactions</h2>
        {txs.length === 0 ? <p className="mt-4 text-sm text-[#5E6B63]">No deposits yet.</p> : null}
        <ul className="mt-2 divide-y divide-[#E4E7DC]">
          {txs.map((tx) => (
            <li key={tx.id} className="flex flex-col gap-2 py-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-medium">{tx.description}</p>
                <p className="mt-1 text-xs text-[#5E6B63]">{formatDate(tx.created_at)} · {tx.status}</p>
                <p className="mt-1 font-mono text-xs text-[#5E6B63]">{shorten(tx.signature, 6, 4)} · simulated signature</p>
              </div>
              <p className="font-semibold tabular-nums text-[#146C3A]">+{formatCents(tx.amount_cents)}</p>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}
