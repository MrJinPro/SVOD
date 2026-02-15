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
    sync_events_from_agency_sqlite_archives,
    sync_objects_from_agency_mssql,
    sync_objects_from_agency_sqlite,
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
    last_objects_sync_ts = 0.0
    last_logged_state: tuple[str | None, str | None] = (None, None)
    last_warned_unsupported_scheme: str | None = None

    while not stop_event.is_set():
        started_at = time.monotonic()
        try:
            url = settings.agency_database_url
            scheme = (url.split(":", 1)[0] or "").lower() if url else None

            # Log state changes (helps diagnose why data isn't flowing).
            if (url, scheme) != last_logged_state:
                last_logged_state = (url, scheme)
                if not url:
                    logger.info("Auto-sync idle: AGENCY_DATABASE_URL not set")
                else:
                    logger.info("Auto-sync source: scheme=%s url=%s", scheme, url)

            if not url or not scheme:
                # Nothing to do yet.
                continue

            if not (scheme.startswith("mysql") or scheme.startswith("mssql") or scheme.startswith("sqlite")):
                if scheme != last_warned_unsupported_scheme:
                    logger.warning("Auto-sync unsupported scheme: %s", scheme)
                    last_warned_unsupported_scheme = scheme
                continue

            async with _SYNC_LOCK:
                async with SessionLocal() as session:
                    if scheme.startswith("mysql"):
                        await sync_events_from_agency_mysql(
                            session=session,
                            agency_mysql_url=url,
                            batch_limit=settings.auto_sync_events_limit,
                        )
                    elif scheme.startswith("mssql"):
                        await sync_events_from_agency_mssql_archives(
                            session=session,
                            agency_mssql_url=url,
                            archives_db_name=settings.agency_archives_db_name,
                            batch_limit=settings.auto_sync_events_limit,
                        )
                    else:
                        await sync_events_from_agency_sqlite_archives(
                            session=session,
                            agency_sqlite_url=url,
                            batch_limit=settings.auto_sync_events_limit,
                        )

                    now = time.monotonic()
                    if (now - last_objects_sync_ts) >= settings.auto_sync_objects_interval_seconds:
                        if scheme.startswith("mssql"):
                            await sync_objects_from_agency_mssql(session=session, agency_mssql_url=url)
                            last_objects_sync_ts = now
                        elif scheme.startswith("sqlite"):
                            await sync_objects_from_agency_sqlite(session=session, agency_sqlite_url=url)
                            last_objects_sync_ts = now

        except asyncio.CancelledError:
            raise
        except Exception:
            # Don't stop the loop: keep trying.
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

    logger.info("Fetching auto-sync status")

    return {
        "enabled": settings.auto_sync_enabled,
        "database_url": url,
        "scheme": scheme,
        "interval_seconds": settings.auto_sync_interval_seconds,
        "events_limit": settings.auto_sync_events_limit,
        "objects_interval_seconds": settings.auto_sync_objects_interval_seconds,
    }
