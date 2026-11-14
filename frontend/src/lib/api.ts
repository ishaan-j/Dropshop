const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "dropshop_token";

export function apiUrl(path: string) {
  return `${API_URL}${path}`;
}

export async function ensureSession(): Promise<string> {
  const existing = sessionStorage.getItem(TOKEN_KEY);
  if (existing) return existing;
  const response = await fetch(apiUrl("/auth/session"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ display_name: "Local user" }),
  });
  if (!response.ok) throw new Error("Could not start a session.");
  const body = (await response.json()) as { token: string };
  sessionStorage.setItem(TOKEN_KEY, body.token);
  return body.token;
}

export async function api<T>(path: string, init?: RequestInit, retried = false): Promise<T> {
  const token = await ensureSession();
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (response.status === 401 && !retried) {
    sessionStorage.removeItem(TOKEN_KEY);
    return api<T>(path, init, true);
  }
  if (!response.ok) {
    let detail = `${response.status}`;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : detail;
    } catch {
      detail = response.statusText || detail;
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export async function openAuthorized(path: string) {
  const token = await ensureSession();
  const response = await fetch(apiUrl(path), { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) throw new Error("Could not open that file.");
  const blob = await response.blob();
  window.open(URL.createObjectURL(blob), "_blank", "noopener");
}

export const money = (cents: number | null | undefined) => {
  if (cents == null) return "—";
  return (cents / 100).toLocaleString("en-US", { style: "currency", currency: "USD" });
};

export const when = (iso: string | null | undefined) => {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
};
