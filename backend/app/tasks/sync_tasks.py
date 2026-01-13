from __future__ import annotations

import asyncio

from celery.utils.log import get_task_logger

from app.core.config import settings
from app.db.session import SessionLocal
from app.tasks.celery_app import celery_app
from app.services.sync_service import sync_events_from_agency_mysql, sync_objects_from_agency_mssql

logger = get_task_logger(__name__)


@celery_app.task(name="svod.sync_events")
def sync_events() -> dict:
    if not settings.agency_database_url:
        logger.info("sync_events: AGENCY_DATABASE_URL not set")
        return {"status": "skipped", "reason": "AGENCY_DATABASE_URL not set"}

    async def _run() -> dict:
        async with SessionLocal() as session:
            return await sync_events_from_agency_mysql(
                session=session,
                agency_mysql_url=settings.agency_database_url or "",
                batch_limit=500,
            )

    result = asyncio.run(_run())
    logger.info("sync_events: %s", result)
    return result


@celery_app.task(name="svod.sync_objects")
def sync_objects() -> dict:
    if not settings.agency_database_url:
        logger.info("sync_objects: AGENCY_DATABASE_URL not set")
        return {"status": "skipped", "reason": "AGENCY_DATABASE_URL not set"}

    url = settings.agency_database_url
    scheme = (url.split(":", 1)[0] or "").lower()
    if not scheme.startswith("mssql"):
        logger.info("sync_objects: Unsupported scheme: %s", scheme)
        return {"status": "error", "reason": f"Unsupported scheme: {scheme}"}

    async def _run() -> dict:
        async with SessionLocal() as session:
            return await sync_objects_from_agency_mssql(
                session=session,
                agency_mssql_url=url,
            )

    result = asyncio.run(_run())
    logger.info("sync_objects: %s", result)
    return result
