import Link from "next/link";
import { ProductArt } from "@/components/product-art";
import { StatusBadge } from "@/components/status-badge";
import { Sparkline } from "@/components/charts/sparkline";
import { displayStatus, type DisplayStatus } from "@/lib/metrics";
import type { Claim, TrackedPurchase } from "@/types";
import { daysUntil, dropPercent, formatCents, formatDate, priceGap } from "@/lib/utils";

export function windowCopy(purchase: TrackedPurchase, status: DisplayStatus) {
  if (status === "completed") return "Refund complete";
  if (status === "expired") return "Window closed";
  if (status === "ineligible") return "Not eligible";
  const days = daysUntil(purchase.adjustment_window_ends);
  if (days == null) return "No adjustment window";
  if (days < 0) return "Window closed";
  if (days === 0) return "Last day to file";
  if (days === 1) return "1 day left";
  return `${days} days left`;
}

export function PurchaseCard({
  purchase,
  claim,
  layout = "grid",
}: {
  purchase: TrackedPurchase;
  claim?: Claim;
  layout?: "grid" | "list";
}) {
  const status = displayStatus(purchase, claim);
  const gap = priceGap(purchase.price_paid_cents, purchase.current_price_cents);
  const percent = dropPercent(purchase.price_paid_cents, purchase.current_price_cents);
  const history = purchase.price_history.map((point) => point.price_cents);
  const details = (
    <Link href={`/tracker/${purchase.id}`} className="text-sm font-semibold text-[#12372A] underline-offset-4 hover:underline">
      View details
    </Link>
  );

  if (layout === "list") {
    return (
      <article className="grid items-center gap-4 rounded-xl border border-[#E4E7DC] bg-white p-4 shadow-[0_1px_2px_rgba(18,55,42,0.04)] md:grid-cols-[72px_1.4fr_1fr_auto]">
        <ProductArt art={purchase.art} label={purchase.product_name} className="h-[72px] w-[72px] rounded-lg" />
        <div>
          <h3 className="font-semibold text-[#17211C]">{purchase.product_name}</h3>
          <p className="text-sm text-[#5E6B63]">{purchase.retailer} · {formatDate(purchase.purchased_at)}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span className="tabular-nums text-[#5E6B63] line-through">{formatCents(purchase.price_paid_cents)}</span>
          <span className="font-semibold tabular-nums">{formatCents(purchase.current_price_cents ?? purchase.price_paid_cents)}</span>
          <span className="font-semibold tabular-nums text-[#146C3A]">{gap > 0 ? formatCents(gap) : "—"}</span>
          <StatusBadge status={status} />
        </div>
        <div className="flex items-center justify-between gap-4 md:justify-end">
          <Sparkline points={history} />
          {details}
        </div>
      </article>
    );
  }

  return (
    <article className="flex h-full flex-col rounded-xl border border-[#E4E7DC] bg-white p-4 shadow-[0_1px_2px_rgba(18,55,42,0.04)]">
      <ProductArt art={purchase.art} label={purchase.product_name} className="h-36 rounded-lg" />
      <div className="mt-4 flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold leading-5 text-[#17211C]">{purchase.product_name}</h3>
          <p className="mt-1 text-sm text-[#5E6B63]">{purchase.retailer}</p>
        </div>
        <StatusBadge status={status} />
      </div>
      <p className="mt-3 text-xs text-[#5E6B63]">Purchased {formatDate(purchase.purchased_at)}</p>
      <div className="mt-3 flex items-end justify-between">
        <div>
          <p className="text-xs text-[#5E6B63] line-through tabular-nums">{formatCents(purchase.price_paid_cents)}</p>
          <p className="text-lg font-semibold tabular-nums">{formatCents(purchase.current_price_cents ?? purchase.price_paid_cents)}</p>
        </div>
        <div className="text-right">
          <p className="text-sm font-semibold tabular-nums text-[#146C3A]">{gap > 0 ? `${formatCents(gap)} saved` : "No drop"}</p>
          <p className="text-xs text-[#5E6B63]">{percent > 0 ? `${percent}% lower` : windowCopy(purchase, status)}</p>
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between">
        <Sparkline points={history} />
        <p className="text-xs font-medium text-[#5E6B63]">{windowCopy(purchase, status)}</p>
      </div>
      <div className="mt-4">{details}</div>
    </article>
  );
}
