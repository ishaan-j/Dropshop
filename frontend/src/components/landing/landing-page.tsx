"use client";

import Link from "next/link";
import { useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowDownRight, BadgeDollarSign, Bot, LineChart, Mail, Menu, ShieldCheck, Wallet, X } from "lucide-react";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";

const STEPS = [
  { n: "01", title: "Connect your email.", body: "DropShop looks for order confirmations and purchase receipts." },
  { n: "02", title: "We track your purchases.", body: "Prices are watched after you buy, without another search." },
  { n: "03", title: "AI finds and claims your refunds.", body: "A policy check decides if you qualify, then the claim is filed." },
  { n: "04", title: "Your savings grow automatically.", body: "Confirmed refunds land in a vault you can actually see." },
];

const FEATURES = [
  { icon: Mail, title: "Automatic receipt detection", body: "Sentient OS reads order emails and turns them into tracked purchases." },
  { icon: LineChart, title: "Real-time price monitoring", body: "Tiger Data keeps the price history and flags a drop against what you paid." },
  { icon: ShieldCheck, title: "AI-powered eligibility checks", body: "Gemini reads the retailer policy and explains the decision in plain language." },
  { icon: Bot, title: "Automated refund claims", body: "Grok Bot fills the price-adjustment form so you don't have to call anyone." },
  { icon: Wallet, title: "Automatic savings vault", body: "Once a refund is confirmed, the money is recorded in your savings vault." },
];

