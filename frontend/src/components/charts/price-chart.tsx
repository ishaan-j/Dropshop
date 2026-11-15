"use client";

import { Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PricePoint } from "@/types";
import { formatCents, formatDate } from "@/lib/utils";

export function PriceChart({ points, paidCents }: { points: PricePoint[]; paidCents: number }) {
  const data = points.map((point) => ({
    label: new Date(point.time).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
    iso: point.time,
    price: point.price_cents,
  }));
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 12, right: 8, left: 0, bottom: 0 }}>
          <XAxis dataKey="label" tick={{ fontSize: 12, fill: "#5E6B63" }} axisLine={false} tickLine={false} minTickGap={24} />
          <YAxis
            tickFormatter={(value: number) => `$${Math.round(value / 100)}`}
            tick={{ fontSize: 12, fill: "#5E6B63" }}
            axisLine={false}
            tickLine={false}
            width={48}
            domain={["dataMin - 500", "dataMax + 500"]}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const point = payload[0]?.payload as { iso: string } | undefined;
              const value = typeof payload[0]?.value === "number" ? payload[0].value : 0;
              return (
                <div className="rounded-lg border border-[#E4E7DC] bg-white px-3 py-2 text-sm shadow-md">
                  <p className="text-xs text-[#5E6B63]">{point ? formatDate(point.iso) : ""}</p>
                  <p className="font-semibold tabular-nums text-[#12372A]">{formatCents(value)}</p>
                </div>
              );
            }}
          />
          <ReferenceLine
            y={paidCents}
            stroke="#12372A"
            strokeDasharray="4 4"
            label={{ value: "Paid", position: "insideTopRight", fill: "#5E6B63", fontSize: 11 }}
          />
          <Line type="monotone" dataKey="price" stroke="#12372A" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
