"use client";

import { Check, Pause, Play, RotateCcw, Shrink } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useDemo } from "@/components/demo/demo-provider";
import { StageVisual } from "@/components/demo/demo-stages";
import { DEMO_STAGES, demoHeadline } from "@/components/demo/script";
import { cn } from "@/lib/utils";

export function DemoOverlay() {
  const demo = useDemo();
  const headline = demoHeadline(demo.stage, demo.stageProgress, demo.phase);
  const showDock = !demo.open && !demo.dockHidden && demo.phase !== "idle";

  return (
    <>
      <Dialog open={demo.open} onOpenChange={(next) => { if (!next) demo.minimize(); }}>
        <DialogContent full hideClose className="bg-[#F7F8F2]" aria-describedby="demo-note">
          <div className="flex items-center justify-between border-b border-[#E4E7DC] px-4 py-3 sm:px-6">
            <div>
              <DialogTitle>Live demo</DialogTitle>
              <DialogDescription id="demo-note" className="mt-0.5">
                Simulated. Nothing is sent to a retailer, bank, or blockchain.
              </DialogDescription>
            </div>
            <Button variant="outline" size="sm" onClick={demo.minimize}>
              <Shrink className="h-4 w-4" />
              Minimize
            </Button>
          </div>
          <div className="grid min-h-0 flex-1 lg:grid-cols-[280px_1fr]">
            <ol className="flex gap-2 overflow-x-auto border-b border-[#E4E7DC] bg-[#12372A] p-3 text-white lg:flex-col lg:gap-1 lg:overflow-visible lg:border-b-0 lg:border-r lg:p-4">
              {DEMO_STAGES.map((item) => {
                const done = demo.committed >= item.id;
                const active = demo.stage === item.id && demo.phase !== "complete";
                return (
                  <li key={item.id} className={cn("min-w-40 rounded-lg px-3 py-2 lg:min-w-0", active ? "bg-white/10" : "")}>
                    <div className="flex items-center gap-2">
                      <span className={cn("flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold", done ? "bg-[#C8F55A] text-[#12372A]" : "bg-white/10 text-white")}>
                        {done ? <Check className="h-3.5 w-3.5" /> : item.id}
                      </span>
                      <span className="text-sm font-medium">{item.agent}</span>
                    </div>
                    <p className="mt-1 pl-8 text-xs text-white/60">{item.title}</p>
                  </li>
                );
              })}
            </ol>
            <div className="min-h-0 overflow-y-auto px-4 py-6 sm:px-8">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-[#5E6B63]" aria-live="polite">
                {headline}
              </p>
              <div className="mt-4">
                <StageVisual stage={demo.stage} progress={demo.stageProgress} phase={demo.phase} />
              </div>
            </div>
          </div>
          <footer className="border-t border-[#E4E7DC] px-4 py-3 sm:px-6">
            <div className="mb-3 h-1.5 overflow-hidden rounded-full bg-[#E4E7DC]">
              <div className="h-full rounded-full bg-[#12372A]" style={{ width: `${Math.round(demo.overall * 100)}%` }} />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {demo.phase === "running" ? (
                <Button variant="outline" onClick={demo.pause}><Pause className="h-4 w-4" /> Pause</Button>
              ) : (
                <Button onClick={demo.phase === "paused" ? demo.resume : demo.replay}>
                  <Play className="h-4 w-4" /> {demo.phase === "paused" ? "Resume" : demo.phase === "idle" ? "Start" : "Replay"}
                </Button>
              )}
              <Button variant="outline" onClick={demo.replay}><RotateCcw className="h-4 w-4" /> Replay</Button>
              <Button variant="ghost" onClick={demo.reset}>Reset</Button>
              <p className="ml-auto text-xs text-[#5E6B63]">Minimize to watch the dashboard update.</p>
            </div>
          </footer>
        </DialogContent>
      </Dialog>
      {showDock ? (
        <div className="fixed bottom-4 right-4 z-40 w-[min(100%-2rem,22rem)] rounded-xl border border-[#E4E7DC] bg-white p-4 shadow-xl">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-[#5E6B63]">Live demo · simulated</p>
          <p className="mt-1 font-semibold text-[#12372A]">
            {demo.phase === "complete" ? "Success — $40 recovered" : DEMO_STAGES.find((item) => item.id === demo.stage)?.title}
          </p>
          <div className="mt-3 flex gap-2">
            <Button size="sm" onClick={() => demo.openDemo()}>Expand</Button>
            {demo.phase === "running" ? <Button size="sm" variant="outline" onClick={demo.pause}>Pause</Button> : null}
            {demo.phase === "paused" ? <Button size="sm" variant="outline" onClick={demo.resume}>Resume</Button> : null}
            <Button size="sm" variant="ghost" onClick={demo.dismissDock}>Hide</Button>
          </div>
        </div>
      ) : null}
    </>
  );
}
