"use client";

import { useState } from "react";
import { ErrorBox, Loading, Pill } from "@/components/ui";
import { useResource } from "@/components/use-resource";
import { api } from "@/lib/api";
import type { IntegrationStatus, Preferences } from "@/types";

export default function SettingsPage() {
  const integrations = useResource<IntegrationStatus[]>("/integrations");
  const preferences = useResource<Preferences>("/preferences");
  const gmail = useResource<{ connected: boolean; email?: string | null; oauth_configured: boolean }>("/integrations/gmail");
  const [message, setMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  async function save(next: Preferences) {
    setActionError(null);
    try {
      await api("/preferences", { method: "PUT", body: JSON.stringify(next) });
      setMessage(
        next.sentient_read_enabled
          ? "Sentient reading is on. The next receipt run will look only at order-like notes in the knowledge folder."
          : "Preferences saved. DropShop does not send notification email.",
      );
      await preferences.reload();
      await integrations.reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not save preferences");
    }
  }

  async function connectGmail() {
    setActionError(null);
    try {
      const body = await api<{ url: string }>("/integrations/gmail/start");
      window.location.href = body.url;
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Gmail is not configured");
    }
  }

  async function disconnectGmail() {
    await api("/integrations/gmail/disconnect", { method: "POST" });
    setMessage("Gmail disconnected.");
    await gmail.reload();
    await integrations.reload();
  }

  async function createSandbox() {
    setActionError(null);
    try {
      const body = await api<{ note: string; account_id: string }>("/integrations/nessie/sandbox-account", {
        method: "POST",
        body: JSON.stringify({ first_name: "Drop", last_name: "Shop" }),
      });
      setMessage(`${body.note} Account ${body.account_id}.`);
      await integrations.reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Nessie request failed");
    }
  }

  async function recheck() {
    setActionError(null);
    try {
      await api("/integrations/recheck", { method: "POST" });
      await integrations.reload();
      setMessage("Connections checked again.");
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Recheck failed");
    }
  }

  if (integrations.loading && !integrations.data) return <Loading label="Loading settings" />;
  if (integrations.error && !integrations.data) return <ErrorBox message={integrations.error} />;
  const prefs = preferences.data;

  return (
    <>
      <p className="muted">Settings</p>
      <h1 className="page-title">Connections and control</h1>
      {message && <div className="banner">{message}</div>}
      {actionError && <ErrorBox message={actionError} />}
      <div className="row-actions" style={{ margin: "12px 0" }}>
        <button className="btn" onClick={() => void recheck()}>Check connections again</button>
      </div>
      <div className="stack">
        {(integrations.data ?? []).map((item) => (
          <article className="panel" key={item.id}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
              <h2 className="serif" style={{ margin: 0 }}>{item.name}</h2>
              <Pill value={item.mode} />
            </div>
            <p>{item.detail}</p>
          </article>
        ))}
      </div>
      <section className="panel" style={{ marginTop: 12 }}>
        <h2 className="serif" style={{ marginTop: 0 }}>Gmail</h2>
        <p>{gmail.data?.connected ? `Connected as ${gmail.data.email ?? "an account"}. Readonly.` : "Not connected."}</p>
        <div className="row-actions">
          <button className="btn primary" onClick={() => void connectGmail()}>Connect Gmail</button>
          <button className="btn" onClick={() => void disconnectGmail()} disabled={!gmail.data?.connected}>Disconnect</button>
        </div>
      </section>
      <section className="panel" style={{ marginTop: 12 }}>
        <h2 className="serif" style={{ marginTop: 0 }}>Nessie sandbox</h2>
        <p>Creates a customer and checking account in Capital One&apos;s sandbox. It does not connect your bank.</p>
        <button className="btn" onClick={() => void createSandbox()}>Create sandbox account</button>
      </section>
      <section className="panel" style={{ marginTop: 12 }}>
        <h2 className="serif" style={{ marginTop: 0 }}>Preferences</h2>
        {prefs ? (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void save(prefs);
            }}
          >
            <label className="field"><span><input type="checkbox" checked={prefs.notify_price_drop} onChange={(event) => preferences.setData({ ...prefs, notify_price_drop: event.target.checked })} /> Price drop</span></label>
            <label className="field"><span><input type="checkbox" checked={prefs.notify_deadline} onChange={(event) => preferences.setData({ ...prefs, notify_deadline: event.target.checked })} /> Deadline</span></label>
            <label className="field"><span><input type="checkbox" checked={prefs.notify_claim} onChange={(event) => preferences.setData({ ...prefs, notify_claim: event.target.checked })} /> Claim updates</span></label>
            <label className="field"><span><input type="checkbox" checked={prefs.sentient_read_enabled} onChange={(event) => preferences.setData({ ...prefs, sentient_read_enabled: event.target.checked })} /> Read Sentient OS order notes</span></label>
            <p className="muted">Notification delivery is not connected. These choices are stored only.</p>
            <button className="btn primary" type="submit">Save preferences</button>
          </form>
        ) : (
          <Loading label="Loading preferences" />
        )}
      </section>
    </>
  );
}
