"use client";

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { toast } from "sonner";
import { DemoOverlay } from "@/components/demo/demo-overlay";
import { COMMIT_AT, DEMO_TOTAL, STAGE_TOASTS, demoPosition } from "@/components/demo/script";
import type { DemoStage } from "@/lib/demo-reducer";
import { useAppStore } from "@/store/app-store";

export type DemoPhase = "idle" | "running" | "paused" | "complete";

export interface DemoController {
  open: boolean;
  phase: DemoPhase;
  stage: number;
  stageProgress: number;
  overall: number;
  committed: number;
  dockHidden: boolean;
  openDemo: () => void;
  pause: () => void;
  resume: () => void;
  replay: () => void;
  reset: () => void;
  minimize: () => void;
  dismissDock: () => void;
  halt: () => void;
}

const DemoContext = createContext<DemoController | null>(null);

export function useDemo() {
  const value = useContext(DemoContext);
  if (!value) throw new Error("useDemo must be used within DemoProvider");
  return value;
}

export function DemoProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [phase, setPhase] = useState<DemoPhase>("idle");
  const [stage, setStage] = useState(0);
  const [stageProgress, setStageProgress] = useState(0);
  const [overall, setOverall] = useState(0);
  const [committed, setCommitted] = useState(0);
  const [dockHidden, setDockHidden] = useState(true);
  const elapsedRef = useRef(0);
  const committedRef = useRef(0);
  const phaseRef = useRef<DemoPhase>("idle");
  const timer = useRef<number | null>(null);
  const tick = useRef<() => void>(() => {});
  const epoch = useAppStore((state) => state.epoch);
  const seenEpoch = useRef(epoch);

  const stop = () => {
    if (timer.current != null) window.clearTimeout(timer.current);
    timer.current = null;
  };

  useEffect(() => {
    tick.current = () => {
    if (phaseRef.current !== "running") return;
    elapsedRef.current += 100;
    const position = demoPosition(elapsedRef.current);
    if (position.stage > committedRef.current && position.progress >= COMMIT_AT) {
      committedRef.current = position.stage;
      setCommitted(position.stage);
      useAppStore.getState().applyDemoStage(position.stage as DemoStage);
      if (useAppStore.getState().settings.refundNotifications) {
        toast.success(STAGE_TOASTS[position.stage] ?? "Demo updated");
      }
    }
    if (elapsedRef.current >= DEMO_TOTAL) {
      phaseRef.current = "complete";
      setPhase("complete");
      setStage(6);
      setStageProgress(1);
      setOverall(1);
      return;
    }
    setStage(position.stage);
    setStageProgress(position.progress);
    setOverall(elapsedRef.current / DEMO_TOTAL);
      timer.current = window.setTimeout(() => tick.current(), 100);
    };
  }, []);

  const replay = () => {
    stop();
    useAppStore.getState().resetDemoRun();
    committedRef.current = 0;
    elapsedRef.current = 0;
    setCommitted(0);
    setStage(1);
    setStageProgress(0);
    setOverall(0);
    phaseRef.current = "running";
    setPhase("running");
    setOpen(true);
    setDockHidden(false);
    timer.current = window.setTimeout(() => tick.current(), 100);
  };

  const pause = () => {
    if (phaseRef.current !== "running") return;
    stop();
    phaseRef.current = "paused";
    setPhase("paused");
  };

  const resume = () => {
    if (phaseRef.current !== "paused") return;
    phaseRef.current = "running";
    setPhase("running");
    timer.current = window.setTimeout(() => tick.current(), 100);
  };

  const reset = () => {
    stop();
    useAppStore.getState().resetDemoRun();
    committedRef.current = 0;
    elapsedRef.current = 0;
    setCommitted(0);
    setStage(0);
    setStageProgress(0);
    setOverall(0);
    phaseRef.current = "idle";
    setPhase("idle");
    setOpen(true);
    setDockHidden(false);
  };

  const halt = () => {
    stop();
    phaseRef.current = "idle";
    committedRef.current = 0;
    elapsedRef.current = 0;
    setPhase("idle");
    setCommitted(0);
    setStage(0);
    setStageProgress(0);
    setOverall(0);
    setOpen(false);
    setDockHidden(true);
  };

  const value: DemoController = {
    open,
    phase,
    stage,
    stageProgress,
    overall,
    committed,
    dockHidden,
    openDemo: () => {
      setDockHidden(false);
      if (phaseRef.current === "running" || phaseRef.current === "paused") {
        setOpen(true);
        return;
      }
      replay();
    },
    pause,
    resume,
    replay,
    reset,
    minimize: () => setOpen(false),
    dismissDock: () => setDockHidden(true),
    halt,
  };

  useEffect(() => {
    if (seenEpoch.current === epoch) return;
    seenEpoch.current = epoch;
    stop();
    phaseRef.current = "idle";
    committedRef.current = 0;
    elapsedRef.current = 0;
    setPhase("idle");
    setCommitted(0);
    setStage(0);
    setStageProgress(0);
    setOverall(0);
    setOpen(false);
    setDockHidden(true);
  }, [epoch]);

  useEffect(() => () => stop(), []);

  return (
    <DemoContext.Provider value={value}>
      {children}
      <DemoOverlay />
    </DemoContext.Provider>
  );
}
