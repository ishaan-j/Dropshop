"use client";

import { useState } from "react";

/**
 * Mock retailer price-adjustment form. The Playwright claim bot (backend/agents/claim_bot.py)
 * fills this page. Keep the data-testid values in sync with docs/demo-store-contract.md.
 */
export default function DemoStoreClaimPage() {
  const [reference, setReference] = useState<string | null>(null);

  function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const order = new FormData(event.currentTarget).get("order") as string;
    setReference(`PA-${(order || "0000").replace(/[^A-Za-z0-9]/g, "").slice(-6).toUpperCase()}-${Date.now().toString().slice(-4)}`);
  }

  const input = "mt-1 h-10 w-full rounded-lg border border-[#D9DED3] bg-white px-3 text-sm";

  return (
    <main className="mx-auto max-w-xl px-6 py-12">
      <p className="text-xs font-semibold uppercase tracking-wide text-[#5E6B63]">Demo Store · Customer care</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[#12372A]">Price adjustment request</h1>
      <p className="mt-3 text-sm leading-6 text-[#5E6B63]">
        Bought something that has since dropped in price? Tell us about it and we&apos;ll refund the difference.
      </p>

      {/* data-ready tells the claim bot the submit handler is attached (see docs/demo-store-contract.md). */}
      <form
        onSubmit={onSubmit}
        data-ready="false"
        ref={(form) => {
          if (form) form.dataset.ready = "true";
        }}
        className="mt-8 space-y-4"
      >
        <label className="block text-sm font-medium">
          Order number
          <input name="order" data-testid="order-number" className={input} required />
        </label>
        <label className="block text-sm font-medium">
          Product
          <input name="product" data-testid="product-name" className={input} required />
        </label>
        <div className="grid grid-cols-2 gap-4">
          <label className="block text-sm font-medium">
            Price paid ($)
            <input name="paid" data-testid="price-paid" inputMode="decimal" className={input} required />
          </label>
          <label className="block text-sm font-medium">
            Current price ($)
            <input name="current" data-testid="current-price" inputMode="decimal" className={input} required />
          </label>
        </div>
        <label className="block text-sm font-medium">
          Message
          <textarea name="message" data-testid="message" rows={5} className={`${input} h-auto py-2`} required />
        </label>
        <button
          type="submit"
          data-testid="submit"
          className="h-10 rounded-lg bg-[#12372A] px-5 text-sm font-semibold text-white"
        >
          Submit request
        </button>
      </form>

      {reference && (
        <div
          data-testid="claim-confirmation"
          className="mt-6 rounded-lg border border-[#12372A] bg-[#EAF3EC] p-4 text-sm font-medium text-[#12372A]"
        >
          Request received. Reference {reference}
        </div>
      )}
    </main>
  );
}
