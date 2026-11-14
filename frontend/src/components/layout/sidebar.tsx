"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bot, Landmark, LayoutDashboard, LineChart, Receipt, Settings, X } from "lucide-react";
import { Logo } from "@/components/logo";
import { useAppStore } from "@/store/app-store";
import { useBackend } from "@/lib/live";
import { cn, initials } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/tracker", label: "Price Tracker", icon: LineChart },
  { href: "/claims", label: "Claims", icon: Receipt },
  { href: "/vault", label: "Savings Vault", icon: Landmark },
  { href: "/activity", label: "AI Activity", icon: Bot },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname();
  const user = useAppStore((state) => state.user);
  const backend = useBackend();
  return (
    <>
      {open ? (
        <button type="button" className="fixed inset-0 z-30 bg-[#17211C]/40 lg:hidden" aria-label="Close menu" onClick={onClose} />
      ) : null}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-72 flex-col bg-[#12372A] text-white transition-transform lg:w-60 lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
        aria-label="Primary"
      >
        <div className="flex items-center justify-between border-b border-white/10 px-4 py-4">
          <Link href="/dashboard" onClick={onClose} aria-label="DropShop overview">
            <Logo inverted />
          </Link>
          <button type="button" className="rounded-md p-1 text-white/80 hover:bg-white/10 lg:hidden" onClick={onClose} aria-label="Close menu">
            <X className="h-5 w-5" />
          </button>
        </div>
        <p className="mx-4 mt-4 rounded-full bg-white/10 px-3 py-1 text-center text-[11px] font-medium tracking-wide text-[#C8F55A]">
          {backend ? "Live backend" : "Demo data"}
        </p>
        <nav className="mt-4 flex-1 space-y-1 px-3">
          {NAV.map((item) => {
            const active = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onClose}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium",
                  active ? "bg-white/10 text-white" : "text-white/70 hover:bg-white/5 hover:text-white",
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <Link href="/settings" onClick={onClose} className="m-3 flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-white/5">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#C8F55A] text-sm font-semibold text-[#12372A]">
            {initials(user.name)}
          </span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium">{user.name}</span>
            <span className="block truncate text-xs text-white/60">{user.email}</span>
          </span>
        </Link>
      </aside>
    </>
  );
}