export function LandingPage() {
  const [open, setOpen] = useState(false);
  const reduce = useReducedMotion();
  const rise = reduce ? undefined : { initial: { opacity: 0, y: 12 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.45 } };
  return (
    <div className="min-h-screen bg-[#F7F8F2] text-[#17211C]">
      <header className="sticky top-0 z-30 border-b border-[#E4E7DC] bg-[#F7F8F2]">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
          <Link href="/" aria-label="DropShop home"><Logo /></Link>
          <nav className="hidden items-center gap-8 text-sm font-medium md:flex">
            <a href="#how-it-works" className="hover:text-[#12372A]">How It Works</a>
            <a href="#features" className="hover:text-[#12372A]">Features</a>
            <Button asChild><Link href="/onboarding">Get Started</Link></Button>
          </nav>
          <button type="button" className="rounded-md p-2 md:hidden" aria-label="Open menu" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
        {open ? (
          <div className="border-t border-[#E4E7DC] px-5 py-4 md:hidden">
            <div className="flex flex-col gap-3 text-sm font-medium">
              <a href="#how-it-works" onClick={() => setOpen(false)}>How It Works</a>
              <a href="#features" onClick={() => setOpen(false)}>Features</a>
              <Link href="/onboarding" onClick={() => setOpen(false)}>Get Started</Link>
            </div>
          </div>
        ) : null}
      </header>

      <main>
        <section className="mx-auto grid max-w-6xl items-center gap-12 px-5 py-16 lg:grid-cols-[1.05fr_0.95fr] lg:py-24">
          <motion.div {...rise}>
            <p className="text-xs font-medium uppercase tracking-[0.16em] text-[#5E6B63]">Price-drop refunds, handled</p>
            <h1 className="mt-4 max-w-xl text-5xl font-semibold tracking-tight text-[#12372A] sm:text-6xl sm:leading-[1.02]">
              You shop. Prices drop. You save.
            </h1>
            <p className="mt-5 max-w-md text-lg leading-7 text-[#3E4C45]">
              Get money back automatically when prices drop on things you’ve already bought.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button size="lg" asChild><Link href="/onboarding">Start Saving</Link></Button>
              <Button size="lg" variant="outline" asChild><a href="#how-it-works">See How It Works</a></Button>
            </div>
          </motion.div>
          <motion.div {...(reduce ? undefined : { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.5, delay: 0.08 } })}>
            <Preview />
          </motion.div>
        </section>

        <section id="how-it-works" className="border-t border-[#E4E7DC]">
          <div className="mx-auto max-w-6xl px-5 py-20">
            <h2 className="text-3xl font-semibold tracking-tight text-[#12372A]">How it works</h2>
            <p className="mt-3 max-w-xl text-sm leading-6 text-[#5E6B63]">Four steps. You connect once. DropShop does the watching, the paperwork, and the deposit.</p>
            <ol className="mt-10 grid gap-8 md:grid-cols-4">
              {STEPS.map((step) => (
                <li key={step.n}>
                  <p className="text-sm font-semibold text-[#12372A]">{step.n}</p>
                  <div className="mt-3 h-px w-10 bg-[#12372A]" />
                  <h3 className="mt-4 text-lg font-semibold text-[#12372A]">{step.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-[#5E6B63]">{step.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-5 pb-8">
          <div className="grid items-center gap-8 rounded-xl border border-[#E4E7DC] bg-white p-6 sm:p-8 lg:grid-cols-[1fr_auto]">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-[#5E6B63]">A price drop, after you already paid</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-[#12372A]">Nike Air Max 270</h2>
              <p className="mt-2 text-sm text-[#5E6B63]">Bought at $160. The price falls to $120. DropShop claims the difference.</p>
            </div>
            <div className="flex items-center gap-4">
              <div>
                <p className="text-sm text-[#5E6B63] line-through">$160</p>
                <p className="text-3xl font-semibold tabular-nums text-[#12372A]">$120</p>
              </div>
              <ArrowDownRight className="h-8 w-8 text-[#146C3A]" />
              <div className="rounded-xl bg-[#12372A] px-4 py-3 text-white">
                <p className="text-xs text-white/70">Recovered</p>
                <p className="text-2xl font-semibold tabular-nums text-[#C8F55A]">$40</p>
              </div>
            </div>
          </div>
        </section>

        <section id="features" className="mx-auto max-w-6xl px-5 py-20">
          <h2 className="text-3xl font-semibold tracking-tight text-[#12372A]">What DropShop handles</h2>
          <div className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((feature) => (
              <article key={feature.title} className="rounded-xl border border-[#E4E7DC] bg-white p-5">
                <feature.icon className="h-5 w-5 text-[#12372A]" />
                <h3 className="mt-4 font-semibold text-[#12372A]">{feature.title}</h3>
                <p className="mt-2 text-sm leading-6 text-[#5E6B63]">{feature.body}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="get-started" className="bg-[#12372A] text-white">
          <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-6 px-5 py-16 sm:flex-row sm:items-center">
            <div>
              <h2 className="text-3xl font-semibold tracking-tight">Start with the live demo.</h2>
              <p className="mt-2 max-w-lg text-sm leading-6 text-white/70">No API keys. The sample account already has purchases, claims, and $60 in the vault.</p>
            </div>
            <Button variant="lime" size="lg" asChild><Link href="/onboarding">Get Started</Link></Button>
          </div>
        </section>
      </main>

      <footer className="border-t border-[#E4E7DC]">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-5 py-10 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <Logo />
            <p className="mt-2 text-sm text-[#5E6B63]">You shop. Prices drop. You save.</p>
          </div>
          <div className="flex flex-wrap gap-5 text-sm">
            <a href="#how-it-works">How It Works</a>
            <a href="#features">Features</a>
            <Link href="/onboarding">Get Started</Link>
            <Link href="/dashboard">Dashboard</Link>
          </div>
        </div>
        <p className="border-t border-[#E4E7DC] px-5 py-4 text-center text-xs text-[#5E6B63]">Hackathon demo. Receipts, policies, bank deposits, and vault transfers are simulated.</p>
      </footer>
    </div>
  );
}

function Preview() {
  return (
    <div className="rounded-xl border border-[#E4E7DC] bg-white p-4 shadow-[0_18px_50px_rgba(18,55,42,0.08)]">
      <div className="flex items-center justify-between border-b border-[#E4E7DC] pb-3">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-[#12372A]" />
          <span className="text-sm font-semibold text-[#12372A]">Overview</span>
        </div>
        <span className="rounded-full bg-[#F4F6EE] px-2 py-1 text-[11px] font-medium text-[#5E6B63]">Alex</span>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-2">
        <Mini label="Recovered" value="$60" />
        <Mini label="Potential" value="$171" />
        <Mini label="Tracked" value="11" />
      </div>
      <svg viewBox="0 0 320 90" className="mt-4 h-24 w-full" aria-hidden>
        <path d="M8 70 H70 V70 H120 V48 H180 V48 H240 V28 H312" fill="none" stroke="#12372A" strokeWidth="2.5" />
        <path d="M8 70 H70 V70 H120 V48 H180 V48 H240 V28 H312 V80 H8 Z" fill="#C8F55A" opacity="0.45" />
      </svg>
      <div className="mt-2 flex items-center justify-between rounded-lg bg-[#F7F8F2] px-3 py-3">
        <div className="flex items-center gap-3">
          <BadgeDollarSign className="h-5 w-5 text-[#12372A]" />
          <div>
            <p className="text-sm font-medium">Nike Air Max 270</p>
            <p className="text-xs text-[#5E6B63]">$160 → $120</p>
          </div>
        </div>
        <p className="text-sm font-semibold text-[#146C3A]">+$40</p>
      </div>
    </div>
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[#E4E7DC] px-3 py-2">
      <p className="text-[11px] text-[#5E6B63]">{label}</p>
      <p className="text-lg font-semibold tabular-nums text-[#12372A]">{value}</p>
    </div>
  );
}
