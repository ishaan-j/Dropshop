"use client";

import { useState } from "react";
import { ErrorBox, Loading, Pill } from "@/components/ui";
import { useResource } from "@/components/use-resource";
import { api, money, openAuthorized, when } from "@/lib/api";
import type { Claim, Opportunity, Refund } from "@/types";

export default function OpportunitiesPage() {
  const { data, error, loading, reload } = useResource<Opportunity[]>("/opportunities");
  const [message, setMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);

  async function act(id: string, path: string) {
    setBusy(id);
    setActionError(null);
    try {
      const result = await api<Claim | { claim: Claim; submitted: boolean; note: string }>(path, { method: "POST" });
      if ("note" in result && result.note) setMessage(result.note);
      else if ("submission_note" in result && result.submission_note) setMessage(result.submission_note);
      setRevision((value) => value + 1);
      await reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy(null);
    }
  }

  async function refund(id: string, kind: "demo" | "nessie") {
    setBusy(id);
    setActionError(null);
    try {
      const result = await api<Refund>(`/refunds/${id}/${kind}`, { method: "POST" });
      setMessage(result.explanation);
      setRevision((value) => value + 1);
      await reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Refund action failed");
    } finally {
      setBusy(null);
    }
  }

  if (loading && !data) return <Loading label="Loading opportunities" />;
  if (error && !data) return <ErrorBox message={error} />;

  return (
    <>
      <p className="muted">Opportunities</p>
      <h1 className="page-title">Drops, and the reason each one counts or does not</h1>
      {message && <div className="banner">{message}</div>}
      {actionError && <ErrorBox message={actionError} />}
      {(data ?? []).length === 0 ? (
        <div className="empty">
          <strong>No decisions yet.</strong>
          <p className="muted">Run the demo scenario or a price check. Ineligible drops stay on this page so the rule is visible.</p>
        </div>
      ) : (
        <div className="list">
          {(data ?? []).map((item) => (
            <article className="panel" key={item.purchase_id}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                <div>
                  <h2 className="serif" style={{ margin: 0 }}>{item.product_name}</h2>
                  <p className="muted">{item.retailer} · bought {when(item.purchased_at)} · deadline {when(item.deadline)}</p>
                </div>
                <div className="row-actions">
                  <Pill value={item.data_origin} />
                  <Pill value={item.eligibility} />
                  {item.claim_status && <Pill value={item.claim_status} />}
                </div>
              </div>
              <p>Paid {money(item.price_paid_cents)} · current {money(item.current_price_cents)} · potential {money(item.difference_cents)}</p>
              <p>{item.reason}</p>
              <p className="muted">Price source: {item.price_source ?? "none"}. {item.policy_url ? `Policy ${item.policy_url}.` : "No policy URL."}</p>
              <ul>{item.evidence.map((line) => <li key={line}>{line}</li>)}</ul>
              {item.missing_information.length > 0 && <p>Missing: {item.missing_information.join(", ")}</p>}
              {item.claim_id && item.claim_status === "awaiting_approval" && (
                <div className="row-actions">
                  <button className="btn primary" disabled={busy === item.claim_id} onClick={() => void act(item.claim_id!, `/claims/${item.claim_id}/approve`)}>
                    Approve submission
                  </button>
                  <button className="btn danger" disabled={busy === item.claim_id} onClick={() => void act(item.claim_id!, `/claims/${item.claim_id}/reject`)}>
                    Reject
                  </button>
                </div>
              )}
              {item.claim_id && item.claim_status === "submitted" && (
                <div className="row-actions">
                  <button className="btn" disabled={busy === item.claim_id} onClick={() => void refund(item.claim_id!, "demo")}>
                    Record demo refund
                  </button>
                  <button className="btn" disabled={busy === item.claim_id} onClick={() => void refund(item.claim_id!, "nessie")}>
                    Post Nessie sandbox deposit
                  </button>
                </div>
              )}
              <Evidence key={`${item.claim_id ?? item.purchase_id}-${revision}`} claimId={item.claim_id} />
            </article>
          ))}
        </div>
      )}
    </>
  );
}

function Evidence({ claimId }: { claimId: string | null }) {
  const claim = useResource<Claim[]>(claimId ? "/claims" : null);
  const match = claim.data?.find((item) => item.id === claimId);
  if (!match) return null;
  return (
    <div style={{ marginTop: 8 }}>
      {match.submission_note && <p>{match.submission_note}</p>}
      {match.explanation_source === "gemini" && <p className="muted">Explanation rewritten by Gemini and checked against the verified amounts.</p>}
      {match.explanation_source === "template" && <p className="muted">Explanation written from the verified fields.</p>}
      {match.manual_packet && (
        <details>
          <summary>Manual claim packet</summary>
          <p>{match.manual_packet}</p>
        </details>
      )}
      {match.screenshots.map((name) => (
        <button key={name} className="btn" onClick={() => void openAuthorized(`/claims/${match.id}/screenshots/${name}`)}>
          Open screenshot
        </button>
      ))}
    </div>
  );
}
