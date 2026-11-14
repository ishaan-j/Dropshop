"use client";

import { Suspense } from "react";
import { Shell } from "@/components/shell";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <Shell>
      <Suspense fallback={<p className="muted">Loading…</p>}>{children}</Suspense>
    </Shell>
  );
}
