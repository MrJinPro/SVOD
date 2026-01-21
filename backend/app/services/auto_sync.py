from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import FastAPI

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.sync_service import (
    sync_events_from_agency_mssql_archives,
    sync_events_from_agency_mysql,
    sync_objects_from_agency_mssql,
)

logger = logging.getLogger(__name__)

# SQLite allows only one writer at a time. Also prevents overlapping sync loops.
_SYNC_LOCK = asyncio.Lock()


def start_auto_sync(app: FastAPI) -> None:
    if getattr(app.state, "auto_sync_task", None) is not None:
        return

    stop_event = asyncio.Event()
    app.state.auto_sync_stop_event = stop_event

    if not settings.auto_sync_enabled:
        logger.info("Auto-sync disabled (AUTO_SYNC_ENABLED=false)")
        return

    task = asyncio.create_task(_auto_sync_loop(stop_event))
    app.state.auto_sync_task = task
    logger.info(
        "Auto-sync started: interval=%ss eventsLimit=%s objectsInterval=%ss",
        settings.auto_sync_interval_seconds,
        settings.auto_sync_events_limit,
        settings.auto_sync_objects_interval_seconds,
    )


async def stop_auto_sync(app: FastAPI) -> None:
    stop_event = getattr(app.state, "auto_sync_stop_event", None)
    task = getattr(app.state, "auto_sync_task", None)

    if stop_event is None or task is None:
        return

    stop_event.set()
    try:
        await asyncio.wait_for(task, timeout=5)
    except TimeoutError:
        task.cancel()
    finally:
        app.state.auto_sync_task = None
        app.state.auto_sync_stop_event = None


async def _auto_sync_loop(stop_event: asyncio.Event) -> None:
    url = settings.agency_database_url
    if not url:
        logger.info("Auto-sync idle: AGENCY_DATABASE_URL not set")
        return

    scheme = (url.split(":", 1)[0] or "").lower()
    if not (scheme.startswith("mysql") or scheme.startswith("mssql")):
        logger.warning("Auto-sync unsupported scheme: %s", scheme)
        return

    last_objects_sync_ts = 0.0

    while not stop_event.is_set():
        started_at = time.monotonic()
        try:
            async with _SYNC_LOCK:
                async with SessionLocal() as session:
                    if scheme.startswith("mysql"):
                        await sync_events_from_agency_mysql(
                            session=session,
                            agency_mysql_url=url,
                            batch_limit=settings.auto_sync_events_limit,
                        )
                    else:
                        await sync_events_from_agency_mssql_archives(
                            session=session,
                            agency_mssql_url=url,
                            archives_db_name=settings.agency_archives_db_name,
                            batch_limit=settings.auto_sync_events_limit,
                        )

                    now = time.monotonic()
                    if scheme.startswith("mssql") and (
                        now - last_objects_sync_ts
                    ) >= settings.auto_sync_objects_interval_seconds:
                        await sync_objects_from_agency_mssql(session=session, agency_mssql_url=url)
                        last_objects_sync_ts = now

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Auto-sync iteration failed")

        elapsed = time.monotonic() - started_at
        sleep_for = max(1.0, float(settings.auto_sync_interval_seconds) - elapsed)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=sleep_for)
        except TimeoutError:
            continue


async def auto_sync_status() -> dict[str, Any]:
    url = settings.agency_database_url
    scheme = (url.split(":", 1)[0] or "").lower() if url else None
    return {
        "enabled": bool(settings.auto_sync_enabled),
        "agencyUrlConfigured": bool(url),
        "scheme": scheme,
        "intervalSeconds": int(settings.auto_sync_interval_seconds),
        "eventsLimit": int(settings.auto_sync_events_limit),
        "objectsIntervalSeconds": int(settings.auto_sync_objects_interval_seconds),
    }
