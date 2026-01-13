from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.api.v1.api import api_router
from app.core.config import settings
from app.db.init_db import init_db
from app.db.session import engine


def create_app() -> FastAPI:
    app = FastAPI(title="SVOD API", version="0.1.0")

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Make errors readable for the UI while keeping prod safer.
        if settings.app_env.lower() == "dev":
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(exc), "type": exc.__class__.__name__},
            )
        return JSONResponse(status_code=500, content={"status": "error", "message": "Internal server error"})

    @app.get("/", include_in_schema=False)
    async def _root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    @app.on_event("startup")
    async def _startup() -> None:
        await init_db(engine)

    origins = settings.cors_origins_list()
    origin_regex = settings.cors_origin_regex.strip()

    # If explicit origins are provided, use them.
    # Otherwise, in dev allow typical Vite dev/prod-preview ports via regex.
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    elif origin_regex or settings.app_env.lower() == "dev":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[],
            allow_origin_regex=origin_regex or r"^https?://.+(:5173|:4173)$",
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
