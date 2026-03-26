"use client";

import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { api, UsageSummary } from "@/lib/api";

export function CostChart() {
  const [data, setData] = useState<
    { date: string; cost: number; requests: number; tokens: number }[]
  >([]);

  useEffect(() => {
    api
      .getUsage()
      .then((usage) => {
        // Aggregate by date
        const byDate = new Map<
          string,
          { cost: number; requests: number; tokens: number }
        >();
        for (const u of usage) {
          const existing = byDate.get(u.date) || {
            cost: 0,
            requests: 0,
            tokens: 0,
          };
          existing.cost += u.total_cost_usd;
          existing.requests += u.total_requests;
          existing.tokens += u.total_tokens;
          byDate.set(u.date, existing);
        }
        const chartData = Array.from(byDate.entries())
          .map(([date, vals]) => ({ date, ...vals }))
          .sort((a, b) => a.date.localeCompare(b.date))
          .slice(-30); // Last 30 days
        setData(chartData);
      })
      .catch(() => {});
  }, []);

  if (data.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">
          Daily Cost Trend
        </h2>
        <p className="text-gray-500 text-sm">
          No usage data available. Start sending requests to see cost trends.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">
        Daily Cost Trend (Last 30 Days)
      </h2>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="date"
            stroke="#6B7280"
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => v.slice(5)} // MM-DD
          />
          <YAxis
            stroke="#6B7280"
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => `$${v.toFixed(2)}`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1F2937",
              border: "1px solid #374151",
              borderRadius: "6px",
            }}
            labelStyle={{ color: "#D1D5DB" }}
            formatter={(value: number, name: string) => {
              if (name === "cost") return [`$${value.toFixed(4)}`, "Cost"];
              if (name === "requests")
                return [value.toLocaleString(), "Requests"];
              return [value.toLocaleString(), name];
            }}
          />
          <Legend />
          <Bar dataKey="cost" fill="#3B82F6" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
