"use client";

import { Check, Loader2 } from "lucide-react";
import { formatCents } from "@/lib/utils";
import { cn } from "@/lib/utils";

function reveal(value: string, progress: number, start: number, end: number) {
  const amount = Math.min(1, Math.max(0, (progress - start) / (end - start)));
  return value.slice(0, Math.ceil(value.length * amount));
}

export function StageVisual({ stage, progress, phase }: { stage: number; progress: number; phase: string }) {
  if (stage <= 0) return <Intro />;
  if (phase === "complete" || (stage === 6 && progress > 0.9)) return <Celebration />;
  if (stage === 1) return <ReceiptStage progress={progress} paused={phase === "paused"} />;
  if (stage === 2) return <DropStage progress={progress} />;
  if (stage === 3) return <EligibilityStage progress={progress} />;
  if (stage === 4) return <ClaimStage progress={progress} />;
  if (stage === 5) return <BankStage progress={progress} />;
  return <VaultStage progress={progress} />;
}

function Intro() {
  return (
    <div className="flex h-full flex-col justify-center">
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-[#5E6B63]">Six stages · about 27 seconds</p>
      <h2 className="mt-3 max-w-xl text-3xl font-semibold tracking-tight text-[#12372A] sm:text-4xl">
        Watch DropShop recover $40 from a new Nike receipt.
      </h2>
      <p className="mt-4 max-w-lg text-sm leading-6 text-[#5E6B63]">
        The sequence discovers a purchase, sees the price fall from $160 to $120, checks the policy, files a claim, confirms the refund, and deposits it. Every step is simulated.
      </p>
    </div>
  );
}

function ReceiptStage({ progress, paused }: { progress: number; paused: boolean }) {
  return (
    <div>
      <Window title="Inbox · Simulated email scan">
        <div className="relative overflow-hidden rounded-lg border border-[#E4E7DC] bg-[#FBFCF8] p-4">
          <div className={cn("scan-bar pointer-events-none absolute inset-x-4 h-8 bg-gradient-to-b from-transparent via-[#C8F55A]/80 to-transparent", paused && "[animation-play-state:paused]")} />
          <p className="text-xs text-[#5E6B63]">From receipts@nike.example</p>
          <p className="mt-1 font-medium">Order confirmation NK-10482931</p>
          <div className="mt-4 flex items-center justify-between border-t border-[#E4E7DC] pt-4">
            <div>
              <p className="font-semibold text-[#12372A]">Nike Air Max 270</p>
              <p className="text-sm text-[#5E6B63]">Size 9 · Order today</p>
            </div>
            <p className="text-lg font-semibold tabular-nums">$160.00</p>
          </div>
        </div>
      </Window>
      {progress > 0.55 ? <Callout title="Purchase discovered!" body="Nike Air Max 270 · Purchase price $160.00. Added to Price Tracker." /> : <p className="mt-4 text-sm text-[#5E6B63]">Scanning connected email for order confirmations…</p>}
    </div>
  );
}

function DropStage({ progress }: { progress: number }) {
  const t = Math.min(1, Math.max(0, (progress - 0.12) / 0.7));
  const eased = 1 - (1 - t) ** 3;
  const price = 160 - 40 * eased;
  const steps = 28;
  const coords = Array.from({ length: steps }, (_, index) => {
    const x = index / (steps - 1);
    const local = Math.min(1, x / 0.82);
    const yPrice = 160 - 40 * local * eased;
    return `${(16 + x * 300).toFixed(1)},${(24 + ((160 - yPrice) / 48) * 120).toFixed(1)}`;
  }).join(" ");
  return (
    <div>
      <div className="rounded-xl border border-[#E4E7DC] bg-white p-4">
        <div className="flex items-end justify-between">
          <div>
            <p className="text-xs text-[#5E6B63]">Nike · tracked price</p>
            <p className="text-3xl font-semibold tabular-nums text-[#12372A]">${price.toFixed(2)}</p>
          </div>
          <p className="text-sm text-[#5E6B63] line-through">$160.00 paid</p>
        </div>
        <svg viewBox="0 0 332 160" className="mt-2 h-44 w-full" aria-hidden>
          <polyline points={coords} fill="none" stroke="#12372A" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
        </svg>
      </div>
      {progress > 0.6 ? <Callout title="Price drop detected!" body="Potential refund $40.00 · 25% below what you paid." /> : null}
    </div>
  );
}

function EligibilityStage({ progress }: { progress: number }) {
  const checks = [
    { label: "Purchase within the adjustment window", at: 0.22 },
    { label: "Same product as the original order", at: 0.42 },
    { label: "Eligible price difference of $40.00", at: 0.62 },
  ];
  return (
    <div className="rounded-xl border border-[#E4E7DC] bg-white p-5">
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-[#5E6B63]">Gemini · simulated policy review</p>
      <h3 className="mt-2 text-xl font-semibold text-[#12372A]">Nike price adjustment, 14 days</h3>
      <ul className="mt-5 space-y-3">
        {checks.map((check) => {
          const on = progress >= check.at;
          return (
            <li key={check.label} className="flex items-center gap-3 text-sm">
              <span className={cn("flex h-6 w-6 items-center justify-center rounded-full", on ? "bg-[#12372A] text-[#C8F55A]" : "bg-[#EEF1EA] text-[#5E6B63]")}>
                {on ? <Check className="h-3.5 w-3.5" /> : <Loader2 className="h-3.5 w-3.5" />}
              </span>
              {check.label}
            </li>
          );
        })}
      </ul>
      {progress > 0.62 ? <Callout title="You qualify for a $40 refund!" body="The purchase is inside the window, the product matches, and the price is lower. Demo policy, not a live Gemini call." /> : null}
    </div>
  );
}

function ClaimStage({ progress }: { progress: number }) {
  const fields = [
    ["Order number", reveal("NK-10482931", progress, 0.08, 0.22)],
    ["Product", reveal("Nike Air Max 270", progress, 0.22, 0.4)],
    ["Purchase price", reveal("$160.00", progress, 0.4, 0.52)],
    ["Current price", reveal("$120.00", progress, 0.52, 0.64)],
    ["Requested refund", reveal("$40.00", progress, 0.64, 0.74)],
  ];
  const pressed = progress > 0.75;
  return (
    <div>
      <Window title="retailer.demo/price-adjustment · Simulated portal">
        <div className="space-y-3">
          {fields.map(([label, value]) => (
            <label key={label} className="block text-xs font-medium text-[#5E6B63]">
              {label}
              <div className="mt-1 flex h-10 items-center rounded-lg border border-[#E4E7DC] bg-[#FBFCF8] px-3 font-mono text-sm text-[#17211C]">
                {value}
                {value && progress < 0.78 ? <span className="ml-0.5 inline-block h-4 w-px bg-[#12372A]" /> : null}
              </div>
            </label>
          ))}
          <div className={cn("flex h-10 items-center justify-center rounded-lg text-sm font-semibold", pressed ? "bg-[#C8F55A] text-[#12372A]" : "bg-[#12372A] text-white")}>
            {pressed ? "Claim submitted" : "Submit claim"}
          </div>
        </div>
      </Window>
      {progress > 0.78 ? <Callout title="Refund claim submitted successfully!" body="The claims list and activity feed now include this $40 Nike claim." /> : null}
    </div>
  );
}

function BankStage({ progress }: { progress: number }) {
  const rows = [
    ["Allbirds Tree Runner", "$20.00"],
    ["Adidas Samba", "$10.00"],
  ];
  return (
    <div className="rounded-xl border border-[#E4E7DC] bg-white p-5">
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-[#5E6B63]">Capital One ·•4821 · Simulated</p>
      <h3 className="mt-2 text-xl font-semibold text-[#12372A]">Checking deposits</h3>
      <ul className="mt-4 divide-y divide-[#E4E7DC]">
        {progress > 0.45 ? (
          <li className="flex items-center justify-between py-3">
            <div>
              <p className="font-medium">Nike Air Max 270</p>
              <p className="text-xs text-[#146C3A]">Verified refund</p>
            </div>
            <p className="font-semibold tabular-nums text-[#146C3A]">+$40.00</p>
          </li>
        ) : null}
        {rows.map(([name, amount]) => (
          <li key={name} className="flex items-center justify-between py-3 text-sm">
            <span>{name}</span>
            <span className="tabular-nums text-[#5E6B63]">{amount}</span>
          </li>
        ))}
      </ul>
      {progress > 0.6 ? <Callout title="Refund received!" body="Nessie matched a $40.00 deposit. Recovered money updates now. The vault is next." /> : null}
    </div>
  );
}

function VaultStage({ progress }: { progress: number }) {
  const amount = Math.min(4000, Math.round(4000 * Math.min(1, progress / 0.72)));
  return (
    <div>
      <div className="rounded-xl bg-[#12372A] p-6 text-white">
        <p className="text-sm text-white/70">Savings vault · simulated Solana deposit</p>
        <p className="mt-3 text-4xl font-semibold tabular-nums">{formatCents(6000 + amount)}</p>
        <p className="mt-2 text-sm text-white/70">Was $60.00 before this deposit.</p>
      </div>
      {progress > 0.4 ? (
        <div className="mt-4 rounded-xl border border-[#E4E7DC] bg-white p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">Deposit · Nike Air Max 270</p>
              <p className="mt-1 font-mono text-xs text-[#5E6B63]">simN…0004</p>
            </div>
            <p className="font-semibold tabular-nums text-[#146C3A]">+{formatCents(amount || 4000)}</p>
          </div>
        </div>
      ) : null}
      {progress > 0.72 ? <Callout title="$40 added to your savings vault!" body="The savings chart includes this deposit. The signature is simulated and was not sent to Solana." /> : null}
    </div>
  );
}

function Celebration() {
  return (
    <div className="relative flex h-full flex-col items-start justify-center overflow-hidden">
      {Array.from({ length: 14 }).map((_, index) => (
        <span
          key={index}
          className="absolute h-2 w-2 rounded-full"
          style={{
            left: `${18 + (index * 37) % 70}%`,
            top: `${12 + (index * 23) % 55}%`,
            background: index % 2 ? "#C8F55A" : "#12372A",
            opacity: 0.85,
          }}
        />
      ))}
      <span className="relative flex h-14 w-14 items-center justify-center rounded-full bg-[#C8F55A] text-[#12372A]">
        <Check className="h-7 w-7" />
      </span>
      <h2 className="relative mt-6 max-w-xl text-3xl font-semibold tracking-tight text-[#12372A] sm:text-4xl">
        Success! DropShop just recovered $40 for you.
      </h2>
      <p className="relative mt-3 max-w-lg text-sm leading-6 text-[#5E6B63]">
        The dashboard, price tracker, claims, activity feed, and savings vault all include this purchase. Replaying the demo removes it first, so the $40 is never counted twice.
      </p>
    </div>
  );
}

function Window({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="overflow-hidden rounded-xl border border-[#E4E7DC] bg-white">
      <div className="flex items-center gap-2 border-b border-[#E4E7DC] px-3 py-2">
        <span className="h-2.5 w-2.5 rounded-full bg-[#E4E7DC]" />
        <span className="h-2.5 w-2.5 rounded-full bg-[#E4E7DC]" />
        <span className="h-2.5 w-2.5 rounded-full bg-[#E4E7DC]" />
        <p className="ml-2 truncate text-xs text-[#5E6B63]">{title}</p>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

function Callout({ title, body }: { title: string; body: string }) {
  return (
    <div className="mt-4 rounded-xl border border-[#D7E7A8] bg-[#F4FBE3] px-4 py-3">
      <p className="font-semibold text-[#12372A]">{title}</p>
      <p className="mt-1 text-sm leading-6 text-[#3E4C45]">{body}</p>
    </div>
  );
}
