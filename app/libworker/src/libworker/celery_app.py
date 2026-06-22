"""Celery application factory for EchoTrade."""

from __future__ import annotations

from celery import Celery

from libshared.config import settings

app = Celery("echotrade")

app.conf.update(
    broker_url=settings.celery_broker_url,
    result_backend=settings.celery_result_backend,
    task_ignore_result=True,
    task_store_errors_even_if_ignored=False,
    result_extended=False,
    task_default_queue="echotrade",
    task_default_queue_type="quorum",
    task_create_missing_queues=True,
    task_create_missing_queue_type="quorum",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Warsaw",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_detect_quorum_queues=True,
    worker_enable_remote_control=False,
    # Autodiscover tasks from all service modules
    include=[
        "libworker.tasks.portfolio",
        "libworker.tasks.market",
        "libworker.tasks.notifications",
    ],
)
