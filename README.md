# AI Gateway

A centralized API layer for LLM access. Routes requests across multiple providers (Azure OpenAI, AWS Bedrock), enforces per-tenant rate limits, tracks usage costs, and applies policy controls — so each application in an organization doesn't have to reinvent the same plumbing.

## Why this exists

Teams adopting LLMs often end up with each application calling OpenAI or Bedrock directly. No central visibility into spend, no consistent rate limiting, no unified guardrails, and every team re-implementing the same retry and fallback logic.

AI Gateway sits in front of the provider APIs and solves all of that in one place.

## What it does

- **Multi-provider routing** — single API that fronts Azure OpenAI, AWS Bedrock, and more. Route by model name, tenant policy, or fallback chain.
- **Per-tenant rate limiting** — prevents runaway spend and noisy-neighbor problems in multi-application environments.
- **Cost tracking** — attributes LLM spend by tenant, application, and model.
- **Audit logging** — records prompts, responses, and metadata for compliance review.
- **Policy enforcement** — configurable guardrails for PII redaction, scope limits, and output filtering.

## Tech

- **Language:** Python 3.11+
- **Framework:** FastAPI
- **Storage:** PostgreSQL (usage logs, tenant config), Redis (rate-limit counters)
- **Providers:** Azure OpenAI, AWS Bedrock
- **Deploy:** Docker; runs on ECS, Kubernetes, or any container host
- **Observability:** OpenTelemetry metrics and traces

## Quick start

```bash
git clone https://github.com/rajasekharthejan/ai-gateway
cd ai-gateway
cp .env.example .env
# Fill in AZURE_OPENAI_API_KEY, AWS credentials, etc.
docker compose up
```

Gateway will be available at `http://localhost:8080`.

## API shape

```bash
# All requests use the same shape regardless of provider
POST /v1/chat/completions
X-Tenant-Id: acme-corp
Content-Type: application/json

{
  "model": "gpt-4",          # or "claude-3-sonnet", "llama3-70b", etc.
  "messages": [...],
  "max_tokens": 500
}
```

Gateway routes to the right provider, applies the tenant's rate limits and policies, logs the call, and returns the standard OpenAI-compatible response shape.

## Status

Early-stage. Core routing and rate-limiting working. Policy enforcement and cost dashboards under active development.

## License

MIT
