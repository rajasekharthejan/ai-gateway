"use client";

import { BudgetStatus } from "@/lib/api";

interface StatsCardsProps {
  budgets: BudgetStatus[];
}

export function StatsCards({ budgets }: StatsCardsProps) {
  const totalSpent = budgets.reduce((sum, b) => sum + b.spent, 0);
  const totalBudget = budgets.reduce((sum, b) => sum + b.budget, 0);
  const teamCount = budgets.length;
  const avgUtilization =
    budgets.length > 0
      ? budgets.reduce((sum, b) => sum + b.utilization_pct, 0) / budgets.length
      : 0;

  const cards = [
    {
      label: "Total Spend (MTD)",
      value: `$${totalSpent.toFixed(2)}`,
      sub: `of $${totalBudget.toFixed(2)} budget`,
    },
    {
      label: "Active Teams",
      value: teamCount.toString(),
      sub: "with API keys",
    },
    {
      label: "Avg Utilization",
      value: `${avgUtilization.toFixed(1)}%`,
      sub: "across all teams",
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {cards.map((card) => (
        <div
          key={card.label}
          className="bg-gray-900 border border-gray-800 rounded-lg p-5"
        >
          <p className="text-xs text-gray-400 uppercase tracking-wide">
            {card.label}
          </p>
          <p className="text-2xl font-bold mt-1">{card.value}</p>
          <p className="text-xs text-gray-500 mt-1">{card.sub}</p>
        </div>
      ))}
    </div>
  );
}
