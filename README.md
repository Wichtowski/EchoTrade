# EchoTrade

AI-powered portfolio assistant and controlled experimental trading lab.

EchoTrade is built in layers: track the portfolio first, monitor it during market hours, generate daily and weekly intelligence, then add guarded paper trading and eventually tightly constrained live execution.

## Architecture

```text
EchoTrade
├── app/
│   ├── libshared/       - shared config, schemas, constants
│   ├── libdb/           - SQLAlchemy models and database session
│   ├── libworker/       - Celery app and shared worker tasks
│   ├── core/            - FastAPI backend API
│   ├── dash/            - Vike + React dashboard
│   ├── pulse/           - daily portfolio and market summaries
│   ├── signal/          - AI analyst and signal generation
│   ├── guard/           - risk evaluator and policy guard
│   ├── bot/             - execution-only trader bot
│   ├── ledger/          - decision and trade journal
│   ├── review/          - post-trade review engine
│   ├── lens/            - browser research and chart capture
│   └── wire/            - Discord notification layer
├── infra/
│   ├── n8n/             - workflow templates and orchestration notes
│   ├── mailserver/      - docker-mailserver setup
│   └── caddy/           - production reverse proxy config
├── phases/              - roadmap phase definitions
├── docker-compose.yml   - local development stack
└── docker-compose.prod.yml
```

## Prerequisites

- `uv` for the Python workspace
- `bun` for the dashboard
- Docker Compose for local infrastructure

## Quick Start

```bash
# 1. Create local env file
cp .env.example .env

# 2. Install all Python workspace members
uv sync

# 3. Install dashboard dependencies
cd app/dash
bun install
cd ../..

# 4. Start local infrastructure
make up

# 5. Start the backend API
make run-core

# 6. Start the Celery worker in a second terminal
make worker

# 7. Start the dashboard in a third terminal
make dash
```

The backend reads local configuration from `.env`. The dashboard reads its frontend env files from `app/dash/`.

## Local Services

| Service | URL / Port | Notes |
|---------|------------|-------|
| Core API | http://localhost:8000 | FastAPI docs at `/docs` |
| Dashboard | http://localhost:3000 | Vike dev server |
| n8n | http://localhost:5678 | user: `echo`, pass: `echo` |
| Postgres | localhost:5432 | db: `echotrade`, user: `echo`, pass: `echo` |
| RabbitMQ | localhost:5672 | management UI at http://localhost:15672 |
| Redis | localhost:6379 | cache and task support |
| MongoDB | localhost:27017 | browser capture and saved query storage |
| Mail | localhost:25 / 587 / 143 / 993 | docker-mailserver for invite delivery |

## Common Commands

```bash
make help            # show all top-level targets
make sync            # install Python workspace members
make up              # start Postgres, RabbitMQ, Redis, MongoDB, n8n, mail
make down            # stop local infrastructure
make run-core        # start FastAPI app with reload
make worker          # start Celery worker
make beat            # start Celery beat scheduler
make dash            # start dashboard dev server
make backend-compose # build and run the backend stack with Docker Compose
make lint            # lint all Python modules
make test            # run tests for all Python modules
```

## Environment

Start from `.env.example`. Important groups include:

- database and queue settings for Postgres, RabbitMQ, Redis, and MongoDB
- market data and LLM provider keys
- Discord webhook targets
- internal automation auth via `ECHO_INTERNAL_API_TOKEN`
- SMTP settings for invite delivery
- frontend/API URLs such as `ECHO_PUBLIC_APP_URL`
- Caddy Basic Auth hash for the public n8n route via `N8N_BASIC_AUTH_HASH`

For n8n automations, set both `ECHO_INTERNAL_API_TOKEN` and `ECHO_AUTOMATION_USER_ID`.
The workflow templates live in `infra/n8n/`.

## Operating Rhythm

EchoTrade is being built around a recurring portfolio loop before any serious live automation:

1. Hourly during market hours: check held positions, price moves, concentration, and thesis-breaking alerts.
2. Daily after market close: generate a portfolio report with value, P/L, allocation, risks, and commentary.
3. Weekly: run a deeper evaluation of portfolio results, decisions, and changing risk.
4. Three times per week: scan for new investment candidates with reasons and risks.

This keeps the roadmap focused on portfolio intelligence first, then paper trading, and only later live execution.

## Time Horizons

| Horizon | Range | Description |
|---------|-------|-------------|
| Intraday | < 1 day | Same-session open/close. Forbidden for the experimental account. |
| Short-term | 1-5 days | Swing trade, up to one trading week. |
| Medium-term | 1-8 weeks | Typical experimental trade range. |
| Long-term | 2-6 months | Multi-month thesis with quarterly review. |
| Strategic | > 6 months | Core conviction with semi-annual review. |

## Phases

| Phase | Name | Description |
|-------|------|-------------|
| 1 | Portfolio Tracker | Positions CRUD, prices, P/L, allocation, snapshots, trade journal |
| 2 | Portfolio Monitoring | Hourly position checks during market hours and alerting |
| 3 | Daily Reporting | Daily portfolio report via EchoPulse and EchoWire |
| 4 | Weekly Evaluation and Opportunity Scans | Weekly reviews plus Monday/Wednesday/Friday candidate scans |
| 5 | Paper Trader | Simulated trading with EchoGuard and EchoBot |
| 6 | Manual Approval Live Trading | Approval flow plus real broker |
| 7 | Limited Autonomous Trading | Auto-execution within strict risk limits |

## Safety

EchoTrade prioritizes transparency, auditability, and strict risk control.

The execution flow is always:

```text
EchoSignal -> Trade Proposal -> EchoGuard -> EchoBot -> Broker API
```

Never:

```text
LLM -> Broker API
```

## Deployment

Production is split across a static frontend target and a VPS-hosted backend stack:

- `echotrade.oskarwichtowski.com`
- `apiechotrade.oskarwichtowski.com`
- `n8n.oskarwichtowski.com`
- `mail.oskarwichtowski.com`

On the VPS, only Caddy and the mail server publish host ports. Caddy handles `80` and `443`; the mail server handles `25`, `587`, `143`, and `993`. Postgres, Redis, RabbitMQ, MongoDB, n8n, the Core API, and workers stay private on Docker networks and are not exposed on the host.

The production Compose stack separates those networks so Caddy can reach only the app services it reverse-proxies, while databases and brokers remain on the internal `data_net`.

GitHub Actions:

- `.github/workflows/deploy-release.yml` deploys a release tag to the VPS backend stack and Cloudflare Pages dashboard
- each merge to `main` creates the next patch tag in the `x.y.z` series
- manual dispatch redeploys both backend and dashboard for a chosen version or the latest tag

Before exposing the public n8n host, protect it with Caddy Basic Auth:

```bash
caddy hash-password
```

Add the generated hash to the GitHub Actions secret `N8N_BASIC_AUTH_HASH`, redeploy with `.github/workflows/deploy-release.yml`, and open the n8n route to confirm the browser asks for Basic Auth.
Production n8n is protected by Caddy Basic Auth and can also keep its own n8n auth enabled for defense in depth.
