"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";
import {
  Activity,
  BadgePercent,
  Bot,
  Landmark,
  LayoutDashboard,
  Settings,
  ShoppingBag,
} from "lucide-react";

const LINKS = [
  { href: "/app", label: "Overview", icon: LayoutDashboard },
  { href: "/app/purchases", label: "Purchases", icon: ShoppingBag },
  { href: "/app/opportunities", label: "Opportunities", icon: BadgePercent },
  { href: "/app/agents", label: "Agents", icon: Bot },
  { href: "/app/activity", label: "Activity", icon: Activity },
  { href: "/app/vault", label: "Vault", icon: Landmark },
  { href: "/app/settings", label: "Settings", icon: Settings },
];

export function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link href="/" className="brand">
          DropShop
        </Link>
        <Suspense fallback={<nav className="nav" aria-hidden="true" />}>
          <SideNav />
        </Suspense>
        <p className="muted" style={{ color: "#b7ad9f", fontSize: 13, marginTop: "auto" }}>
          Purchase, monitor, detect, verify, claim, recover, save.
        </p>
      </aside>
      <div className="main">{children}</div>
    </div>
  );
}

function SideNav() {
  const path = usePathname();
  return (
    <nav className="nav">
      {LINKS.map((link) => {
        const active = link.href === "/app" ? path === "/app" : path.startsWith(link.href);
        const Icon = link.icon;
        return (
          <Link key={link.href} href={link.href} data-active={active}>
            <Icon size={16} />
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
