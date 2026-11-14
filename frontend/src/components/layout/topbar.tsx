"use client";

import Link from "next/link";
import * as Menu from "@radix-ui/react-dropdown-menu";
import { Bell, Menu as MenuIcon, Play } from "lucide-react";
import { Logo } from "@/components/logo";
import { useDemo } from "@/components/demo/demo-provider";
import { useAppStore } from "@/store/app-store";
import { formatRelative, initials } from "@/lib/utils";

export function Topbar({ onMenu, menuOpen }: { onMenu: () => void; menuOpen: boolean }) {
  const demo = useDemo();
  const user = useAppStore((state) => state.user);
  const activity = useAppStore((state) => state.activity);
  const read = useAppStore((state) => state.readNotificationIds);
  const notificationsOn = useAppStore((state) => state.settings.refundNotifications);
  const markRead = useAppStore((state) => state.markNotificationsRead);
  const unread = activity.filter((item) => !read.includes(item.id)).length;
  const recent = [...activity].sort((a, b) => b.time.localeCompare(a.time)).slice(0, 6);
  const label =
    demo.phase === "running" ? "Demo running" : demo.phase === "paused" ? "Demo paused" : demo.phase === "complete" ? "Replay demo" : "Run Live Demo";

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-[#E4E7DC] bg-[#F7F8F2] px-4 sm:px-6">
      <button
        type="button"
        className="rounded-md p-2 hover:bg-[#EEF1E8] lg:hidden"
        aria-label="Open menu"
        aria-expanded={menuOpen}
        onClick={onMenu}
      >
        <MenuIcon className="h-5 w-5" />
      </button>
      <Link href="/dashboard" className="lg:hidden" aria-label="DropShop overview">
        <Logo />
      </Link>
      <div className="flex-1" />
      <Menu.Root>
        <Menu.Trigger asChild>
          <button type="button" className="relative rounded-md p-2 hover:bg-[#EEF1E8]" aria-label={`Notifications${unread && notificationsOn ? `, ${unread} unread` : ""}`}>
            <Bell className="h-5 w-5" />
            {notificationsOn && unread > 0 ? (
              <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#12372A] px-1 text-[10px] font-semibold text-[#C8F55A]">
                {unread > 9 ? "9+" : unread}
              </span>
            ) : null}
          </button>
        </Menu.Trigger>
        <Menu.Portal>
          <Menu.Content className="z-50 w-[min(100vw-2rem,22rem)] rounded-xl border border-[#E4E7DC] bg-white p-2 shadow-xl" align="end" sideOffset={8}>
            <div className="flex items-center justify-between px-2 py-1.5">
              <p className="text-sm font-semibold text-[#12372A]">Notifications</p>
              <button type="button" className="text-xs font-medium text-[#5E6B63] hover:text-[#17211C]" onClick={markRead}>
                Mark all read
              </button>
            </div>
            {recent.length === 0 ? <p className="px-2 py-6 text-sm text-[#5E6B63]">No activity yet.</p> : null}
            <ul>
              {recent.map((item) => (
                <li key={item.id} className="rounded-lg px-2 py-2 hover:bg-[#F7F8F2]">
                  <p className="text-sm leading-5 text-[#17211C]">{item.message}</p>
                  <p className="mt-1 text-xs text-[#5E6B63]">{formatRelative(item.time)}</p>
                </li>
              ))}
            </ul>
            <Menu.Item asChild>
              <Link href="/activity" className="mt-1 block rounded-lg px-2 py-2 text-sm font-medium text-[#12372A] outline-none hover:bg-[#F3F5EE]">
                View AI activity
              </Link>
            </Menu.Item>
          </Menu.Content>
        </Menu.Portal>
      </Menu.Root>
      <Link href="/settings" className="flex h-9 w-9 items-center justify-center rounded-full bg-[#12372A] text-xs font-semibold text-[#C8F55A]" aria-label="Account settings">
        {initials(user.name)}
      </Link>
      <button
        type="button"
        onClick={demo.openDemo}
        className="inline-flex h-10 items-center gap-2 rounded-lg bg-[#C8F55A] px-3 text-sm font-semibold text-[#12372A] hover:bg-[#d6f67c]"
      >
        <Play className="h-4 w-4" />
        <span className="hidden sm:inline">{label}</span>
        <span className="sm:hidden">Demo</span>
      </button>
    </header>
  );
}
