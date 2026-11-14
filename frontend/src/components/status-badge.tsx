import type { DisplayStatus } from "@/lib/metrics";
import { cn } from "@/lib/utils";

const STYLES: Record<DisplayStatus, { label: string; className: string }> = {
  eligible: { label: "Eligible", className: "bg-[#E7F6EC] text-[#146C3A]" },
  completed: { label: "Completed", className: "bg-[#E7F6EC] text-[#146C3A]" },
  pending: { label: "Pending", className: "bg-[#FFF4D6] text-[#8A5A00]" },
  processing: { label: "Processing", className: "bg-[#E7F1FB] text-[#1D4E89]" },
  submitted: { label: "Submitted", className: "bg-[#E7F1FB] text-[#1D4E89]" },
  monitoring: { label: "Monitoring", className: "bg-[#EEF1EA] text-[#4E5B54]" },
  ineligible: { label: "Ineligible", className: "bg-[#FDECEC] text-[#9B2C2C]" },
  expired: { label: "Expired", className: "bg-[#FDECEC] text-[#9B2C2C]" },
};

export function StatusBadge({ status, className }: { status: DisplayStatus; className?: string }) {
  const style = STYLES[status];
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", style.className, className)}>
      {style.label}
    </span>
  );
}

export function statusLabel(status: DisplayStatus) {
  return STYLES[status].label;
}
