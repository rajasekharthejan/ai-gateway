"use client";

import { useEffect, useState } from "react";
import { api, CostBreakdown } from "@/lib/api";

export default function UsagePage() {
  const [costs, setCosts] = useState<CostBreakdown[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getCosts()
      .then((d) => setCosts(d.costs))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Usage & Costs</h1>

      <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800">
              <th className="text-left p-4 text-gray-400 font-medium">Team</th>
              <th className="text-left p-4 text-gray-400 font-medium">Model</th>
              <th className="text-right p-4 text-gray-400 font-medium">
                Requests
              </th>
              <th className="text-right p-4 text-gray-400 font-medium">
                Tokens
              </th>
              <th className="text-right p-4 text-gray-400 font-medium">
                Cost (USD)
              </th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={5} className="p-4 text-center text-gray-500">
                  Loading...
                </td>
              </tr>
            )}
            {!loading && costs.length === 0 && (
              <tr>
                <td colSpan={5} className="p-4 text-center text-gray-500">
                  No usage data yet
                </td>
              </tr>
            )}
            {costs.map((c, i) => (
              <tr
                key={i}
                className="border-b border-gray-800/50 hover:bg-gray-800/30"
              >
                <td className="p-4">{c.team_name}</td>
                <td className="p-4 font-mono text-blue-400">{c.model}</td>
                <td className="p-4 text-right">
                  {c.total_requests.toLocaleString()}
                </td>
                <td className="p-4 text-right">
                  {c.total_tokens.toLocaleString()}
                </td>
                <td className="p-4 text-right font-mono">
                  ${c.total_cost_usd.toFixed(4)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
