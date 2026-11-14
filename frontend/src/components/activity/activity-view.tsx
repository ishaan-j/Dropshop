"use client";

import { Bot, Check, Landmark, LineChart, Mail, Sparkles, Wallet } from "lucide-react";
import { PageHeader, Panel } from "@/components/page-header";
import { useDemo } from "@/components/demo/demo-provider";
import { PIPELINE } from "@/lib/constants";
import { claimForPurchase, isVaulted } from "@/lib/metrics";
import { priceGap, formatRelative, cn } from "@/lib/utils";
import { useAppStore } from "@/store/app-store";
import type { AgentEventKind, TrackedPurchase } from "@/types";

const AGENTS: Array<{
  id: string;
  name: string;
  role: string;
  description: string;
  kinds: AgentEventKind[];
  stage: number;
  icon: typeof Mail;
}> = [
  { id: "sentient", name: "Sentient OS", role: "Receipt Hunter", description: "Finds order confirmations and purchase receipts in your email.", kinds: ["purchase_found"], stage: 1, icon: Mail },
  { id: "tiger", name: "Tiger Data", role: "Price Tracker", description: "Stores price history and catches a drop against what you paid.", kinds: ["price_checked", "price_drop"], stage: 2, icon: LineChart },
  { id: "gemini", name: "Gemini", role: "Eligibility Analyzer", description: "Reads the retailer policy and decides if a refund qualifies.", kinds: ["eligibility_checked"], stage: 3, icon: Sparkles },
  { id: "grok", name: "Grok Bot", role: "Claim Agent", description: "Fills out the price-adjustment form and submits the claim.", kinds: ["claim_drafted", "claim_submitting", "claim_submitted"], stage: 4, icon: Bot },
  { id: "nessie", name: "Nessie", role: "Refund Verifier", description: "Checks the bank feed and confirms the refund arrived.", kinds: ["refund_received"], stage: 5, icon: Landmark },
  { id: "solana", name: "Solana", role: "Savings Vault", description: "Records the recovered money as a deposit in your vault.", kinds: ["vault_recorded"], stage: 6, icon: Wallet },
];

const KIND_LABEL: Record<AgentEventKind, string> = {
  purchase_found: "Receipt",
  price_checked: "Price check",
  price_drop: "Price drop",
  eligibility_checked: "Eligibility",
  claim_drafted: "Claim draft",
  claim_submitting: "Submitting",
  claim_submitted: "Submitted",
  refund_received: "Refund",
  vault_recorded: "Vault",
  error: "Note",
};

