from __future__ import annotations

from celery.utils.log import get_task_logger
from app.tasks.celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(name="svod.generate_daily_report")
def generate_daily_report(date: str) -> dict:
    logger.warning("generate_daily_report is disabled: date=%s", date)
    return {
        "status": "disabled",
        "date": date,
        "message": "Daily report generation is disabled",
    }
