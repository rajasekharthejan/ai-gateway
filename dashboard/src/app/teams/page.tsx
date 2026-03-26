"use client";

import { useEffect, useState } from "react";
import { api, Team } from "@/lib/api";

export default function TeamsPage() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getTeams()
      .then(setTeams)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Teams</h1>

      <div className="grid gap-4">
        {loading && <p className="text-gray-500">Loading teams...</p>}
        {!loading && teams.length === 0 && (
          <p className="text-gray-500">
            No teams configured. Use the Admin API to create teams.
          </p>
        )}
        {teams.map((team) => (
          <div
            key={team.id}
            className="bg-gray-900 border border-gray-800 rounded-lg p-5"
          >
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold text-lg">{team.name}</h3>
              <span
                className={`text-xs px-2 py-0.5 rounded-full ${
                  team.is_active
                    ? "bg-green-900/50 text-green-400"
                    : "bg-gray-800 text-gray-500"
                }`}
              >
                {team.is_active ? "Active" : "Inactive"}
              </span>
            </div>
            {team.description && (
              <p className="text-sm text-gray-400 mb-3">{team.description}</p>
            )}
            <div className="flex gap-6 text-xs text-gray-500">
              <span>
                Budget:{" "}
                <span className="text-gray-300">
                  {(team.token_budget_monthly / 1_000_000).toFixed(1)}M
                  tokens/mo
                </span>
              </span>
              <span>
                Rate Limit:{" "}
                <span className="text-gray-300">
                  {team.rate_limit_rpm} RPM
                </span>
              </span>
              <span>
                Created:{" "}
                <span className="text-gray-300">
                  {new Date(team.created_at).toLocaleDateString()}
                </span>
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
