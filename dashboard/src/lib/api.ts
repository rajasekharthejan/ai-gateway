const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface FetchOptions {
  method?: string;
  body?: unknown;
}

async function apiFetch<T>(path: string, opts: FetchOptions = {}): Promise<T> {
  const adminKey = typeof window !== "undefined"
    ? localStorage.getItem("admin-key") || ""
    : "";

  const res = await fetch(`${API_BASE}${path}`, {
    method: opts.method || "GET",
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Key": adminKey,
    },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });

  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${await res.text()}`);
  }

  return res.json();
}

export interface Team {
  id: string;
  name: string;
  description: string;
  is_active: boolean;
  token_budget_monthly: number;
  rate_limit_rpm: number;
  created_at: string;
}

export interface UsageSummary {
  team_id: string;
  model: string;
  provider: string;
  date: string;
  total_requests: number;
  total_tokens: number;
  total_cost_usd: number;
  cache_hits: number;
}

export interface CostBreakdown {
  team_name: string;
  model: string;
  total_cost_usd: number;
  total_requests: number;
  total_tokens: number;
}

export interface BudgetStatus {
  team_id: string;
  team_name: string;
  budget: number;
  spent: number;
  remaining: number;
  utilization_pct: number;
}

export const api = {
  getTeams: () => apiFetch<Team[]>("/v1/teams"),
  getUsage: (params?: string) =>
    apiFetch<UsageSummary[]>(`/v1/usage${params ? `?${params}` : ""}`),
  getCosts: (params?: string) =>
    apiFetch<{ costs: CostBreakdown[] }>(`/v1/usage/costs${params ? `?${params}` : ""}`),
  getTopModels: (limit = 10) =>
    apiFetch<{ models: { model: string; request_count: number; total_cost: number }[] }>(
      `/v1/usage/top-models?limit=${limit}`
    ),
  getBudgetStatus: () =>
    apiFetch<{ teams: BudgetStatus[] }>("/v1/usage/budget-status"),
  getHealth: () => apiFetch<{ status: string }>("/health"),
};
