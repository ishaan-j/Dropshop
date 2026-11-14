import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Money is integer cents everywhere. */
export function formatCents(cents: number) {
  return (cents / 100).toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function formatRelative(iso: string, now = Date.now()) {
  const diff = now - new Date(iso).getTime();
  const min = Math.round(diff / 60000);
  if (Math.abs(min) < 1) return "Just now";
  if (min < 0) return formatDate(iso);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.round(hr / 24);
  if (day < 45) return `${day}d ago`;
  return formatDate(iso);
}

export function shiftDays(days: number, hour = 12) {
  const d = new Date();
  d.setSeconds(0, 0);
  d.setMinutes(0);
  d.setHours(hour, 0, 0);
  d.setDate(d.getDate() + days);
  return d.toISOString();
}

export function shiftHours(hours: number) {
  const d = new Date();
  d.setSeconds(0, 0);
  d.setMinutes(0);
  d.setTime(d.getTime() + hours * 60 * 60 * 1000);
  return d.toISOString();
}

export function daysUntil(iso: string | null, now = new Date()) {
  if (!iso) return null;
  const end = new Date(iso);
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  end.setHours(0, 0, 0, 0);
  return Math.round((end.getTime() - start.getTime()) / 86_400_000);
}

export function priceGap(paid: number, current: number | null) {
  return Math.max(0, paid - (current ?? paid));
}

export function dropPercent(paid: number, current: number | null) {
  const gap = priceGap(paid, current);
  if (paid <= 0 || gap <= 0) return 0;
  return Math.round((gap / paid) * 100);
}

export function shorten(value: string, lead = 4, tail = 4) {
  if (value.length <= lead + tail + 1) return value;
  return `${value.slice(0, lead)}…${value.slice(-tail)}`;
}

export function firstName(name: string) {
  return name.trim().split(/\s+/)[0] || "there";
}

export function initials(name: string) {
  const parts = name.trim().split(/\s+/).slice(0, 2);
  const letters = parts.map((part) => part[0]?.toUpperCase() ?? "").join("");
  return letters || "DS";
}

export function startOfDay(date: Date) {
  const next = new Date(date);
  next.setHours(0, 0, 0, 0);
  return next;
}

export function addDays(date: Date, days: number) {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}
