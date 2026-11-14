"use client";

import type { ReactNode } from "react";
import { DemoNote } from "@/components/page-header";
import { liveNote, useBackend } from "@/lib/live";
import type { BackendStatus } from "@/types";

/**
 * The small "what's real here" note. On the local demo ledger it shows `demo` (or DemoNote's
 * default). Connected to the backend it shows `live(status)`, or a summary of what the backend
 * is running against.
 */
export function StatusNote({ demo, live }: { demo?: ReactNode; live?: (status: BackendStatus) => ReactNode }) {
  const backend = useBackend();
  if (!backend) return <DemoNote>{demo}</DemoNote>;
  return <DemoNote>{live ? live(backend) : liveNote(backend)}</DemoNote>;
}
