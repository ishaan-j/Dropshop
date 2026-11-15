"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { Toaster, toast } from "sonner";
import { DemoProvider, useDemo } from "@/components/demo/demo-provider";
import { config } from "@/lib/config";
import { hydrateFromBackend, startBackendSync } from "@/lib/services";
import { useAppStore } from "@/store/app-store";

const HydrationContext = createContext(false);

export function useHydrated() {
  return useContext(HydrationContext);
}

/** Poll the backend unless NEXT_PUBLIC_DATA_MODE=demo. Paused while the guided demo runs, since it edits the local ledger. */
function BackendSync() {
  const hydrated = useHydrated();
  const { phase } = useDemo();
  useEffect(() => {
    if (!hydrated || config.dataMode === "demo" || phase !== "idle") return;
    return startBackendSync();
  }, [hydrated, phase]);
  return null;
}

export function Providers({ children }: { children: ReactNode }) {
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const finish = useAppStore.persist.onFinishHydration(() => setHydrated(true));
    void useAppStore.persist.rehydrate();
    return finish;
  }, []);

  useEffect(() => {
    if (!hydrated || config.dataMode === "demo") return;
    let cancel = false;
    hydrateFromBackend().catch(() => {
      // In auto mode a missing backend is normal: the app just runs on its demo ledger.
      if (!cancel && config.dataMode === "api") toast.error("Backend unavailable. Showing saved demo data.");
    });
    return () => {
      cancel = true;
    };
  }, [hydrated]);

  return (
    <HydrationContext.Provider value={hydrated}>
      <DemoProvider>
        <BackendSync />
        {children}
        <Toaster
          position="top-right"
          toastOptions={{ style: { background: "#fff", border: "1px solid #E4E7DC", color: "#17211C" } }}
        />
      </DemoProvider>
    </HydrationContext.Provider>
  );
}
