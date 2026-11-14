"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ErrorBox, Loading, Pill } from "@/components/ui";
import { useResource } from "@/components/use-resource";
import { api, money, when } from "@/lib/api";
import type { Purchase } from "@/types";

export default function PurchasesPage() {
  const { data, error, loading, reload } = useResource<Purchase[]>("/purchases");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [sort, setSort] = useState("newest");
  const [formError, setFormError] = useState<string | null>(null);
  const [retailer, setRetailer] = useState("");
  const [product, setProduct] = useState("");
  const [price, setPrice] = useState("");
  const [date, setDate] = useState("");

  const rows = useMemo(() => {
    const list = (data ?? []).filter((purchase) => {
      const hay = `${purchase.product_name} ${purchase.retailer}`.toLowerCase();
      if (query && !hay.includes(query.toLowerCase())) return false;
      if (status !== "all" && purchase.status !== status && purchase.eligibility !== status) return false;
      return true;
    });
    return list.sort((a, b) => {
      if (sort === "difference") {
        const diff = (item: Purchase) =>
          item.current_price_cents == null ? -1 : item.price_paid_cents - item.current_price_cents;
        return diff(b) - diff(a);
      }
      if (sort === "retailer") return a.retailer.localeCompare(b.retailer);
      return +new Date(b.purchased_at) - +new Date(a.purchased_at);
    });
  }, [data, query, status, sort]);

  async function addPurchase(event: React.FormEvent) {
    event.preventDefault();
    setFormError(null);
    try {
      await api("/purchases", {
        method: "POST",
        body: JSON.stringify({
          retailer,
          product_name: product,
          price_paid_cents: Math.round(Number(price) * 100),
          purchased_at: new Date(date).toISOString(),
        }),
      });
      setRetailer("");
      setProduct("");
      setPrice("");
      setDate("");
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not save the purchase");
    }
  }

  if (loading && !data) return <Loading label="Loading purchases" />;
  if (error && !data) return <ErrorBox message={error} />;

  return (
    <>
      <p className="muted">Purchases</p>
      <h1 className="page-title">What is being watched</h1>
      <div className="filters">
        <input placeholder="Search product or retailer" value={query} onChange={(event) => setQuery(event.target.value)} />
        <select value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="all">All statuses</option>
          <option value="monitoring">Monitoring</option>
          <option value="drop_detected">Drop detected</option>
          <option value="claim_pending">Claim ready</option>
          <option value="eligible">Eligible</option>
          <option value="ineligible">Not eligible</option>
          <option value="expired">Expired</option>
        </select>
        <select value={sort} onChange={(event) => setSort(event.target.value)}>
          <option value="newest">Newest</option>
          <option value="difference">Largest difference</option>
          <option value="retailer">Retailer</option>
        </select>
      </div>
      {rows.length === 0 ? (
        <div className="empty">
          <strong>No purchases match.</strong>
          <p className="muted">Run the labeled demo on the overview, connect Gmail, or add a purchase yourself. A blank current price means DropShop has no authorized price source.</p>
        </div>
      ) : (
        <div className="list">
          {rows.map((purchase) => {
            const difference =
              purchase.current_price_cents == null ? null : purchase.price_paid_cents - purchase.current_price_cents;
            return (
              <Link className="item" key={purchase.id} href={`/app/purchases/${purchase.id}`}>
                <div>
                  <strong>{purchase.product_name}</strong>
                  <div className="muted">{purchase.retailer} · bought {when(purchase.purchased_at)}</div>
                  <div style={{ marginTop: 8 }}>
                    <Pill value={purchase.data_origin} /> <Pill value={purchase.status} /> <Pill value={purchase.eligibility} />
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div>Paid {money(purchase.price_paid_cents)}</div>
                  <div>Current {money(purchase.current_price_cents)}</div>
                  <div>{difference == null ? "No verified price" : `Difference ${money(difference)}`}</div>
                  <div className="muted">{purchase.price_source ?? "no price source"}</div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
      <form className="panel" style={{ marginTop: 16 }} onSubmit={addPurchase}>
        <h2 className="serif" style={{ marginTop: 0 }}>Add a purchase yourself</h2>
        <p className="muted">This does not check a live price. Eligibility stays unknown until a price source exists.</p>
        <div className="filters">
          <input required placeholder="Retailer" value={retailer} onChange={(event) => setRetailer(event.target.value)} />
          <input required placeholder="Product" value={product} onChange={(event) => setProduct(event.target.value)} />
          <input required type="number" min="0.01" step="0.01" placeholder="Price paid" value={price} onChange={(event) => setPrice(event.target.value)} />
          <input required type="date" value={date} onChange={(event) => setDate(event.target.value)} />
          <button className="btn primary" type="submit">Save</button>
        </div>
        {formError && <ErrorBox message={formError} />}
      </form>
    </>
  );
}
