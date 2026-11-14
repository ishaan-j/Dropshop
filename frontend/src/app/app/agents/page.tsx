"use client";

import { useEffect, useState } from "react";
import { ErrorBox, Loading, Pill } from "@/components/ui";
import { useResource } from "@/components/use-resource";
import { api, apiUrl, ensureSession, when } from "@/lib/api";
import type { AgentEvent, AgentSnapshot } from "@/types";

const ACTIONS = [
  ["/agents/receipt/run", "Run receipt agent"],
  ["/agents/price/run", "Run price agent"],
  ["/agents/eligibility/run", "Run eligibility agent"],
  ["/agents/claims/prepare", "Prepare claims"],
] as const;

export default function AgentsPage() {
  const agents = useResource<AgentSnapshot[]>("/agents");
  const activity = useResource<AgentEvent[]>("/activity?limit=30");
  const [live, setLive] = useState<"connecting" | "live" | "disconnected">("connecting");
  const [streamed, setStreamed] = useState<AgentEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    let source: EventSource | null = null;
    let cancelled = false;
    void (async () => {
      try {
        const token = await ensureSession();
        if (cancelled) return;
        source = new EventSource(apiUrl(`/agents/stream?token=${encodeURIComponent(token)}`));
        source.onopen = () => setLive("live");
        source.onerror = () => setLive("disconnected");
        source.onmessage = (event) => {
          const parsed = JSON.parse(event.data) as AgentEvent;
          setStreamed((current) => [parsed, ...current].slice(0, 40));
        };
      } catch {
        setLive("disconnected");
      }
    })();
    return () => {
      cancelled = true;
      source?.close();
    };
  }, []);

  async function run(path: string) {
    setBusy(path);
    setError(null);
    try {
      await api(path, { method: "POST" });
      await agents.reload();
      await activity.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Agent run failed");
      await agents.reload();
    } finally {
      setBusy(null);
    }
  }

  const events = [...streamed, ...(activity.data ?? [])].filter(
    (event, index, all) => all.findIndex((item) => item.id === event.id) === index,
  );

  return (
    <>
      <p className="muted">Agent center</p>
      <h1 className="page-title">What the agents actually did</h1>
      <p className="lede">
        Stream: {live === "live" ? "connected to saved backend events" : live === "connecting" ? "connecting" : "disconnected. Showing saved events."}
        {" "}These runs are DropShop&apos;s. Sentient OS is not shown as the orchestrator unless Settings says its knowledge folder was read.
      </p>
      {error && <ErrorBox message={error} />}
      <div className="row-actions" style={{ margin: "14px 0" }}>
        {ACTIONS.map(([path, label]) => (
          <button key={path} className="btn" disabled={busy !== null} onClick={() => void run(path)}>
            {busy === path ? "Running…" : label}
          </button>
        ))}
      </div>
      {agents.loading && !agents.data ? <Loading /> : null}
      {agents.error && <ErrorBox message={agents.error} />}
      <div className="agents">
        {(agents.data ?? []).map((agent) => (
          <article className="panel" key={agent.name}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <h2 className="serif" style={{ margin: 0 }}>{agent.title}</h2>
              <span className={`pill pill-${agent.status === "error" ? "error" : agent.status === "running" ? "live" : "sandbox"}`}>{agent.status}</span>
            </div>
            <p>{agent.responsibility}</p>
            <p className="muted">Last run {when(agent.last_run_at)}</p>
            {agent.current_task && <p>Now: {agent.current_task}</p>}
            {agent.last_result && <p>{agent.last_result}</p>}
            {agent.last_error && <p>{agent.last_error}</p>}
            {agent.data_origin && <Pill value={agent.data_origin} />}
          </article>
        ))}
      </div>
      <section className="panel" style={{ marginTop: 12 }}>
        <h2 className="serif" style={{ marginTop: 0 }}>Events</h2>
        {events.length === 0 ? (
          <p className="muted">No events yet. Run an agent or the demo scenario.</p>
        ) : (
          <div className="timeline">
            {events.slice(0, 25).map((event) => (
              <article key={event.id}>
                <div className="muted">{when(event.time)} · {event.agent ?? "system"} · <Pill value={event.data_origin} /></div>
                <div>{event.message}</div>
              </article>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
