from __future__ import annotations

import asyncio
import sys
import logging
import re
import ipaddress
from urllib.parse import urlparse


# IMPORTANT (Windows): psycopg async mode is incompatible with ProactorEventLoop.
# Uvicorn may create the event loop very early, so the policy must be set as
# soon as possible (before importing other app modules).
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.api.v1.api import api_router
from app.core.config import settings
from app.db.init_db import init_db
from app.db.session import engine
from app.services.auto_sync import start_auto_sync, stop_auto_sync


logger = logging.getLogger(__name__)


_DEFAULT_INTERNAL_ORIGIN_REGEX = (
    r"^https?://(localhost|127\\.0\\.0\\.1|"
    r"10\\.(?:\\d{1,3}\\.){2}\\d{1,3}|"
    r"192\\.168\\.(?:\\d{1,3}\\.)\\d{1,3}|"
    r"172\\.(?:1[6-9]|2\\d|3[01])\\.(?:\\d{1,3}\\.)\\d{1,3})"
    r"(?::\\d+)?$"
)


def _is_internal_origin(origin: str) -> bool:
    try:
        parsed = urlparse(origin)
        if parsed.scheme not in {"http", "https"}:
            return False
        host = parsed.hostname
        if not host:
            return False
        if host in {"localhost", "127.0.0.1"}:
            return True
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback
    except Exception:
        return False


def _maybe_add_cors_headers(request: Request, response: JSONResponse) -> JSONResponse:
    """Attach minimal CORS headers to error responses.

    Starlette's ExceptionMiddleware is outer to user middleware, so responses generated
    from exception handlers may bypass CORSMiddleware. This helper ensures browsers
    can still read error bodies from the UI origin.
    """

    origin = request.headers.get("origin")
    if not origin:
        return response

    origins = settings.cors_origins_list()
    origin_regex = settings.cors_origin_regex.strip()

    allowed = False
    if origins and origin in origins:
        allowed = True
    elif origin_regex:
        try:
            allowed = re.match(origin_regex, origin) is not None
        except re.error:
            allowed = False
    elif settings.app_env.lower() != "dev" and _is_internal_origin(origin):
        # Intranet-safe fallback: allow private IP / localhost origins in prod.
        allowed = True

    if not allowed:
        return response

    response.headers.setdefault("Access-Control-Allow-Origin", origin)
    response.headers.setdefault("Access-Control-Allow-Credentials", "true")
    response.headers.setdefault("Vary", "Origin")
    return response


def create_app() -> FastAPI:
    app = FastAPI(title="SVOD API", version="0.1.0")

    @app.exception_handler(HTTPException)
    async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        # Preserve correct HTTP status codes for auth/permission errors.
        res = JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        return _maybe_add_cors_headers(request, res)

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Make errors readable for the UI while keeping prod safer.
        if settings.app_env.lower() == "dev":
            res = JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(exc), "type": exc.__class__.__name__},
            )
            return _maybe_add_cors_headers(request, res)

        res = JSONResponse(status_code=500, content={"status": "error", "message": "Internal server error"})
        return _maybe_add_cors_headers(request, res)

    @app.get("/", include_in_schema=False)
    async def _root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    @app.on_event("startup")
    async def _startup() -> None:
        if settings.app_env.lower() != "dev" and settings.insecure_auth:
            raise RuntimeError("INSECURE_AUTH=true is not allowed outside dev")
        await init_db(engine)
        start_auto_sync(app)

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await stop_auto_sync(app)

    origins = settings.cors_origins_list()
    origin_regex = settings.cors_origin_regex.strip()

    default_dev_origin_regex = r"^https?://.+(:5173|:4173)$"

    allow_origin_regex: str | None
    if origin_regex:
        allow_origin_regex = origin_regex
    elif not origins and settings.app_env.lower() == "dev":
        allow_origin_regex = default_dev_origin_regex
    elif settings.app_env.lower() != "dev":
        # Intranet-safe default for prod/stage: allow UI served from private IPs.
        allow_origin_regex = _DEFAULT_INTERNAL_ORIGIN_REGEX
    else:
        allow_origin_regex = None

    # If regex is provided, enable it even when allow_origins is also set.
    # This helps LAN/dev setups where multiple hosts access the UI.
    if origins or allow_origin_regex:
        logger.info(
            "CORS enabled: origins=%s origin_regex=%r allow_origin_regex=%r",
            origins,
            origin_regex,
            allow_origin_regex,
        )
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_origin_regex=allow_origin_regex,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        logger.warning(
            "CORS disabled: CORS_ORIGINS empty and no allow_origin_regex (app_env=%s)",
            settings.app_env,
        )

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
