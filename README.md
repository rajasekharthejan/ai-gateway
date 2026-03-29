# AI Gateway Platform

A centralized API gateway for routing, monitoring, and governing LLM API calls across multiple providers (OpenAI, Azure OpenAI, AWS Bedrock). Built for enterprises managing AI spend across teams.

## Why This Exists

When multiple teams use LLMs independently, you get:
- **No cost visibility** — $50K monthly bills with no breakdown
- **No access control** — interns calling GPT-4 Turbo for summarization
- **No rate protection** — one runaway script exhausts the org's API quota
- **Vendor lock-in** — every team imports `openai` directly

This gateway sits between your teams and the LLM providers, adding governance without changing how teams write code.

## Architecture

```
┌──────────────┐     ┌──────────────────────────────────────────┐     ┌─────────────┐
│              │     │              AI GATEWAY                   │     │   OpenAI     │
│  Your App    │────▶│                                          │────▶│   API        │
│  (any lang)  │     │  Auth → Rate Limit → Policy → Cache     │     ├─────────────┤
│              │◀────│       → Route → Cost Track → Audit       │────▶│  Azure       │
│              │     │                                          │     │  OpenAI      │
└──────────────┘     ├──────────┬──────────┬───────────────────┤     ├─────────────┤
                     │ Postgres │  Redis   │  React Dashboard  │────▶│  AWS         │
                     │ (audit,  │ (cache,  │  (cost monitoring) │     │  Bedrock     │
                     │  usage)  │  rate    │                    │     └─────────────┘
                     │          │  limit)  │                    │
                     └──────────┴──────────┴───────────────────┘
```

## Features

| Feature | Description |
|---------|-------------|
| **Multi-Provider Routing** | OpenAI, Azure OpenAI, AWS Bedrock with automatic failover |
| **Cost Tracking** | Per-token pricing for 20+ models, daily aggregated summaries |
| **Team Management** | Isolated API keys, token budgets, rate limits per team |
| **Policy Engine** | Glob-pattern resource matching, deny/allow rules, conditions (max_tokens, time_window, model lists) |
| **Rate Limiting** | Redis sliding window (60s), per-team RPM configuration |
| **Response Caching** | SHA256-based deterministic caching for temperature=0 requests |
| **Audit Logging** | Every request logged: model, tokens, cost, latency, status, truncated body |
| **Usage Analytics** | Costs by team/model, top models, budget utilization, date-range filtering |
| **React Dashboard** | Overview, cost charts, team management, budget gauges |

## Tech Stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy (async), Pydantic v2
- **Database:** PostgreSQL 16 (via asyncpg)
- **Cache/Rate Limiter:** Redis 7
- **Providers:** httpx (OpenAI/Azure), boto3 (Bedrock)
- **Dashboard:** Next.js 15, React 19, Recharts, Tailwind CSS
- **Infrastructure:** Docker Compose, Alembic migrations

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/rajasekharthejan/ai-gateway.git
cd ai-gateway
cp .env.example .env
# Edit .env with your API keys

# 2. Start everything
docker compose up -d

# 3. Run migrations
docker compose exec gateway alembic upgrade head

# 4. Create a team + API key
curl -X POST http://localhost:8000/v1/teams \
  -H "X-Admin-Key: your-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"name": "engineering", "token_budget_monthly": 5000000}'

curl -X POST http://localhost:8000/v1/teams/{team_id}/keys \
  -H "X-Admin-Key: your-admin-key" \
  -d '{"name": "prod-key"}'

# 5. Use it (drop-in replacement for OpenAI)
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer gw-your-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## API Endpoints

