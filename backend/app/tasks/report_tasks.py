from __future__ import annotations

from celery.utils.log import get_task_logger

from app.services.report_service import export_daily_report_csv
from app.tasks.celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(name="svod.generate_daily_report")
def generate_daily_report(date: str) -> dict:
    # На этапе MVP генерируем файл (CSV) без БД.
    content = export_daily_report_csv(date=date)
    logger.info("generate_daily_report: date=%s bytes=%s", date, len(content))
    return {"status": "ok", "date": date, "bytes": len(content)}