export function ActivityView() {
  const demo = useDemo();
  const purchases = useAppStore((state) => state.purchases);
  const claims = useAppStore((state) => state.claims);
  const vault = useAppStore((state) => state.vaultTransactions);
  const activity = useAppStore((state) => state.activity);
  const demoRunning = demo.phase === "running" || demo.phase === "paused";
  const featured = featuredPurchase(purchases, claims, activity);
  const purchase = purchases.find((item) => item.id === featured);
  const claim = purchase ? claimForPurchase(claims, purchase.id) : undefined;
  const vaulted = claim ? isVaulted(claim, vault) : false;
  const idleCompleted = pipelineCompleted(purchase, claim, vaulted);
  const completed = demoRunning || demo.phase === "complete" ? demo.committed : idleCompleted;
  const active = demoRunning ? demo.stage : demo.phase === "complete" ? 0 : idleCompleted < 6 ? idleCompleted + 1 : 0;
  const events = [...activity].sort((a, b) => b.time.localeCompare(a.time));

  return (
    <div>
      <PageHeader
        eyebrow="AI activity"
        title="Six agents, one refund"
        description="Each agent has one job. During the live demo the active agent is highlighted and the log updates as the $40 moves through the pipeline."
      />
      <Panel>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold text-[#12372A]">Workflow</h2>
          <p className="text-sm text-[#5E6B63]">
            {demoRunning || demo.phase === "complete" ? "Live demo · Nike Air Max 270" : purchase ? `Latest · ${purchase.product_name}` : "No purchase yet"}
          </p>
        </div>
        <div className="relative mt-6">
          <div className="absolute left-0 right-0 top-5 hidden h-px bg-[#E4E7DC] md:block" />
          <ol className="grid gap-4 md:grid-cols-6">
            {PIPELINE.map((step, index) => {
              const stepNumber = index + 1;
              const done = completed >= stepNumber;
              const current = active === stepNumber;
              return (
                <li key={step.id}>
                  <div className={cn("relative z-10 flex h-10 w-10 items-center justify-center rounded-full border text-sm font-semibold", done ? "border-[#12372A] bg-[#12372A] text-[#C8F55A]" : current ? "border-[#C8F55A] bg-[#C8F55A] text-[#12372A]" : "border-[#E4E7DC] bg-white text-[#5E6B63]")}>
                    {done ? <Check className="h-4 w-4" /> : stepNumber}
                  </div>
                  <p className="mt-3 text-sm font-medium">{step.title}</p>
                  <p className="text-xs text-[#5E6B63]">{step.agent}</p>
                </li>
              );
            })}
          </ol>
        </div>
      </Panel>

      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {AGENTS.map((agent) => {
          const related = events.filter((event) => agent.kinds.includes(event.kind));
          const latest = related[0];
          const processing = demoRunning && demo.stage === agent.stage;
          const Icon = agent.icon;
          return (
            <article key={agent.id} className={cn("rounded-xl border bg-white p-5", processing ? "border-[#C8F55A] shadow-[0_0_0_3px_rgba(200,245,90,0.45)]" : "border-[#E4E7DC]")}>
              <div className="flex items-start justify-between">
                <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#F4F6EE] text-[#12372A]">
                  <Icon className="h-5 w-5" />
                </span>
                <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", processing ? "bg-[#C8F55A] text-[#12372A]" : "bg-[#EEF1EA] text-[#4E5B54]")}>
                  {processing ? "Processing" : related.length ? "Ready" : "Idle"}
                </span>
              </div>
              <h3 className="mt-4 font-semibold text-[#12372A]">{agent.name}</h3>
              <p className="text-sm text-[#5E6B63]">{agent.role}</p>
              <p className="mt-2 text-sm leading-6">{agent.description}</p>
              <p className="mt-4 text-sm"><span className="font-semibold tabular-nums">{related.length}</span> tasks completed</p>
              <p className="mt-1 text-sm text-[#5E6B63]">{latest ? latest.message : "No activity yet."}</p>
              {processing ? <p className="mt-3 text-xs font-medium text-[#12372A]">Working through this stage…</p> : null}
            </article>
          );
        })}
      </div>

      <Panel className="mt-4">
        <h2 className="font-semibold text-[#12372A]">Live event log</h2>
        <ul className="mt-2 max-h-[32rem] divide-y divide-[#E4E7DC] overflow-y-auto">
          {events.map((event) => (
            <li key={event.id} className="flex gap-3 py-3">
              <span className={cn("mt-1 h-2 w-2 shrink-0 rounded-full", event.id.startsWith("demo-") ? "bg-[#C8F55A]" : "bg-[#12372A]")} />
              <div>
                <p className="text-sm leading-5">{event.message}</p>
                <p className="mt-1 text-xs text-[#5E6B63]">{formatRelative(event.time)} · {KIND_LABEL[event.kind]}</p>
              </div>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}

function featuredPurchase(
  purchases: TrackedPurchase[],
  claims: ReturnType<typeof useAppStore.getState>["claims"],
  activity: ReturnType<typeof useAppStore.getState>["activity"],
) {
  const nike = purchases.find((item) => item.id === "demo-nike-air-max");
  if (nike) return nike.id;
  const open = claims
    .filter((claim) => claim.status === "awaiting_approval" || claim.status === "submitting" || claim.status === "submitted")
    .sort((a, b) => b.created_at.localeCompare(a.created_at));
  if (open[0]) return open[0].purchase_id;
  const latest = [...activity].sort((a, b) => b.time.localeCompare(a.time)).find((event) => event.purchase_id);
  return latest?.purchase_id ?? purchases[0]?.id ?? "";
}

function pipelineCompleted(purchase: TrackedPurchase | undefined, claim: ReturnType<typeof claimForPurchase> | undefined, vaulted: boolean) {
  if (!purchase) return 0;
  if (vaulted) return 6;
  if (claim?.status === "refund_received") return 5;
  if (claim?.status === "submitted") return 4;
  if (claim?.status === "submitting" || claim?.status === "awaiting_approval" || purchase.qualifies) return 3;
  if (priceGap(purchase.price_paid_cents, purchase.current_price_cents) > 0) return 2;
  return 1;
}
