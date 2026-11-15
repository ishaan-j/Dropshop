import type { Metadata } from "next";
import { LandingPage } from "@/components/landing/landing-page";

export const metadata: Metadata = {
  title: "You shop. Prices drop. You save.",
  description: "Get money back automatically when prices drop on things you’ve already bought.",
};

export default function HomePage() {
  return <LandingPage />;
}
