"use client";

import { useEffect, useState } from "react";
import { api, BudgetStatus } from "@/lib/api";
import { CostChart } from "@/components/CostChart";
import { StatsCards } from "@/components/StatsCards";

export default function OverviewPage() {
  const [budgets, setBudgets] = useState<BudgetStatus[]>([]);
  const [topModels, setTopModels] = useState<
    { model: string; request_count: number; total_cost: number }[]
  >([]);
  const [health, setHealth] = useState<string>("checking...");
  const [error, setError] = useState<string>("");

  useEffect(() => {
    Promise.all([
      api.getBudgetStatus().then((d) => setBudgets(d.teams)),
      api.getTopModels(5).then((d) => setTopModels(d.models)),
      api
        .getHealth()
        .then(() => setHealth("healthy"))
        .catch(() => setHealth("unreachable")),
    ]).catch((e) => setError(e.message));
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold">Overview</h1>
        <span
          className={`text-xs px-2 py-1 rounded-full ${
            health === "healthy"
              ? "bg-green-900/50 text-green-400"
              : "bg-red-900/50 text-red-400"
          }`}
        >
          Gateway: {health}
        </span>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-700 text-red-300 p-3 rounded-md mb-6 text-sm">
          {error}
        </div>
      )}

      <StatsCards budgets={budgets} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-8">
        {/* Budget utilization */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">
            Budget Utilization
          </h2>
          {budgets.map((b) => (
            <div key={b.team_id} className="mb-4">
              <div className="flex justify-between text-sm mb-1">
                <span>{b.team_name}</span>
                <span className="text-gray-400">
                  ${b.spent.toFixed(2)} / ${b.budget.toFixed(2)}
                </span>
              </div>
              <div className="w-full bg-gray-800 rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all ${
                    b.utilization_pct > 80
                      ? "bg-red-500"
                      : b.utilization_pct > 50
                        ? "bg-yellow-500"
                        : "bg-blue-500"
                  }`}
                  style={{ width: `${Math.min(100, b.utilization_pct)}%` }}
                />
              </div>
            </div>
          ))}
          {budgets.length === 0 && (
            <p className="text-gray-500 text-sm">No teams configured</p>
          )}
        </div>

        {/* Top models */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">
            Top Models by Usage
          </h2>
          <div className="space-y-3">
            {topModels.map((m, i) => (
              <div
                key={m.model}
                className="flex items-center justify-between text-sm"
              >
                <div className="flex items-center gap-2">
                  <span className="text-gray-500 w-4">{i + 1}.</span>
                  <span className="font-mono">{m.model}</span>
                </div>
                <div className="flex gap-4 text-gray-400">
                  <span>{m.request_count.toLocaleString()} reqs</span>
                  <span>${m.total_cost.toFixed(4)}</span>
                </div>
              </div>
            ))}
            {topModels.length === 0 && (
              <p className="text-gray-500 text-sm">No usage data yet</p>
            )}
          </div>
        </div>
      </div>

      <div className="mt-8">
        <CostChart />
      </div>
    </div>
  );
}
