import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {eyebrow ? <p className="text-xs font-medium uppercase tracking-[0.14em] text-[#5E6B63]">{eyebrow}</p> : null}
        <h1 className="mt-1 text-2xl font-semibold tracking-tight text-[#12372A] sm:text-3xl">{title}</h1>
        {description ? <p className="mt-2 max-w-2xl text-sm leading-6 text-[#5E6B63]">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function Panel({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <section className={`rounded-xl border border-[#E4E7DC] bg-white p-5 shadow-[0_1px_2px_rgba(18,55,42,0.04)] ${className ?? ""}`}>
      {children}
    </section>
  );
}

export function DemoNote({ children }: { children?: ReactNode }) {
  return (
    <p className="rounded-lg bg-[#F4F6EE] px-3 py-2 text-xs leading-5 text-[#3E4C45]">
      {children ?? "Simulated for the hackathon demo. DropShop does not contact retailers, banks, or a blockchain."}
    </p>
  );
}
