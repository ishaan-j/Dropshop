"use client";

import { type FormEvent, useState } from "react";
import { toast } from "sonner";
import { PageHeader, Panel } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { useDemo } from "@/components/demo/demo-provider";
import { useBackend } from "@/lib/live";
import { resetBackendDemo } from "@/lib/services";
import { delay, shorten } from "@/lib/utils";
import { useAppStore } from "@/store/app-store";

export function SettingsView() {
  const demo = useDemo();
  const user = useAppStore((state) => state.user);
  const settings = useAppStore((state) => state.settings);
  const emailConnected = useAppStore((state) => state.emailConnected);
  const bankConnected = useAppStore((state) => state.bankConnected);
  const walletConnected = useAppStore((state) => state.walletConnected);
  const updateProfile = useAppStore((state) => state.updateProfile);
  const updateSettings = useAppStore((state) => state.updateSettings);
  const setEmailConnected = useAppStore((state) => state.setEmailConnected);
  const setBankConnected = useAppStore((state) => state.setBankConnected);
  const setWalletConnected = useAppStore((state) => state.setWalletConnected);
  const resetDemo = useAppStore((state) => state.resetDemo);
  const backend = useBackend();

  async function reset() {
    demo.halt();
    setConfirmReset(false);
    if (!backend) {
      resetDemo();
      toast.success("Demo data reset");
      return;
    }
    try {
      await resetBackendDemo();
      toast.success("Backend demo reset");
    } catch {
      toast.error("The backend couldn't reset. Is it running with DEMO_MODE on?");
    }
  }
  const saved = `${user.name}|${user.email}|${settings.minRefundCents}`;
  const [source, setSource] = useState(saved);
  const [form, setForm] = useState({
    name: user.name,
    email: user.email,
    minimum: String(settings.minRefundCents / 100),
  });
  if (source !== saved) {
    setSource(saved);
    setForm({ name: user.name, email: user.email, minimum: String(settings.minRefundCents / 100) });
  }
  const { name, email, minimum } = form;
  const [errors, setErrors] = useState<{ name?: string; email?: string; min?: string }>({});
  const [saving, setSaving] = useState(false);
  const [connecting, setConnecting] = useState<string | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);

  async function onSave(event: FormEvent) {
    event.preventDefault();
    const nextErrors: typeof errors = {};
    if (name.trim().length < 2) nextErrors.name = "Enter at least two characters.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) nextErrors.email = "Enter a valid email address.";
    const dollars = Number(minimum);
    if (!Number.isFinite(dollars) || dollars < 0 || dollars > 1000) nextErrors.min = "Enter an amount from 0 to 1000.";
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;
    setSaving(true);
    await delay(300);
    updateProfile({ name, email });
    updateSettings({ minRefundCents: Math.round(dollars * 100) });
    setSaving(false);
    toast.success("Profile saved");
  }

  async function connect(kind: "email" | "bank" | "wallet", connected: boolean, setter: (value: boolean) => void) {
    if (connected) {
      setter(false);
      toast.success("Disconnected");
      return;
    }
    setConnecting(kind);
    await delay(700);
    setter(true);
    setConnecting(null);
    toast.success("Connected (simulated)");
  }

  return (
    <div>
      <PageHeader
        eyebrow="Settings"
        title="Your account"
        description="Profile, connections, and demo preferences stay in this browser."
      />
      <form onSubmit={onSave} className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <h2 className="font-semibold text-[#12372A]">Profile</h2>
          <label className="mt-4 block text-sm font-medium" htmlFor="name">Name</label>
          <input id="name" value={name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} autoComplete="name" className="mt-1 h-10 w-full rounded-lg border border-[#D5DACB] px-3 text-sm" />
          {errors.name ? <p className="mt-1 text-xs text-[#9B2C2C]">{errors.name}</p> : null}
          <label className="mt-4 block text-sm font-medium" htmlFor="email">Email</label>
          <input id="email" type="email" value={email} onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))} autoComplete="email" className="mt-1 h-10 w-full rounded-lg border border-[#D5DACB] px-3 text-sm" />
          {errors.email ? <p className="mt-1 text-xs text-[#9B2C2C]">{errors.email}</p> : null}
          <label className="mt-4 block text-sm font-medium" htmlFor="minimum">Minimum refund ($)</label>
          <input id="minimum" inputMode="decimal" value={minimum} onChange={(event) => setForm((current) => ({ ...current, minimum: event.target.value }))} className="mt-1 h-10 w-full rounded-lg border border-[#D5DACB] px-3 text-sm" />
          {errors.min ? <p className="mt-1 text-xs text-[#9B2C2C]">{errors.min}</p> : null}
          <p className="mt-1 text-xs text-[#5E6B63]">Drops under this amount are flagged. You can still file them.</p>
          <Button className="mt-5" type="submit" disabled={saving}>{saving ? "Saving…" : "Save profile"}</Button>
        </Panel>
        <Panel>
          <h2 className="font-semibold text-[#12372A]">Connections</h2>
          <Connection name="Email" detail={emailConnected ? email : "Not connected"} connected={emailConnected} pending={connecting === "email"} onClick={() => connect("email", emailConnected, setEmailConnected)} />
          <Connection name="Bank" detail={bankConnected ? `${user.bank_name} ••${user.bank_mask}` : "Not connected"} connected={bankConnected} pending={connecting === "bank"} onClick={() => connect("bank", bankConnected, setBankConnected)} />
          <Connection name="Wallet" detail={walletConnected ? shorten(user.wallet_address, 6, 4) : "Not connected"} connected={walletConnected} pending={connecting === "wallet"} onClick={() => connect("wallet", walletConnected, setWalletConnected)} />
        </Panel>
      </form>

      <Panel className="mt-4">
        <h2 className="font-semibold text-[#12372A]">Preferences</h2>
        <Switch checked={settings.autoTracking} onCheckedChange={(checked) => updateSettings({ autoTracking: checked })} label="Automatic price tracking" description="Keep watching purchases after a receipt is found. The live demo always tracks the Nike example." />
        <Switch checked={settings.autoClaims} onCheckedChange={(checked) => { updateSettings({ autoClaims: checked }); toast.success(checked ? "Automatic claim filing is on. New eligible refunds can be filed without a prompt. The live demo still runs the full sequence." : "Automatic claim filing is off. You will confirm each claim."); }} label="Automatic claim filing" description="When on, eligible refunds are marked ready for Grok Bot. Filing still never contacts a real retailer." />
        <Switch checked={settings.refundNotifications} onCheckedChange={(checked) => updateSettings({ refundNotifications: checked })} label="Refund notifications" description="Show the notification badge and demo toasts." />
      </Panel>

      <Panel className="mt-4">
        <h2 className="font-semibold text-[#12372A]">Privacy</h2>
        <Switch checked={settings.shareAnonymizedUsage} onCheckedChange={(checked) => updateSettings({ shareAnonymizedUsage: checked })} label="Share anonymized usage" description="Stored only on this device. Nothing is uploaded." />
        <Switch checked={settings.marketingEmails} onCheckedChange={(checked) => updateSettings({ marketingEmails: checked })} label="Product emails" description="A local preference for the demo account." />
      </Panel>

      <Panel className="mt-4">
        <h2 className="font-semibold text-[#9B2C2C]">Reset demo</h2>
        <p className="mt-2 text-sm leading-6 text-[#5E6B63]">
          {backend
            ? "Reseeds the backend's purchases, claims and activity, and stops any job still running."
            : "Restores the sample account, removes the live-demo purchase, and clears a replay so the $40 cannot be counted twice."}
        </p>
        <Button className="mt-4" variant="danger" onClick={() => setConfirmReset(true)}>Reset demo</Button>
      </Panel>

      <Dialog open={confirmReset} onOpenChange={setConfirmReset}>
        <DialogContent>
          <DialogTitle>Reset the demo data?</DialogTitle>
          <DialogDescription>
            {backend
              ? "This reseeds the backend's demo state. Claims you approved in this run are cleared."
              : "This restores the sample purchases and clears any Nike demo refund. Your place in the app stays open."}
          </DialogDescription>
          <div className="mt-6 flex justify-end gap-2">
            <Button variant="outline" onClick={() => setConfirmReset(false)}>Cancel</Button>
            <Button variant="danger" onClick={reset}>Reset</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Connection({
  name,
  detail,
  connected,
  pending,
  onClick,
}: {
  name: string;
  detail: string;
  connected: boolean;
  pending: boolean;
  onClick: () => void;
}) {
  return (
    <div className="mt-4 flex items-center justify-between gap-3 border-t border-[#E4E7DC] pt-4 first:border-0">
      <div>
        <p className="text-sm font-medium">{name}</p>
        <p className="text-sm text-[#5E6B63]">{detail}</p>
      </div>
      <Button size="sm" variant={connected ? "outline" : "primary"} onClick={onClick} disabled={pending}>
        {pending ? "Connecting…" : connected ? "Disconnect" : "Connect"}
      </Button>
    </div>
  );
}
