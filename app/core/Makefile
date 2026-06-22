MODULE_NAME := core
include ../../make/python.mk

.PHONY: run
run:
	cd ../.. && uv run uvicorn core.app:app --host 0.0.0.0 --port 8000 --reload
