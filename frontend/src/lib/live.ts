/**
 * What the screens say about where their data comes from.
 *
 * `useBackend()` is null while the app runs on its local demo ledger, and the backend's
 * GET /health report once it's connected. The backend can itself be simulating some systems
 * (the bank, the vault), so the copy here names what is real and what isn't.
 */
import type { BackendStatus } from "../types";
import { useAppStore } from "../store/app-store";

export function useBackend() {
  return useAppStore((state) => state.backend);
}

/** The bank is Nessie and nothing is being covered by the simulator. */
export function bankIsReal(status: BackendStatus) {
  return status.bank === "nessie";
}

/** Vault records are going to Solana devnet right now (not the simulated fallback). */
export function vaultIsReal(status: BackendStatus) {
  return status.vault === "solana";
}

/** A simulated vault signature (the demo ledger's, or the backend's `sim-` fallback). */
export function isSimulatedSignature(signature: string) {
  return signature.startsWith("sim") || signature === "pending-signature";
}

export function explorerUrl(signature: string) {
  return `https://explorer.solana.com/tx/${signature}?cluster=devnet`;
}

/** One line for the note under a claim or a balance. */
export function liveNote(status: BackendStatus) {
  const bank =
    status.bank === "nessie"
      ? "the Capital One Nessie sandbox"
      : status.bank === "nessie+simulated"
        ? "the Capital One Nessie sandbox (a simulated bank covers when it's down)"
        : "a simulated bank";
  const vault =
    status.vault === "solana"
      ? "Solana devnet"
      : status.vault === "solana+simulated"
        ? "a simulated vault for now, because Solana devnet can't be used"
        : "a simulated vault";
  return `Live backend. The claim bot files on DropShop's demo store, not a real retailer. Refunds post to ${bank} and are recorded in ${vault}.`;
}
