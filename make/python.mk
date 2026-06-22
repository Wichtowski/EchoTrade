# make/python.mk — shared targets for all Python microservice modules.
# Each module Makefile sets MODULE_NAME and includes this file.
#
# Usage in app/{module}/Makefile:
#   MODULE_NAME := core
#   include ../../make/python.mk

ROOT_DIR := $(shell git rev-parse --show-toplevel 2>/dev/null || echo ../..)

.PHONY: install lint test fmt

install:
	cd $(ROOT_DIR) && uv sync

lint:
	cd $(ROOT_DIR) && uv run ruff check app/$(MODULE_NAME)/src/ app/$(MODULE_NAME)/tests/
	cd $(ROOT_DIR) && uv run mypy app/$(MODULE_NAME)/src/

test:
	cd $(ROOT_DIR) && uv run pytest app/$(MODULE_NAME)/tests/ -v

fmt:
	cd $(ROOT_DIR) && uv run ruff format app/$(MODULE_NAME)/src/ app/$(MODULE_NAME)/tests/
	cd $(ROOT_DIR) && uv run ruff check --fix app/$(MODULE_NAME)/src/ app/$(MODULE_NAME)/tests/
