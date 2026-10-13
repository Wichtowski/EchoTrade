# EchoTrade — top-level Makefile
# Uses uv workspace — `uv sync` from root installs all members.

MODULES = libshared libdb core pulse signal guard bot ledger review lens wire

.PHONY: sync install-all lint test help run-core up down dash backend-compose mail-up

help:
	@echo "EchoTrade targets:"
	@echo "  sync          — uv sync (install all workspace members)"
	@echo "  up            — start Postgres and the consolidated application"
	@echo "  down          — stop infrastructure"
	@echo "  run-core      — start Core API server"
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
	docker compose up echo-postgres echo-core
	@echo "Postgres and Core API are running; background jobs run inside Core."

mail-up:
	docker compose --profile mail up -d echo-mail
	@echo "docker-mailserver started. Finish mailbox setup from infra/mailserver/README.md"

down:
	docker compose down

run-core:
	uv run uvicorn core.app:app --host 0.0.0.0 --port 8000 --reload

dash:
	cd app/dash && bun run dev

backend-compose:
	docker compose up --build echo-postgres echo-core

test-discord:
	uv run --package wire test-discord

lint:
	@for mod in $(MODULES); do \
		echo "==> Linting $$mod"; \
		$(MAKE) -C app/$$mod lint || true; \
	done

test:
	uv run --all-packages --extra dev pytest app/core/tests app/lens/tests -v
