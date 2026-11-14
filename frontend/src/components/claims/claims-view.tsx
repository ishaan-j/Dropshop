"use client";

import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { Check } from "lucide-react";
import { PageHeader, Panel } from "@/components/page-header";
import { StatusNote } from "@/components/status-note";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { CLAIM_TIMELINE } from "@/lib/constants";
import { useBackend } from "@/lib/live";
import { claimForPurchase, claimStageLabel, claimTimelineProgress, displayStatus, isVaulted } from "@/lib/metrics";
import { approveClaim, fileClaim, rejectClaim } from "@/lib/services";
import { formatCents, formatDate } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/store/app-store";
import type { Claim } from "@/types";

const TABS = [
  { id: "all", label: "All claims" },
  { id: "eligible", label: "Eligible" },
  { id: "processing", label: "Processing" },
  { id: "submitted", label: "Submitted" },
  { id: "completed", label: "Completed" },
  { id: "ineligible", label: "Ineligible" },
] as const;

type TabId = (typeof TABS)[number]["id"];

function matches(tab: TabId, claim: Claim) {
  if (tab === "all") return true;
  if (tab === "eligible") return claim.status === "awaiting_approval";
  if (tab === "processing") return claim.status === "submitting";
  if (tab === "submitted") return claim.status === "submitted";
  if (tab === "completed") return claim.status === "refund_received";
  return claim.status === "rejected" || claim.status === "failed";
}

