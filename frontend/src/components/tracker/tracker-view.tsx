"use client";

import { useMemo, useState } from "react";
import { LayoutGrid, List, Search } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { PurchaseCard } from "@/components/purchase-card";
import { claimForPurchase, displayStatus, type DisplayStatus } from "@/lib/metrics";
import { daysUntil, priceGap } from "@/lib/utils";
import { useAppStore } from "@/store/app-store";

const STATUSES: Array<DisplayStatus | "all"> = ["all", "eligible", "monitoring", "pending", "processing", "submitted", "completed", "ineligible", "expired"];

export function TrackerView() {
  const purchases = useAppStore((state) => state.purchases);
  const claims = useAppStore((state) => state.claims);
  const [query, setQuery] = useState("");
  const [retailer, setRetailer] = useState("all");
  const [status, setStatus] = useState<(typeof STATUSES)[number]>("all");
  const [sort, setSort] = useState("savings");
  const [layout, setLayout] = useState<"grid" | "list">("grid");
  const retailers = useMemo(() => [...new Set(purchases.map((item) => item.retailer))].sort(), [purchases]);

  const visible = purchases
    .map((purchase) => ({ purchase, claim: claimForPurchase(claims, purchase.id) }))
    .filter((item) => {
      const haystack = `${item.purchase.product_name} ${item.purchase.retailer} ${item.purchase.order_number ?? ""}`.toLowerCase();
      if (query && !haystack.includes(query.trim().toLowerCase())) return false;
      if (retailer !== "all" && item.purchase.retailer !== retailer) return false;
      if (status !== "all" && displayStatus(item.purchase, item.claim) !== status) return false;
      return true;
    })
    .sort((a, b) => {
      if (sort === "newest") return b.purchase.purchased_at.localeCompare(a.purchase.purchased_at);
      if (sort === "expiring") {
        const left = daysUntil(a.purchase.adjustment_window_ends);
        const right = daysUntil(b.purchase.adjustment_window_ends);
        return (left == null || left < 0 ? 10_000 : left) - (right == null || right < 0 ? 10_000 : right);
      }
      return priceGap(b.purchase.price_paid_cents, b.purchase.current_price_cents) - priceGap(a.purchase.price_paid_cents, a.purchase.current_price_cents);
    });

  return (
    <div>
      <PageHeader
        eyebrow="Price tracker"
        title="Every purchase being watched"
        description="Search, filter, and open a purchase to see its price history, the simulated policy, and whether a claim can be filed."
      />
      <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center">
        <label className="relative min-w-0 flex-1">
          <span className="sr-only">Search purchases</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#5E6B63]" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search product, retailer, or order"
            className="h-10 w-full rounded-lg border border-[#D5DACB] bg-white pl-9 pr-3 text-sm outline-none focus:border-[#12372A]"
          />
        </label>
        <select aria-label="Retailer" value={retailer} onChange={(event) => setRetailer(event.target.value)} className="h-10 rounded-lg border border-[#D5DACB] bg-white px-3 text-sm">
          <option value="all">All retailers</option>
          {retailers.map((name) => <option key={name}>{name}</option>)}
        </select>
        <select aria-label="Status" value={status} onChange={(event) => setStatus(event.target.value as (typeof STATUSES)[number])} className="h-10 rounded-lg border border-[#D5DACB] bg-white px-3 text-sm">
          {STATUSES.map((item) => <option key={item} value={item}>{item === "all" ? "All statuses" : item[0].toUpperCase() + item.slice(1)}</option>)}
        </select>
        <select aria-label="Sort" value={sort} onChange={(event) => setSort(event.target.value)} className="h-10 rounded-lg border border-[#D5DACB] bg-white px-3 text-sm">
          <option value="savings">Biggest savings</option>
          <option value="newest">Newest purchase</option>
          <option value="expiring">Expiring soon</option>
        </select>
        <div className="flex rounded-lg border border-[#D5DACB] bg-white p-1">
          <button type="button" aria-label="Grid view" aria-pressed={layout === "grid"} className={`rounded-md p-2 ${layout === "grid" ? "bg-[#12372A] text-white" : ""}`} onClick={() => setLayout("grid")}><LayoutGrid className="h-4 w-4" /></button>
          <button type="button" aria-label="List view" aria-pressed={layout === "list"} className={`rounded-md p-2 ${layout === "list" ? "bg-[#12372A] text-white" : ""}`} onClick={() => setLayout("list")}><List className="h-4 w-4" /></button>
        </div>
      </div>
      {visible.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[#D5DACB] bg-white px-6 py-16 text-center">
          <p className="font-semibold text-[#12372A]">No purchases match</p>
          <p className="mt-2 text-sm text-[#5E6B63]">Try a different search or clear the filters.</p>
          <button type="button" className="mt-4 text-sm font-semibold underline-offset-4 hover:underline" onClick={() => { setQuery(""); setRetailer("all"); setStatus("all"); }}>
            Clear filters
          </button>
        </div>
      ) : (
        <div className={layout === "grid" ? "grid gap-4 sm:grid-cols-2 xl:grid-cols-3" : "space-y-3"}>
          {visible.map((item) => <PurchaseCard key={item.purchase.id} purchase={item.purchase} claim={item.claim} layout={layout} />)}
        </div>
      )}
    </div>
  );
}
