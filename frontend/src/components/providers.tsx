"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { Toaster, toast } from "sonner";
import { DemoProvider } from "@/components/demo/demo-provider";
import { config } from "@/lib/config";
import { hydrateFromBackend } from "@/lib/services";
import { useAppStore } from "@/store/app-store";

const HydrationContext = createContext(false);

export function useHydrated() {
  return useContext(HydrationContext);
}

export function Providers({ children }: { children: ReactNode }) {
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const finish = useAppStore.persist.onFinishHydration(() => setHydrated(true));
    void useAppStore.persist.rehydrate();
    return finish;
  }, []);

  useEffect(() => {
    if (!hydrated || config.dataMode !== "api") return;
    let cancel = false;
    hydrateFromBackend().catch(() => {
      if (!cancel) toast.error("Backend unavailable. Showing saved demo data.");
    });
    return () => {
      cancel = true;
    };
  }, [hydrated]);

  return (
    <HydrationContext.Provider value={hydrated}>
      <DemoProvider>
        {children}
        <Toaster
          position="top-right"
          toastOptions={{ style: { background: "#fff", border: "1px solid #E4E7DC", color: "#17211C" } }}
        />
      </DemoProvider>
    </HydrationContext.Provider>
  );
}
