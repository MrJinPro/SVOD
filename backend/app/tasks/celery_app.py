from __future__ import annotations

from celery import Celery

from app.core.config import settings


def _get_broker_url() -> str:
    return settings.celery_broker_url or settings.redis_url


def _get_result_backend() -> str:
    return settings.celery_result_backend or settings.redis_url


celery_app = Celery(
    "svod",
    broker=_get_broker_url(),
    backend=_get_result_backend(),
    include=[
        "app.tasks.sync_tasks",
        "app.tasks.report_tasks",
    ],
)

celery_app.conf.update(
    timezone="Europe/Moscow",
    enable_utc=False,
)
