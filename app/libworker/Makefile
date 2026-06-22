MODULE_NAME := libworker
include ../../make/python.mk

.PHONY: worker beat

worker:
	cd ../.. && uv run celery -A libworker.celery_app worker --loglevel=info --without-gossip --without-mingle

beat:
	cd ../.. && uv run celery -A libworker.celery_app beat --loglevel=info
