/**
 * demo: the UI runs from the local ledger. No API keys, backend, or network.
 * api: hydrate from NEXT_PUBLIC_API_URL using the contract in docs/api-contract.md.
 */
export const config = {
  apiUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  dataMode: process.env.NEXT_PUBLIC_DATA_MODE === "api" ? "api" : "demo",
} as const;
