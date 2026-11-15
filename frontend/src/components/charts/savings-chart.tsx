"use client";

import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { SavingsPoint, SavingsRange } from "@/lib/metrics";
import { formatCents, formatDate } from "@/lib/utils";

export function SavingsChart({
  data,
  range,
  onRange,
}: {
  data: SavingsPoint[];
  range: SavingsRange;
  onRange: (range: SavingsRange) => void;
}) {
  return (
    <div>
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-[#12372A]">Savings over time</h2>
          <p className="text-sm text-[#5E6B63]">Cumulative money deposited in the vault.</p>
        </div>
        <div className="flex rounded-lg border border-[#E4E7DC] p-1" role="group" aria-label="Chart range">
          {(["7d", "30d", "all"] as const).map((item) => (
            <button
              key={item}
              type="button"
              aria-pressed={range === item}
              onClick={() => onRange(item)}
              className={`rounded-md px-2.5 py-1 text-xs font-semibold ${range === item ? "bg-[#12372A] text-white" : "text-[#5E6B63] hover:text-[#17211C]"}`}
            >
              {item === "all" ? "All" : item.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="vaultFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#C8F55A" stopOpacity={0.85} />
                <stop offset="100%" stopColor="#C8F55A" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <XAxis dataKey="label" tick={{ fontSize: 12, fill: "#5E6B63" }} axisLine={false} tickLine={false} minTickGap={28} />
            <YAxis
              tickFormatter={(value: number) => `$${Math.round(value / 100)}`}
              tick={{ fontSize: 12, fill: "#5E6B63" }}
              axisLine={false}
              tickLine={false}
              width={48}
            />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const point = payload[0]?.payload as SavingsPoint | undefined;
                const value = typeof payload[0]?.value === "number" ? payload[0].value : 0;
                return (
                  <div className="rounded-lg border border-[#E4E7DC] bg-white px-3 py-2 text-sm shadow-md">
                    <p className="text-xs text-[#5E6B63]">{point ? formatDate(point.iso) : ""}</p>
                    <p className="font-semibold tabular-nums text-[#12372A]">{formatCents(value)}</p>
                  </div>
                );
              }}
            />
            <Area type="monotone" dataKey="balance" stroke="#12372A" strokeWidth={2} fill="url(#vaultFill)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
