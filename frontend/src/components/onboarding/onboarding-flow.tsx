"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Check, Landmark, Mail, Wallet } from "lucide-react";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { useAppStore } from "@/store/app-store";
import { delay } from "@/lib/utils";
import { cn } from "@/lib/utils";

const STEPS = [
  {
    title: "Connect your email",
    body: "DropShop looks for order confirmations. This connection is simulated — no inbox is opened.",
    providers: ["Gmail", "Outlook"],
  },
  {
    title: "Connect your bank account",
    body: "Nessie watches for the refund to land in Capital One. No real account is linked.",
    providers: ["Capital One"],
  },
  {
    title: "Set up your savings vault",
    body: "Recovered refunds are recorded in a simulated Solana vault. Nothing is sent on-chain.",
    providers: ["Solana vault"],
  },
];

export function OnboardingFlow() {
  const router = useRouter();
  const emailConnected = useAppStore((state) => state.emailConnected);
  const bankConnected = useAppStore((state) => state.bankConnected);
  const walletConnected = useAppStore((state) => state.walletConnected);
  const setEmail = useAppStore((state) => state.setEmailConnected);
  const setBank = useAppStore((state) => state.setBankConnected);
  const setWallet = useAppStore((state) => state.setWalletConnected);
  const complete = useAppStore((state) => state.completeOnboarding);
  const [step, setStep] = useState(0);
  const [provider, setProvider] = useState("Gmail");
  const [pending, setPending] = useState(false);
  const connected = [emailConnected, bankConnected, walletConnected];

  async function connect() {
    setPending(true);
    await delay(800);
    if (step === 0) setEmail(true);
    if (step === 1) setBank(true);
    if (step === 2) setWallet(true);
    setPending(false);
  }

  function finish() {
    complete();
    router.push("/dashboard");
  }

  const current = STEPS[step];
  const icons = [Mail, Landmark, Wallet];
  const Icon = icons[step];

  return (
    <div className="min-h-screen bg-[#F7F8F2]">
      <header className="mx-auto flex h-16 max-w-3xl items-center justify-between px-5">
        <Link href="/" aria-label="DropShop home"><Logo /></Link>
        <button type="button" className="text-sm font-medium text-[#5E6B63] hover:text-[#17211C]" onClick={finish}>
          Skip to Demo
        </button>
      </header>
      <main className="mx-auto max-w-xl px-5 py-10">
        <div className="mb-8 flex gap-2" aria-label="Onboarding progress">
          {STEPS.map((item, index) => (
            <div key={item.title} className={cn("h-1.5 flex-1 rounded-full", index <= step ? "bg-[#12372A]" : "bg-[#E4E7DC]")} />
          ))}
        </div>
        <p className="text-xs font-medium uppercase tracking-[0.14em] text-[#5E6B63]">Step {step + 1} of 3</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[#12372A]">{current.title}</h1>
        <p className="mt-3 text-sm leading-6 text-[#5E6B63]">{current.body}</p>
        <div className="mt-8 rounded-xl border border-[#E4E7DC] bg-white p-5">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#F4F6EE] text-[#12372A]">
              {connected[step] ? <Check className="h-5 w-5" /> : <Icon className="h-5 w-5" />}
            </span>
            <div>
              <p className="font-semibold">{connected[step] ? "Connected" : "Not connected"}</p>
              <p className="text-sm text-[#5E6B63]">{step === 0 ? provider : current.providers[0]} · simulated</p>
            </div>
          </div>
          {step === 0 ? (
            <div className="mt-5 flex gap-2">
              {current.providers.map((name) => (
                <button
                  key={name}
                  type="button"
                  aria-pressed={provider === name}
                  onClick={() => setProvider(name)}
                  className={cn("rounded-lg border px-3 py-2 text-sm font-medium", provider === name ? "border-[#12372A] bg-[#12372A] text-white" : "border-[#E4E7DC]")}
                >
                  {name}
                </button>
              ))}
            </div>
          ) : null}
          <div className="mt-6 flex flex-wrap gap-2">
            {connected[step] ? (
              <p className="text-sm text-[#146C3A]">Check — this connection is ready.</p>
            ) : (
              <Button onClick={connect} disabled={pending}>{pending ? "Connecting…" : "Connect"}</Button>
            )}
          </div>
        </div>
        <div className="mt-6 flex items-center justify-between">
          <Button variant="ghost" onClick={() => setStep((value) => Math.max(0, value - 1))} disabled={step === 0}>Back</Button>
          {step < 2 ? (
            <Button onClick={() => setStep((value) => value + 1)} disabled={!connected[step]}>Continue</Button>
          ) : (
            <Button onClick={finish} disabled={!connected[step]}>Go to dashboard</Button>
          )}
        </div>
        <p className="mt-8 text-center text-sm text-[#5E6B63]">
          Already set up? <Link href="/dashboard" className="font-medium text-[#12372A] underline-offset-4 hover:underline">Open dashboard</Link>
        </p>
      </main>
    </div>
  );
}
