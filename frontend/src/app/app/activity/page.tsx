"use client";

import { ErrorBox, Loading, Pill } from "@/components/ui";
import { useResource } from "@/components/use-resource";
import { when } from "@/lib/api";
import type { AgentEvent } from "@/types";

export default function ActivityPage() {
  const { data, error, loading } = useResource<AgentEvent[]>("/activity?limit=100");
  if (loading && !data) return <Loading label="Loading activity" />;
  if (error) return <ErrorBox message={error} />;
  return (
    <>
      <p className="muted">Activity</p>
      <h1 className="page-title">The trail, in order</h1>
      {(data ?? []).length === 0 ? (
        <div className="empty">
          <strong>Nothing has happened in this session yet.</strong>
          <p className="muted">Events appear after an agent runs. This page does not invent a timeline.</p>
        </div>
      ) : (
        <div className="timeline">
          {(data ?? []).map((event) => (
            <article key={event.id}>
              <div className="muted">{when(event.time)} · {event.kind.replaceAll("_", " ")} · <Pill value={event.data_origin} /></div>
              <div>{event.message}</div>
            </article>
          ))}
        </div>
      )}
    </>
  );
}
