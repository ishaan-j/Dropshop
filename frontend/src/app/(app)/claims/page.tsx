import type { Metadata } from "next";
import { ClaimsView } from "@/components/claims/claims-view";

export const metadata: Metadata = { title: "Claims" };

export default function ClaimsPage() {
  return <ClaimsView />;
}
