# EchoTrade

Portfolio intelligence and a guarded paper-trading lab.

## One application service

EchoCore runs the API, background jobs, scheduler, AI research, and browser captures in one Python process. PostgreSQL stores portfolios, paper accounts, job history, captures, and saved chart queries. Redis, RabbitMQ, MongoDB, n8n, and a separate Celery worker are no longer required. The dashboard remains on Cloudflare.

The default production stack contains only `echo-core` and `echo-postgres`. The mail server is optional (`--profile mail`); an existing SMTP service can handle invites instead. PostgreSQL may also be an existing VPS database via `ECHO_DATABASE_URL`.

Jobs run one at a time. PostgreSQL advisory locks elect one consumer, queued work survives restarts, and scheduled jobs are unique per user/period. Transient network failures retry at most three times. Research output is saved before delivery retries; paper fills and cash updates commit together.

## Development

Requires uv, Bun, and Docker Compose.

```bash
cp .env.example .env
uv sync --all-packages --extra dev
cd app/dash && bun install
```

Start the database with `docker compose up -d echo-postgres`, then `make run-core` and `make dash` in separate terminals. `make backend-compose` runs the database and consolidated application in containers. There is no separate worker or Beat process.

Use `make test` for Python tests and `cd app/dash && bun run lint && bun run build` for the dashboard. Database integration tests require an explicitly supplied isolated `ECHO_TEST_DATABASE_URL`; they create and remove their own schemas.

## Models and automation

Configure `ECHO_OPENAI_API_KEY` on the server. In **AI & Automation**, owners select separate commentary/proposal models and reasoning effort. Supported choices are `gpt-6-luna` (default), `gpt-6.1-sol`, and `gpt-6-astra`. Preferences are persisted per user and used by both manual requests and scheduled jobs. The browser never receives the API key. Higher model/effort selections and web searches incur provider usage charges.

Automation starts disabled. Enabling it schedules:

- Hourly quote refresh and risk monitoring during US exchange sessions.
- Daily portfolio snapshot and sourced commentary 15 minutes after exchange close.
- Sunday weekly review after 18:00 Europe/Warsaw.
- Monday/Wednesday/Friday opportunity scans after the first trading hour.

The exchange calendar handles holidays, early closes, and DST. Monitoring currently follows US sessions; holdings on other exchanges need per-exchange schedules in a future change. Notifications use the existing Discord webhook settings. Identical consecutive hourly warnings are suppressed. A crash after Discord accepts a message but before the delivery commit may still duplicate that message.

Scheduled scans generate proposals only when their separate preference is enabled and the paper account is active. AI refusals, errors, and no-trade decisions remain visible in job history. AI does not execute trades.

## Paper account

Each user has an isolated USD paper account, initially paused, with starting cash configured by `ECHO_PAPER_INITIAL_CASH` (default USD 300). Activate it in **Paper trading**, create a sourced manual or AI proposal, evaluate risk, approve, then execute a simulated fill.

Only experimental USD market orders are supported. Quotes must come from a supported market-data provider, match the account currency, and be recent. Missing/stale valuations, insufficient cash or holdings, daily/monthly loss limits, exposure limits, budgets, cooldowns, and paused/closed-market execution reject the trade. USD risk budgets and trade limits come from the existing `ECHO_MAX_*` settings.

Risk evaluation never grants manual approval. Execution rechecks all constraints under a user lock. Retrying an already filled proposal returns the existing fill; a database uniqueness constraint also prevents duplicates. Cash, holdings, and realized/unrealized P/L derive from the paper ledger. Personal holdings are unchanged.

Fills support fractional quantities, use the stored quote, and assume zero fees; spreads/slippage and real broker execution are outside this simulator. Legacy simulated fills remain stored but are excluded from the new funded account because they had no cash ledger.

## Production transition

Before upgrading, disable the legacy n8n workflows, stop the old Core and Celery worker to prevent new captures, back up PostgreSQL and MongoDB, and copy the legacy captures and saved chart queries. Keep MongoDB and PostgreSQL running for the import. The importer is repeatable, preserves identifiers, and never deletes MongoDB data:

```bash
uv sync --all-packages --extra migration
# ECHO_DATABASE_URL targets the existing EchoTrade database;
# ECHO_MONGODB_URL targets the legacy MongoDB instance.
uv run --package core --extra migration python -m core.import_mongo
```

If uv is unavailable on the VPS, build the new Core image from the selected release in the existing project directory and run `docker compose --env-file .env -f docker-compose.prod.yml run --rm --no-deps --entrypoint /opt/venv/bin/python echo-core -m core.import_mongo` while the legacy MongoDB/PostgreSQL containers remain running on the existing networks. Keep a copy of the old Compose file to stop its services after the import.

Then stop the old stack with its original Compose file and start the new `docker-compose.prod.yml`. No volume deletion is required. Existing legacy volumes remain declared in the production file so operators can recover them. The application uses PostgreSQL immediately after the upgrade, so import the legacy documents before stopping MongoDB. The release deployment refuses to proceed until the legacy MongoDB import marker is present when a legacy MongoDB container exists.

Keep one Uvicorn worker for the smallest memory footprint. `echo-core` has a 768 MB cap and one CPU; PostgreSQL has a 256 MB cap with 64 MB shared buffers. These are configured limits, not measured production usage. Chromium starts only for requested captures and shares the single background slot. Existing production capacity and SMTP delivery must be verified on the VPS.

The public API hostname and existing edge routing remain unchanged. Backend start/stop/restart actions now target only `echo-core`. No live broker execution is enabled.