### Gateway
| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/chat/completions` | OpenAI-compatible chat endpoint |
| GET | `/health` | Liveness check |
| GET | `/health/ready` | Readiness (DB + Redis) |

### Admin (requires `X-Admin-Key` header)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/teams` | Create team |
| GET | `/v1/teams` | List teams |
| PUT | `/v1/teams/{id}` | Update team |
| POST | `/v1/teams/{id}/keys` | Generate API key |
| DELETE | `/v1/teams/{id}/keys/{key_id}` | Revoke API key |
| POST | `/v1/policies` | Create policy |
| GET | `/v1/policies` | List policies |
| GET | `/v1/usage` | Usage summaries |
| GET | `/v1/usage/costs` | Cost breakdown by team/model |
| GET | `/v1/usage/top-models` | Top N models by usage |
| GET | `/v1/usage/budget-status` | Budget utilization |

## Request Pipeline

Every request flows through this pipeline:

```
Request → Auth (API key → team lookup)
        → Rate Limit (Redis sliding window, 60s)
        → Policy Engine (glob matching, conditions)
        → Cache Check (SHA256 key, temp=0 only)
        → Provider Router (failover across providers)
        → Cost Calculation (per-model token pricing)
        → Audit Log (PostgreSQL)
        → Usage Summary (daily aggregation)
        → Response (with gateway_metadata)
```

## Response Format

The gateway adds `gateway_metadata` to every response:

```json
{
  "id": "chatcmpl-abc123",
  "model": "gpt-4o-mini",
  "choices": [...],
  "usage": {
    "prompt_tokens": 25,
    "completion_tokens": 50,
    "total_tokens": 75
  },
  "gateway_metadata": {
    "cost_usd": 0.0000337,
    "cache_hit": false,
    "provider": "openai",
    "latency_ms": 892,
    "request_id": "req_abc123"
  }
}
```

## Project Structure

```
ai-gateway/
├── app/
│   ├── main.py              # FastAPI app + lifespan
│   ├── config.py             # Pydantic Settings
│   ├── database.py           # SQLAlchemy async engine
│   ├── cache.py              # Redis connection pool
│   ├── models/               # SQLAlchemy ORM models
│   │   ├── user.py           # Team, ApiKey
│   │   ├── audit.py          # AuditLog
│   │   ├── policy.py         # Policy
│   │   └── usage.py          # UsageSummary
│   ├── providers/            # LLM provider adapters
│   │   ├── base.py           # Abstract BaseProvider
│   │   ├── openai_provider.py
│   │   ├── azure_provider.py
│   │   └── bedrock_provider.py
│   ├── routers/              # API routes
│   │   ├── gateway.py        # /v1/chat/completions
│   │   ├── admin.py          # Team + key management
│   │   ├── policies.py       # Policy CRUD
│   │   ├── usage.py          # Analytics endpoints
│   │   └── health.py         # Health checks
│   ├── services/             # Business logic
│   │   ├── router.py         # Provider routing + failover
│   │   ├── cost_tracker.py   # Token pricing + usage aggregation
│   │   ├── policy_engine.py  # Access control evaluation
│   │   ├── rate_limiter.py   # Redis sliding window
│   │   ├── cache.py          # Response caching
│   │   └── audit.py          # Audit logging
│   └── schemas/              # Pydantic models
│       ├── gateway.py        # Chat completion req/resp
│       ├── auth.py           # Team/key schemas
│       ├── policy.py         # Policy schemas
│       └── usage.py          # Usage/cost schemas
├── dashboard/                # React cost monitoring UI
│   └── src/
│       ├── app/              # Next.js pages
│       ├── components/       # Charts, stats cards
│       └── lib/              # API client
├── alembic/                  # Database migrations
├── tests/                    # pytest test suite
├── docker-compose.yml        # Postgres + Redis + Gateway
├── Dockerfile
└── requirements.txt
```

## Running Tests

```bash
pip install -r requirements.txt
pytest -v
```

## Dashboard

```bash
cd dashboard
npm install
npm run dev
# Open http://localhost:3001
```

The dashboard proxies API calls to the gateway at `localhost:8000`.

## License

MIT
