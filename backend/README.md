# SVOD Backend (FastAPI)

## Быстрый старт (Windows)

1) Поставить зависимости.

Если на диске C: мало места, можно временно работать на системном Python без venv
(главное, чтобы были установлены `fastapi`, `uvicorn`, `sqlalchemy`, `psycopg`).

Вариант с venv:

```powershell
cd d:\alarm\SVOD_SOFT\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2) Настроить переменные окружения:

- Скопируй `.env.example` в `.env`
- Заполни `DATABASE_URL`

3) Запуск API:

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Проверка:
- `GET http://localhost:8000/api/v1/health`
- `GET http://localhost:8000/api/v1/db/tables`

## Зачем эндпоинты `/db/*`

Когда схема БД большая и “что именно дёргать” пока не ясно, эти эндпоинты помогают быстро смотреть таблицы/колонки из браузера/Swagger.
