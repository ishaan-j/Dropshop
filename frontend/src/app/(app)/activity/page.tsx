import type { Metadata } from "next";
import { ActivityView } from "@/components/activity/activity-view";

export const metadata: Metadata = { title: "AI activity" };

export default function ActivityPage() {
  return <ActivityView />;
}
