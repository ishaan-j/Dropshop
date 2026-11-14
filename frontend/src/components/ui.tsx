"use client";

import type { IntegrationMode } from "@/types";

const MODE_LABEL: Record<string, string> = {
  live: "Live",
  sandbox: "Sandbox",
  demo: "Demo",
  not_connected: "Not connected",
  error: "Error",
  eligible: "Eligible",
  ineligible: "Not eligible",
  needs_review: "Needs review",
  unknown: "Unknown",
  monitoring: "Monitoring",
  drop_detected: "Drop detected",
  claim_pending: "Claim ready",
  claimed: "Claimed",
  expired: "Expired",
  awaiting_approval: "Needs approval",
  submitting: "Submitting",
  submitted: "Submitted",
  refund_received: "Refund recorded",
  rejected: "Rejected",
  failed: "Failed",
};

export function Pill({ value }: { value: string }) {
  return <span className={`pill pill-${value}`}>{MODE_LABEL[value] ?? value.replaceAll("_", " ")}</span>;
}

export function ModeNote({ mode }: { mode: IntegrationMode | string }) {
  return <Pill value={mode} />;
}

export function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      <p className="muted">{body}</p>
    </div>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="error-box" role="alert">
      {message}
    </div>
  );
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return <p className="muted">{label}…</p>;
}
