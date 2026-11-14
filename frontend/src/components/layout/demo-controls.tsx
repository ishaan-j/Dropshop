"use client";

import { useState } from "react";
import * as Menu from "@radix-ui/react-dropdown-menu";
import { RotateCcw, ScanLine, ShieldCheck, SlidersHorizontal, TrendingDown } from "lucide-react";
import { toast } from "sonner";
import { useBackend } from "@/lib/live";
import { resetBackendDemo, runPolicyWatch, scanForPurchases, triggerPriceDrop } from "@/lib/services";
import { formatCents } from "@/lib/utils";

type Control = "scan" | "drop" | "policy" | "reset";

const ITEM = "flex cursor-pointer items-start gap-3 rounded-lg px-2 py-2 text-left outline-none hover:bg-[#F3F5EE] data-[disabled]:opacity-50";

/**
 * Presenter controls for the live backend: each one starts a real background job, and the
 * screens update as it runs. Hidden while the app is on its local demo ledger.
 */
export function DemoControls() {
  const backend = useBackend();
  const [busy, setBusy] = useState<Control | null>(null);
  if (!backend) return null;

  async function run(control: Control) {
    setBusy(control);
    try {
      if (control === "scan") {
        await scanForPurchases();
        toast.success("Scanning receipts. New purchases appear in the tracker.");
      } else if (control === "drop") {
        const drop = await triggerPriceDrop();
        toast.success(`${drop.product_name} dropped to ${formatCents(drop.new_price_cents)}. The agents are checking eligibility.`);
      } else if (control === "policy") {
        const result = await runPolicyWatch();
        if (!result || result.reviewed === 0) toast.message("Grok is off (mock mode or no xAI key), so no policies were checked.");
        else if (result.changed.length) toast.success(`Grok found a policy change at ${result.changed.join(", ")}.`);
        else toast.success(`Grok checked ${result.reviewed} retailer ${result.reviewed === 1 ? "policy" : "policies"}: no changes.`);
      } else {
        await resetBackendDemo();
        toast.success("Backend demo reset");
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "";
      toast.error(message.includes("409") ? "Nothing to do: no purchase is being monitored right now." : "The backend didn't accept that. Is it running with DEMO_MODE on?");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Menu.Root>
      <Menu.Trigger asChild>
        <button
          type="button"
          className="inline-flex h-10 items-center gap-2 rounded-lg border border-[#D5DACB] bg-white px-3 text-sm font-semibold text-[#12372A] hover:bg-[#F3F5EE]"
          aria-label="Backend demo controls"
        >
          <SlidersHorizontal className="h-4 w-4" />
          <span className="hidden md:inline">Demo controls</span>
        </button>
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Content className="z-50 w-72 rounded-xl border border-[#E4E7DC] bg-white p-2 shadow-xl" align="end" sideOffset={8}>
          <p className="px-2 py-1.5 text-xs leading-5 text-[#5E6B63]">
            Live backend · {backend.mock_mode ? "mock integrations" : "live integrations"}. Each action runs a real background job.
          </p>
          <Menu.Item className={ITEM} disabled={busy !== null} onSelect={() => run("scan")}>
            <ScanLine className="mt-0.5 h-4 w-4 shrink-0 text-[#12372A]" />
            <span>
              <span className="block text-sm font-medium text-[#17211C]">Scan for receipts</span>
              <span className="block text-xs text-[#5E6B63]">Find purchases that aren&apos;t tracked yet.</span>
            </span>
          </Menu.Item>
          <Menu.Item className={ITEM} disabled={busy !== null} onSelect={() => run("drop")}>
            <TrendingDown className="mt-0.5 h-4 w-4 shrink-0 text-[#12372A]" />
            <span>
              <span className="block text-sm font-medium text-[#17211C]">Trigger a price drop</span>
              <span className="block text-xs text-[#5E6B63]">Cut the priciest monitored item by 15%.</span>
            </span>
          </Menu.Item>
          <Menu.Item className={ITEM} disabled={busy !== null} onSelect={() => run("policy")}>
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-[#12372A]" />
            <span>
              <span className="block text-sm font-medium text-[#17211C]">Run Grok policy watch</span>
              <span className="block text-xs text-[#5E6B63]">Check retailer policies for changes now.</span>
            </span>
          </Menu.Item>
          <Menu.Separator className="my-1 h-px bg-[#E4E7DC]" />
          <Menu.Item className={ITEM} disabled={busy !== null} onSelect={() => run("reset")}>
            <RotateCcw className="mt-0.5 h-4 w-4 shrink-0 text-[#9B2C2C]" />
            <span>
              <span className="block text-sm font-medium text-[#9B2C2C]">Reset backend demo</span>
              <span className="block text-xs text-[#5E6B63]">Reseed purchases, claims and activity.</span>
            </span>
          </Menu.Item>
        </Menu.Content>
      </Menu.Portal>
    </Menu.Root>
  );
}
