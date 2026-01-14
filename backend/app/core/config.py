from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# backend/app/core/config.py -> parents[2] is the backend/ directory.
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_PROJECT_DIR = _BACKEND_DIR.parent


class Settings(BaseSettings):
    # Always load backend/.env regardless of current working directory.
    # Also allow a project-root .env as a fallback for legacy setups.
    model_config = SettingsConfigDict(
        env_file=(str(_BACKEND_DIR / ".env"), str(_PROJECT_DIR / ".env")),
        extra="ignore",
    )

    app_env: str = "dev"

    # Дефолт позволяет стартовать сервис даже без .env (подключение к БД
    # фактически происходит только при обращении к эндпоинтам, использующим session).
    database_url: str = "postgresql+psycopg://svod:svod@localhost:5432/svod"
    agency_database_url: str | None = None

    # MSSQL: имя базы с архивными таблицами archiveYYYYMM01/eventserviceYYYYMM01
    agency_archives_db_name: str = "pult4db_archives"

    # MSSQL archives: с какого Date_Key начинать первичную загрузку,
    # если курсора ещё нет в sync_state. Формат: YYYYMMDD (например 20260101).
    # Если не задано, используется первое число текущего месяца.
    agency_mssql_archive_start_date_key: int | None = None

    # Демо-эндпоинты для заполнения мок-данными (по умолчанию выключены)
    enable_demo_seed: bool = False

    cors_origins: str = ""
    cors_origin_regex: str = ""

    jwt_secret: str = "dev-secret-change-me"

    # Bootstrap superadmin (optional). Do NOT hardcode passwords in repo.
    superadmin_username: str = ""
    superadmin_password: str = ""
    superadmin_email: str = ""

    # Celery / Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    def cors_origins_list(self) -> list[str]:
        if not self.cors_origins.strip():
            return []
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()  # type: ignore[call-arg]
