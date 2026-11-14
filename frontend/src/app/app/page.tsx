"use client";

import Link from "next/link";
import { useState } from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ErrorBox, Loading, Pill } from "@/components/ui";
import { useResource } from "@/components/use-resource";
import { api, money, when } from "@/lib/api";
import type { Dashboard } from "@/types";

export default function DashboardPage() {
  const { data, error, loading, reload } = useResource<Dashboard>("/dashboard");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  async function runDemo() {
    setBusy(true);
    setActionError(null);
    try {
      const result = await api<{ note: string }>("/demo/scenario", { method: "POST" });
      setNote(result.note);
      await reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Demo scenario failed");
    } finally {
      setBusy(false);
    }
  }

  if (loading && !data) return <Loading label="Loading dashboard" />;
  if (error && !data) return <ErrorBox message={error} />;
  if (!data) return null;

  const chart = data.savings_series.map((point) => ({
    label: when(point.time),
    dollars: point.total_recovered_cents / 100,
    origin: point.data_origin,
  }));

  return (
    <>
      <p className="muted">Overview</p>
      <h1 className="page-title">What DropShop can account for</h1>
      {data.includes_demo_data && (
        <div className="banner">
          Some records are demo data: sample emails and Harbor &amp; Co catalog prices. They are not your Gmail and not a live retailer.
        </div>
      )}
      {note && <div className="banner">{note}</div>}
      {actionError && <ErrorBox message={actionError} />}
      <div className="row-actions" style={{ marginTop: 16 }}>
        <button className="btn primary" disabled={busy} onClick={() => void runDemo()}>
          {busy ? "Running demo…" : "Run labeled demo scenario"}
        </button>
        <Link className="btn" href="/app/opportunities">Review opportunities</Link>
      </div>
      <section className="metrics">
        <article className="metric"><span>Recovered</span><strong>{money(data.total_recovered_cents)}</strong></article>
        <article className="metric"><span>Pending claims</span><strong>{money(data.pending_refund_cents)}</strong></article>
        <article className="metric"><span>Potential difference</span><strong>{money(data.potential_savings_cents)}</strong></article>
        <article className="metric"><span>Drops detected</span><strong>{data.price_drops_detected}</strong></article>
      </section>
      <p className="muted">
        {data.purchase_count} purchases on file. {data.purchases_monitored} still waiting for a first price check.
        Persistence: {data.persistence.replaceAll("_", " ")}.
        Recovered money counts matched refund records only.
      </p>
      <div className="grid-2">
        <section className="panel">
          <h2 className="serif" style={{ marginTop: 0 }}>Recovered over time</h2>
          {chart.length === 0 ? (
            <p className="muted">No matched refunds yet, so there is no savings line.</p>
          ) : (
            <div style={{ height: 220 }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chart}>
                  <XAxis dataKey="label" hide />
                  <YAxis width={48} />
                  <Tooltip formatter={(value) => [`$${Number(value).toFixed(2)}`, "Recovered"]} />
                  <Area dataKey="dollars" stroke="#0f6e56" fill="#e5f4ef" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>
        <section className="panel">
          <h2 className="serif" style={{ marginTop: 0 }}>Vault</h2>
          <p>{data.vault_network}</p>
          <p className="mono" style={{ wordBreak: "break-all" }}>{data.vault_address ?? "No vault address"}</p>
          <p>
            {data.vault_balance_verified
              ? `${data.vault_balance_lamports} lamports, read from Devnet`
              : "Balance not verified"}
          </p>
          <Link href="/app/vault">Open vault</Link>
        </section>
      </div>
      <div className="grid-2" style={{ marginTop: 12 }}>
        <section className="panel">
          <h2 className="serif" style={{ marginTop: 0 }}>Deadlines</h2>
          {data.upcoming_deadlines.length === 0 ? (
            <p className="muted">No open adjustment windows.</p>
          ) : (
            <div className="stack">
              {data.upcoming_deadlines.map((item) => (
                <div key={item.purchase_id}>
                  <strong>{item.product_name}</strong>
                  <div className="muted">{item.retailer} · {when(item.deadline)} · <Pill value={item.data_origin} /></div>
                </div>
              ))}
            </div>
          )}
        </section>
        <section className="panel">
          <h2 className="serif" style={{ marginTop: 0 }}>Connections</h2>
          <div className="stack">
            {data.integrations.map((item) => (
              <div key={item.id}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                  <strong>{item.name}</strong>
                  <Pill value={item.mode} />
                </div>
                <p className="muted" style={{ margin: "4px 0 0" }}>{item.detail}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
      <section className="panel" style={{ marginTop: 12 }}>
        <h2 className="serif" style={{ marginTop: 0 }}>Recent activity</h2>
        {data.recent_activity.length === 0 ? (
          <p className="muted">No agent events yet.</p>
        ) : (
          <div className="stack">
            {data.recent_activity.map((event) => (
              <div key={event.id}>
                <Pill value={event.data_origin} /> <span className="muted">{when(event.time)}</span>
                <div>{event.message}</div>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
