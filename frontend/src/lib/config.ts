/**
 * NEXT_PUBLIC_DATA_MODE:
 *   auto (default): use the backend when it answers GET /health, otherwise the local demo ledger.
 *   api:  same, but say so if the backend can't be reached.
 *   demo: never call the backend. The UI runs from the local ledger: no API keys or network.
 * The contract with the backend is docs/api-contract.md.
 */
const mode = process.env.NEXT_PUBLIC_DATA_MODE;

export const config = {
  apiUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  dataMode: mode === "api" || mode === "demo" ? mode : "auto",
} as const;
