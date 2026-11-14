"use client";

import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { PriceChart } from "@/components/charts/price-chart";
import { ProductArt } from "@/components/product-art";
import { Panel } from "@/components/page-header";
import { StatusNote } from "@/components/status-note";
import { StatusBadge } from "@/components/status-badge";
import { windowCopy } from "@/components/purchase-card";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { DEMO_POLICY_NOTE } from "@/lib/constants";
import { useBackend } from "@/lib/live";
import { claimForPurchase, displayStatus, isVaulted } from "@/lib/metrics";
import { fileClaim } from "@/lib/services";
import { dropPercent, formatCents, formatDate, priceGap } from "@/lib/utils";
import { useAppStore } from "@/store/app-store";

const SOURCE: Record<string, string> = {
  sentient: "Sentient OS",
  email: "Email receipt",
  nessie: "Card transaction",
  manual: "Added manually",
};

export function ProductDetailView({ id }: { id: string }) {
  const purchase = useAppStore((state) => state.purchases.find((item) => item.id === id));
  const claim = useAppStore((state) => claimForPurchase(state.claims, id));
  const vaulted = useAppStore((state) => (claim ? isVaulted(claim, state.vaultTransactions) : false));
  const minRefund = useAppStore((state) => state.settings.minRefundCents);
  const backend = useBackend();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);

  if (!purchase) {
    return (
      <Panel>
        <h1 className="text-xl font-semibold text-[#12372A]">Purchase not found</h1>
        <p className="mt-2 text-sm text-[#5E6B63]">It may have been cleared by Reset Demo.</p>
        <Link href="/tracker" className="mt-4 inline-block text-sm font-semibold underline-offset-4 hover:underline">Back to tracker</Link>
      </Panel>
    );
  }

  const current = purchase;
  const status = displayStatus(current, claim);
  const gap = priceGap(current.price_paid_cents, current.current_price_cents);
  const canFile = status === "eligible" && (!claim || claim.status === "failed");
  const belowMin = gap > 0 && gap < minRefund;

  async function confirm() {
    setPending(true);
    try {
      const result = await fileClaim(current.id);
      if (result) toast.success("Refund claim submitted");
      else toast.message("This purchase already has a claim");
      setOpen(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not file the claim");
    } finally {
      setPending(false);
    }
  }

  return (
    <div>
      <Link href="/tracker" className="text-sm font-medium text-[#5E6B63] hover:text-[#17211C]">← Price tracker</Link>
      <div className="mt-4 grid gap-6 lg:grid-cols-[280px_1fr]">
        <ProductArt art={purchase.art} label={purchase.product_name} className="h-72 rounded-xl border border-[#E4E7DC]" />
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-3xl font-semibold tracking-tight text-[#12372A]">{purchase.product_name}</h1>
            <StatusBadge status={status} />
          </div>
          <p className="mt-2 text-sm text-[#5E6B63]">{purchase.retailer} · Order {purchase.order_number}</p>
          <div className="mt-6 flex flex-wrap gap-8">
            <div>
              <p className="text-xs text-[#5E6B63]">Paid</p>
              <p className="text-xl font-semibold tabular-nums line-through">{formatCents(purchase.price_paid_cents)}</p>
            </div>
            <div>
              <p className="text-xs text-[#5E6B63]">Current</p>
              <p className="text-xl font-semibold tabular-nums">{formatCents(purchase.current_price_cents ?? purchase.price_paid_cents)}</p>
            </div>
            <div>
              <p className="text-xs text-[#5E6B63]">Potential refund</p>
              <p className="text-xl font-semibold tabular-nums text-[#146C3A]">{gap > 0 ? formatCents(gap) : "—"}</p>
            </div>
          </div>
          <p className="mt-3 text-sm text-[#5E6B63]">
            {dropPercent(purchase.price_paid_cents, purchase.current_price_cents) > 0
              ? `${dropPercent(purchase.price_paid_cents, purchase.current_price_cents)}% lower · `
              : ""}
            {windowCopy(purchase, status)}
          </p>
          {belowMin ? <p className="mt-3 text-sm text-[#8A5A00]">This is below your {formatCents(minRefund)} minimum. You can still file it.</p> : null}
          <div className="mt-6 flex flex-wrap gap-2">
            {canFile ? <Button onClick={() => setOpen(true)}>File refund claim</Button> : null}
            {claim ? <Link href="/claims" className="inline-flex h-10 items-center rounded-lg border border-[#D5DACB] bg-white px-4 text-sm font-semibold">View claim</Link> : null}
          </div>
        </div>
      </div>

      <Panel className="mt-6">
        <h2 className="font-semibold text-[#12372A]">Price history</h2>
        <p className="text-sm text-[#5E6B63]">The dashed line is what you paid.</p>
        <div className="mt-2">
          <PriceChart points={purchase.price_history} paidCents={purchase.price_paid_cents} />
        </div>
      </Panel>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Panel>
          <h2 className="font-semibold text-[#12372A]">Purchase</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <Row label="Purchased" value={formatDate(purchase.purchased_at)} />
            <Row label="Source" value={SOURCE[purchase.source] ?? purchase.source} />
            <Row label="Deadline" value={purchase.adjustment_window_ends ? formatDate(purchase.adjustment_window_ends) : "None"} />
            <Row label="Vault" value={claim && vaulted ? "Credited" : "Not deposited"} />
          </dl>
        </Panel>
        <Panel>
          <h2 className="font-semibold text-[#12372A]">Policy and eligibility</h2>
          <div className="mt-3">
            <StatusNote
              demo={DEMO_POLICY_NOTE}
              live={() => "This is the policy the backend checks eligibility against. The demo policies are simplified, not verified policy statements."}
            />
          </div>
          <p className="mt-4 text-sm leading-6">{purchase.policy_summary}</p>
          <p className="mt-3 text-sm leading-6 text-[#3E4C45]">{purchase.eligibility_explanation}</p>
        </Panel>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogTitle>File this refund claim?</DialogTitle>
          <DialogDescription>
            {backend
              ? `Approve the ${formatCents(gap)} claim for ${purchase.product_name}. The claim bot files it on DropShop's demo store, not with ${purchase.retailer}.`
              : `Submit a simulated ${formatCents(gap)} claim to ${purchase.retailer} for ${purchase.product_name}. DropShop will not contact the retailer.`}
          </DialogDescription>
          <div className="mt-6 flex justify-end gap-2">
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={confirm} disabled={pending}>{pending ? "Submitting…" : "Submit claim"}</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-[#5E6B63]">{label}</dt>
      <dd className="text-right font-medium">{value}</dd>
    </div>
  );
}
