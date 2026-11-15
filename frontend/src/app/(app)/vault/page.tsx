import type { Metadata } from "next";
import { VaultView } from "@/components/vault/vault-view";

export const metadata: Metadata = { title: "Savings vault" };

export default function VaultPage() {
  return <VaultView />;
}
