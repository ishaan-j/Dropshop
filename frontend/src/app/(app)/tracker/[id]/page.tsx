import { Suspense } from "react";
import type { Metadata } from "next";
import { ProductDetailView } from "@/components/tracker/product-detail";

export const metadata: Metadata = { title: "Purchase" };

export default function PurchasePage({ params }: { params: Promise<{ id: string }> }) {
  return (
    <Suspense fallback={<div className="h-96 rounded-xl border border-[#E4E7DC] bg-white" />}>
      <PurchaseRoute params={params} />
    </Suspense>
  );
}

async function PurchaseRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ProductDetailView id={id} />;
}
