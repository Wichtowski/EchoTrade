# EchoTrade

AI-powered portfolio assistant and controlled experimental trading lab.

## Architecture

```
EchoTrade
├── app/
│   ├── libshared/       — shared models, schemas, config, constants
│   ├── libdb/           — SQLAlchemy models and database session
│   ├── core/            — backend API (FastAPI)
│   ├── dash/            — frontend dashboard (Next.js)
│   ├── pulse/           — daily portfolio & market summaries
│   ├── signal/          — AI analyst / signal generation
│   ├── guard/           — risk evaluator and policy guard
│   ├── bot/             — execution-only trader bot
│   ├── ledger/          — decision and trade journal
│   ├── review/          — post-trade review engine
│   ├── lens/            — Playwright browser research
│   └── wire/            — Discord notification layer
├── phases/              — roadmap phase definitions
└── docker-compose.yml
```

## Quick Start

```bash
# 1. Install all Python workspace members
uv sync

# 2. Install dash frontend deps
cd app/dash && bun install && cd ../..

# 3. Start infrastructure (Postgres, RabbitMQ, n8n)
make up

# 4. Start the backend API
make run-core

# 5. Start Celery worker (separate terminal)
make worker

# 6. Start the dashboard (separate terminal)
make dash
```

| Service | URL | Notes |
|---------|-----|-------|
| Core API | http://localhost:8000 | FastAPI + Swagger at `/docs` |
| Dashboard | http://localhost:3000 | Vike dev server |
| n8n | http://localhost:5678 | user: `echo` / pass: `echo` |
| RabbitMQ | localhost:5672 | mgmt UI: http://localhost:15672 |
| Postgres | localhost:5432 | db: `echotrade`, user: `echo` |

### Makefile targets

```bash
make help       # show all targets
make sync       # uv sync — install all Python members
make up         # start Postgres + RabbitMQ + n8n
make down       # stop infrastructure
make run-core   # start Core API (uvicorn)
make worker     # start Celery worker
make beat       # start Celery beat scheduler
make dash       # start Dash dev server (Vike)
make lint       # lint all Python modules
make test       # run all tests
```

## Time Horizons

EchoTrade uses the following time-horizon definitions across all modules:

| Horizon | Range | Description |
|---------|-------|-------------|
| Intraday | < 1 day | Same-session open/close. **Forbidden** for experimental account. |
| Short-term | 1–5 days | Swing trade, up to one trading week. |
| Medium-term | 1–8 weeks | Typical experimental trade range. |
| Long-term | 2–6 months | Multi-month thesis; quarterly review. |
| Strategic | > 6 months | Core conviction; semi-annual review. Personal portfolio default. |

## Phases

| Phase | Name | Description |
|-------|------|-------------|
| 1 | Portfolio Tracker | Positions CRUD, prices, P/L, allocation, snapshots, trade journal |
| 2 | Portfolio Monitoring | Hourly position checks during market hours + alerting |
| 3 | Daily Reporting | Daily portfolio report via EchoPulse + EchoWire |
| 4 | Weekly Evaluation & Opportunity Scans | Weekly portfolio reviews + three-times-weekly candidate scans |
| 5 | Paper Trader | Simulated trading with EchoGuard + EchoBot |
| 6 | Manual Approval Live Trading | Discord approval flow + real broker |
| 7 | Limited Autonomous Trading | Auto-execution within strict risk limits |

## Operating Rhythm

EchoTrade is being built around a recurring portfolio operating loop before any serious live automation:

- Hourly during market hours: check held positions, price moves, concentration, and thesis-breaking alerts.
- Daily after market close: generate a portfolio report with value, P/L, allocation, risks, and commentary.
- Weekly: run a deeper evaluation of portfolio results, decisions, and changes in risk.
- Three times per week: scan for potential new investments and "next Nvidia"-style candidates, with reasons and risks.

This means the project should prioritise portfolio intelligence first:

1. Real portfolio tracking and snapshots.
2. Monitoring and reporting workflows.
3. Evaluation and idea discovery.
4. Paper trading for experimentation.
5. Live execution only after the earlier layers are trustworthy.

## Safety

EchoTrade prioritises transparency, auditability, and strict risk control.

The correct trade execution flow is always:

```
EchoSignal → Trade Proposal → EchoGuard → EchoBot → Broker API
```

Never: `LLM → Broker API`

## Production Split

Production is now split across two targets:

- `echodash.oskarwichtowski.com` -> Cloudflare Pages static dashboard from `app/dash/dist/client`
- `api.oskarwichtowski.com` -> Contabo VPS backend API
- `n8n.oskarwichtowski.com` -> Contabo VPS n8n
- `mail.oskarwichtowski.com` -> Contabo VPS docker-mailserver

GitHub Actions:

- `.github/workflows/deploy-dash.yml` deploys the dashboard to Cloudflare Pages
- `.github/workflows/deploy.yml` deploys the backend stack to the VPS
