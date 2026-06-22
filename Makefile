# EchoTrade — top-level Makefile
# Uses uv workspace — `uv sync` from root installs all members.

MODULES = libshared libdb libworker core pulse signal guard bot ledger review lens wire

.PHONY: sync install-all lint test help run-core up down dash worker beat backend-compose mail-up

help:
	@echo "EchoTrade targets:"
	@echo "  sync          — uv sync (install all workspace members)"
	@echo "  up            — start infrastructure (Postgres, RabbitMQ, Redis, MongoDB, n8n, mail)"
	@echo "  down          — stop infrastructure"
	@echo "  run-core      — start Core API server"
	@echo "  worker        — start Celery worker"
	@echo "  beat          — start Celery beat scheduler"
	@echo "  backend-compose — build and run backend stack with Docker Compose"
	@echo "  mail-up        — start docker-mailserver for invite delivery"
	@echo "  dash          — start Dash dev server (Vike)"
	@echo "  test-discord  — send test message to all Discord webhooks"
	@echo "  lint          — lint all Python modules"
	@echo "  test          — run tests for all Python modules"

sync:
	uv sync

install-all: sync

up:
	docker compose up echo-postgres echo-rabbitmq echo-redis echo-mongo echo-n8n echo-mail
	@echo "Postgres: localhost:5432  RabbitMQ: localhost:5672 (mgmt :15672)  Redis: localhost:6379  MongoDB: localhost:27017  n8n: http://localhost:5678  Mail SMTP: localhost:25/587"

mail-up:
	docker compose up -d echo-mail
	@echo "docker-mailserver started. Finish mailbox setup from infra/mailserver/README.md"

down:
	docker compose down

run-core:
	uv run uvicorn core.app:app --host 0.0.0.0 --port 8000 --reload

dash:
	cd app/dash && bun run dev

worker:
	uv run celery -A libworker.celery_app worker --loglevel=info --without-gossip --without-mingle

backend-compose:
	docker compose up --build echo-postgres echo-rabbitmq echo-redis echo-mongo echo-core echo-worker echo-n8n echo-mail

beat:
	uv run celery -A libworker.celery_app beat --loglevel=info

test-discord:
	uv run --package wire test-discord

lint:
	@for mod in $(MODULES); do \
		echo "==> Linting $$mod"; \
		$(MAKE) -C app/$$mod lint || true; \
	done

test:
	@for mod in $(MODULES); do \
		echo "==> Testing $$mod"; \
		$(MAKE) -C app/$$mod test || true; \
	done
