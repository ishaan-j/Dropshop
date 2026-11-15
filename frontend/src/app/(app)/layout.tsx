import { Suspense, type ReactNode } from "react";
import { AppShell } from "@/components/layout/app-shell";

// The app's screens read the current time ("5m ago", days left in a window), which Next 16 won't
// prerender. Suspense defers them past the prerender, so the build only emits this empty shell.
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#F7F8F2]" aria-busy="true" />}>
      <AppShell>{children}</AppShell>
    </Suspense>
  );
}
