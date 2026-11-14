"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ErrorBox, Loading, Pill } from "@/components/ui";
import { useResource } from "@/components/use-resource";
import { apiUrl, money, when } from "@/lib/api";
import type { PricePoint, Purchase } from "@/types";

export default function PurchaseDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const purchase = useResource<Purchase>(id ? `/purchases/${id}` : null);
  const prices = useResource<PricePoint[]>(purchase.data ? `/prices/${encodeURIComponent(purchase.data.product_id)}?days=120` : null);

  if (purchase.loading && !purchase.data) return <Loading label="Loading purchase" />;
  if (purchase.error) return <ErrorBox message={purchase.error} />;
  if (!purchase.data) return null;
  const item = purchase.data;
  const chart = (prices.data ?? []).map((point) => ({
    label: when(point.time),
    dollars: point.price_cents / 100,
    source: point.source,
    origin: point.data_origin,
  }));

  return (
    <>
      <Link href="/app/purchases">← Purchases</Link>
      <p className="muted" style={{ marginTop: 12 }}>{item.retailer}</p>
      <h1 className="page-title">{item.product_name}</h1>
      <div className="row-actions" style={{ margin: "12px 0" }}>
        <Pill value={item.data_origin} />
        <Pill value={item.status} />
        <Pill value={item.eligibility} />
        {item.final_sale && <Pill value="ineligible" />}
      </div>
      <div className="metrics">
        <article className="metric"><span>Paid</span><strong>{money(item.price_paid_cents)}</strong></article>
        <article className="metric"><span>Current verified</span><strong>{money(item.current_price_cents)}</strong></article>
        <article className="metric"><span>Source</span><strong style={{ fontSize: 18 }}>{item.price_source ?? "None"}</strong></article>
        <article className="metric"><span>Deadline</span><strong style={{ fontSize: 18 }}>{when(item.adjustment_window_ends)}</strong></article>
      </div>
      <section className="panel">
        <h2 className="serif" style={{ marginTop: 0 }}>Price observations</h2>
        {prices.error && <ErrorBox message={prices.error} />}
        {chart.length === 0 ? (
          <p className="muted">No observations stored for this product.</p>
        ) : (
          <div style={{ height: 240 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chart}>
                <XAxis dataKey="label" hide />
                <YAxis width={48} />
                <Tooltip formatter={(value, _name, entry) => [`$${Number(value).toFixed(2)} (${entry.payload.source}, ${entry.payload.origin})`, "Price"]} />
                <Line dataKey="dollars" stroke="#0f6e56" dot />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
        <p className="muted">A point labeled purchase_record is the price on the receipt. It is not an independent price check.</p>
      </section>
      <section className="panel" style={{ marginTop: 12 }}>
        <h2 className="serif" style={{ marginTop: 0 }}>Why this eligibility</h2>
        <p>{item.eligibility_reason || "Not evaluated yet."}</p>
        <ul>
          {item.eligibility_evidence.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        {item.policy_url && (
          <p>
            Policy: <a href={apiUrl(item.policy_url)}>{item.policy_url}</a>
          </p>
        )}
        <p className="muted">Order {item.order_number ?? "not recorded"} · observed {when(item.price_observed_at)}</p>
      </section>
    </>
  );
}
