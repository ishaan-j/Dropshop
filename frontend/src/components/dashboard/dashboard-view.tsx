"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { BadgeDollarSign, FileCheck2, ShoppingBag, TrendingDown } from "lucide-react";
import { Panel } from "@/components/page-header";
import { PurchaseCard } from "@/components/purchase-card";
import { SavingsChart } from "@/components/charts/savings-chart";
import { useCountUp } from "@/components/use-count-up";
import { claimForPurchase, computeMetrics, displayStatus, savingsSeries, type SavingsRange } from "@/lib/metrics";
import { firstName, formatCents, formatRelative } from "@/lib/utils";
import { useAppStore } from "@/store/app-store";

export function DashboardView() {
  const user = useAppStore((state) => state.user);
  const purchases = useAppStore((state) => state.purchases);
  const claims = useAppStore((state) => state.claims);
  const activity = useAppStore((state) => state.activity);
  const vault = useAppStore((state) => state.vaultTransactions);
  const emailConnected = useAppStore((state) => state.emailConnected);
  const [range, setRange] = useState<SavingsRange>("30d");
  const metrics = useMemo(() => computeMetrics(purchases, claims, vault), [purchases, claims, vault]);
  const series = useMemo(() => savingsSeries(vault, range), [vault, range]);
  const drops = purchases
    .map((purchase) => ({ purchase, claim: claimForPurchase(claims, purchase.id) }))
    .filter((item) => {
      const status = displayStatus(item.purchase, item.claim);
      return status === "eligible" || status === "pending" || status === "processing" || status === "submitted";
    })
    .sort((a, b) => (b.purchase.price_paid_cents - (b.purchase.current_price_cents ?? 0)) - (a.purchase.price_paid_cents - (a.purchase.current_price_cents ?? 0)))
    .slice(0, 4);
  const feed = [...activity].sort((a, b) => b.time.localeCompare(a.time)).slice(0, 6);
  const deposits = [...vault].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 3);

  return (
    <div>
      {!emailConnected ? (
        <div className="mb-6 flex flex-col gap-3 rounded-xl border border-[#E4E7DC] bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-[#3E4C45]">Sample purchases are already loaded. Connect email when you want the setup story.</p>
          <Link href="/onboarding" className="text-sm font-semibold text-[#12372A] underline-offset-4 hover:underline">Finish setup</Link>
        </div>
      ) : null}
      <p className="text-sm text-[#5E6B63]">Welcome back, {firstName(user.name)}!</p>
      <h1 className="mt-1 text-3xl font-semibold tracking-tight text-[#12372A]">Your money-saving assistant has been busy.</h1>

      <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric icon={BadgeDollarSign} label="Total money recovered" value={metrics.recoveredCents} note="Confirmed refunds" />
        <Metric icon={TrendingDown} label="Potential refunds" value={metrics.potentialCents} note="Eligible, not yet received" />
        <Metric icon={ShoppingBag} label="Purchases being tracked" value={metrics.trackedCount} money={false} note="In your price tracker" />
        <Metric icon={FileCheck2} label="Active claims" value={metrics.activeClaims} money={false} note="Waiting on you or a retailer" />
      </div>

      <Panel className="mt-6">
        <SavingsChart data={series} range={range} onRange={setRange} />
      </Panel>

      <div className="mt-8 flex items-end justify-between">
        <h2 className="text-lg font-semibold text-[#12372A]">Recent price drops</h2>
        <Link href="/tracker" className="text-sm font-medium text-[#12372A] underline-offset-4 hover:underline">View tracker</Link>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {drops.map((item) => <PurchaseCard key={item.purchase.id} purchase={item.purchase} claim={item.claim} />)}
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Panel>
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-[#12372A]">AI activity</h2>
            <Link href="/activity" className="text-sm font-medium underline-offset-4 hover:underline">Open feed</Link>
          </div>
          <ul className="mt-4 divide-y divide-[#E4E7DC]">
            {feed.map((item) => (
              <li key={item.id} className="py-3">
                <p className="text-sm leading-5">{item.message}</p>
                <p className="mt-1 text-xs text-[#5E6B63]">{formatRelative(item.time)}</p>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel>
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-[#12372A]">Savings vault</h2>
            <Link href="/vault" className="text-sm font-medium underline-offset-4 hover:underline">View vault</Link>
          </div>
          <p className="mt-3 text-3xl font-semibold tabular-nums text-[#12372A]">{formatCents(metrics.vaultBalanceCents)}</p>
          <p className="text-sm text-[#5E6B63]">Deposited refunds. Pending deposits {formatCents(metrics.pendingDepositCents)}.</p>
          <ul className="mt-4 divide-y divide-[#E4E7DC]">
            {deposits.map((tx) => (
              <li key={tx.id} className="flex items-center justify-between py-3 text-sm">
                <span>{tx.description}</span>
                <span className="font-semibold tabular-nums text-[#146C3A]">+{formatCents(tx.amount_cents)}</span>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
  note,
  money = true,
}: {
  icon: typeof ShoppingBag;
  label: string;
  value: number;
  note: string;
  money?: boolean;
}) {
  const display = useCountUp(value);
  return (
    <Panel>
      <div className="flex items-center justify-between">
        <p className="text-sm text-[#5E6B63]">{label}</p>
        <Icon className="h-4 w-4 text-[#12372A]" />
      </div>
      <p className="mt-3 text-3xl font-semibold tabular-nums tracking-tight text-[#12372A]">
        {money ? formatCents(display) : display}
      </p>
      <p className="mt-1 text-xs text-[#5E6B63]">{note}</p>
    </Panel>
  );
}