export function ClaimsView() {
  const purchases = useAppStore((state) => state.purchases);
  const claims = useAppStore((state) => state.claims);
  const vault = useAppStore((state) => state.vaultTransactions);
  const activity = useAppStore((state) => state.activity);
  const backend = useBackend();
  const [tab, setTab] = useState<TabId>("all");
  const [selected, setSelected] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const ready = purchases.filter((purchase) => displayStatus(purchase, claimForPurchase(claims, purchase.id)) === "eligible");
  const visible = [...claims].filter((claim) => matches(tab, claim)).sort((a, b) => b.created_at.localeCompare(a.created_at));
  const claim = claims.find((item) => item.id === selected) ?? null;
  const purchase = claim ? purchases.find((item) => item.id === claim.purchase_id) : undefined;
  // The claim bot's latest screenshot for this claim (live backend only).
  const screenshot = claim
    ? activity
        .filter((event) => event.claim_id === claim.id && event.screenshot_url)
        .sort((a, b) => b.time.localeCompare(a.time))[0]?.screenshot_url
    : null;

  async function run(id: string, action: "approve" | "reject" | "file") {
    setBusy(id);
    try {
      if (action === "approve") {
        await approveClaim(id);
        toast.success("Claim submitted");
      } else if (action === "reject") {
        await rejectClaim(id);
        toast.success("Claim declined");
      } else {
        await fileClaim(id);
        toast.success("Refund claim submitted");
        setConfirmId(null);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Something went wrong");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Claims"
        title="Refunds in motion"
        description={
          backend
            ? "Eligible claims wait for your approval. Once you approve, the claim bot files it on DropShop's demo store and the refund is tracked into your vault."
            : "Eligible claims wait for your approval. Submitted claims are simulated — nothing is sent to a retailer."
        }
      />
      {ready.length > 0 ? (
        <Panel className="mb-6">
          <h2 className="font-semibold text-[#12372A]">Ready to file</h2>
          <ul className="mt-3 divide-y divide-[#E4E7DC]">
            {ready.map((item) => (
              <li key={item.id} className="flex flex-col gap-3 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="font-medium">{item.product_name}</p>
                  <p className="text-sm text-[#5E6B63]">{item.retailer} · {formatCents(item.price_paid_cents - (item.current_price_cents ?? item.price_paid_cents))}</p>
                </div>
                <Button size="sm" onClick={() => setConfirmId(item.id)}>File refund claim</Button>
              </li>
            ))}
          </ul>
        </Panel>
      ) : null}

      <div role="tablist" aria-label="Claim status" className="mb-4 flex gap-2 overflow-x-auto" onKeyDown={(event) => {
        const index = TABS.findIndex((item) => item.id === tab);
        if (event.key === "ArrowRight") setTab(TABS[(index + 1) % TABS.length].id);
        if (event.key === "ArrowLeft") setTab(TABS[(index - 1 + TABS.length) % TABS.length].id);
      }}>
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            onClick={() => setTab(item.id)}
            className={cn("shrink-0 rounded-full px-3 py-1.5 text-sm font-medium", tab === item.id ? "bg-[#12372A] text-white" : "bg-white text-[#5E6B63]")}
          >
            {item.label}
          </button>
        ))}
      </div>

      {visible.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[#D5DACB] bg-white px-6 py-16 text-center">
          <p className="font-semibold text-[#12372A]">No claims in this tab</p>
          <p className="mt-2 text-sm text-[#5E6B63]">File an eligible purchase, or run the live demo to create one.</p>
        </div>
      ) : (
        <>
          <div className="hidden overflow-hidden rounded-xl border border-[#E4E7DC] bg-white md:block">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-[#E4E7DC] text-xs uppercase tracking-wide text-[#5E6B63]">
                <tr>
                  <th className="px-4 py-3 font-medium">Product</th>
                  <th className="px-4 py-3 font-medium">Retailer</th>
                  <th className="px-4 py-3 font-medium">Refund</th>
                  <th className="px-4 py-3 font-medium">Submitted</th>
                  <th className="px-4 py-3 font-medium">Stage</th>
                  <th className="px-4 py-3 font-medium" />
                </tr>
              </thead>
              <tbody>
                {visible.map((item) => {
                  const product = purchases.find((purchase) => purchase.id === item.purchase_id);
                  return (
                    <tr key={item.id} className="border-b border-[#E4E7DC] last:border-0">
                      <td className="px-4 py-3 font-medium">{product?.product_name ?? "Purchase"}</td>
                      <td className="px-4 py-3">{item.retailer}</td>
                      <td className="px-4 py-3 tabular-nums">{formatCents(item.refund_cents)}</td>
                      <td className="px-4 py-3">{item.submitted_at ? formatDate(item.submitted_at) : "—"}</td>
                      <td className="px-4 py-3">{claimStageLabel(item, isVaulted(item, vault))}</td>
                      <td className="px-4 py-3 text-right">
                        <button type="button" className="font-semibold text-[#12372A]" onClick={() => setSelected(item.id)}>View details</button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="space-y-3 md:hidden">
            {visible.map((item) => {
              const product = purchases.find((purchase) => purchase.id === item.purchase_id);
              return (
                <Panel key={item.id}>
                  <p className="font-semibold">{product?.product_name}</p>
                  <p className="mt-1 text-sm text-[#5E6B63]">{item.retailer} · {formatCents(item.refund_cents)}</p>
                  <p className="mt-2 text-sm">{claimStageLabel(item, isVaulted(item, vault))}</p>
                  <button type="button" className="mt-3 text-sm font-semibold" onClick={() => setSelected(item.id)}>View details</button>
                </Panel>
              );
            })}
          </div>
        </>
      )}

      <Dialog open={Boolean(claim)} onOpenChange={(next) => { if (!next) setSelected(null); }}>
        {claim ? (
          <DialogContent>
            <DialogTitle>{purchase?.product_name ?? "Claim"}</DialogTitle>
            <DialogDescription>
              {claim.retailer} · {formatCents(claim.refund_cents)} · {claimStageLabel(claim, isVaulted(claim, vault))}
            </DialogDescription>
            <div className="mt-4"><StatusNote /></div>
            <ol className="mt-5 space-y-3">
              {CLAIM_TIMELINE.map((label, index) => {
                const progress = claimTimelineProgress(claim, isVaulted(claim, vault));
                const step = index + 1;
                const done = step <= progress.done;
                const failed = progress.failedAt === step;
                return (
                  <li key={label} className="flex items-center gap-3 text-sm">
                    <span className={cn("flex h-6 w-6 items-center justify-center rounded-full text-xs", done ? "bg-[#12372A] text-[#C8F55A]" : failed ? "bg-[#FDECEC] text-[#9B2C2C]" : "bg-[#EEF1EA] text-[#5E6B63]")}>
                      {done ? <Check className="h-3.5 w-3.5" /> : step}
                    </span>
                    <span>{label}</span>
                  </li>
                );
              })}
            </ol>
            {screenshot ? (
              <a href={screenshot} target="_blank" rel="noreferrer" className="mt-4 block">
                {/* eslint-disable-next-line @next/next/no-img-element -- served by the backend, not a static asset */}
                <img src={screenshot} alt="The claim form as the bot submitted it" className="max-h-44 w-full rounded-lg border border-[#E4E7DC] object-cover object-top" />
                <span className="mt-1 block text-xs text-[#5E6B63]">What the claim bot submitted. Open full size.</span>
              </a>
            ) : null}
            <p className="mt-4 text-sm leading-6 text-[#3E4C45]">{claim.explanation}</p>
            {claim.status === "awaiting_approval" ? (
              <div className="mt-6 flex gap-2">
                <Button onClick={() => run(claim.id, "approve")} disabled={busy === claim.id}>{busy === claim.id ? "Submitting…" : "Approve and file"}</Button>
                <Button variant="outline" onClick={() => run(claim.id, "reject")} disabled={busy === claim.id}>Decline</Button>
              </div>
            ) : null}
            <Link href={`/tracker/${claim.purchase_id}`} className="mt-4 inline-block text-sm font-medium underline-offset-4 hover:underline">Open purchase</Link>
          </DialogContent>
        ) : null}
      </Dialog>

      <Dialog open={Boolean(confirmId)} onOpenChange={(next) => { if (!next) setConfirmId(null); }}>
        <DialogContent>
          <DialogTitle>File this refund claim?</DialogTitle>
          <DialogDescription>
            {backend
              ? "This approves the drafted claim. The claim bot files it on DropShop's demo store, not a real retailer."
              : "This submits a simulated claim and updates the shared demo data. No retailer is contacted."}
          </DialogDescription>
          <div className="mt-6 flex justify-end gap-2">
            <Button variant="outline" onClick={() => setConfirmId(null)}>Cancel</Button>
            <Button disabled={!confirmId || busy === confirmId} onClick={() => confirmId && run(confirmId, "file")}>
              {busy === confirmId ? "Submitting…" : "Submit claim"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
