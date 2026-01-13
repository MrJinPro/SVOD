# SVOD Command Center

Фронтенд прототипа S.V.O.D (Vite + React + TypeScript).

## Быстрый старт

Требования: Node.js 18+.

```powershell
cd d:\alarm\SVOD_SOFT\svod-command-center
npm install
npm run dev
```

Откройте: http://localhost:5173

## Подключение к backend

По умолчанию фронт ходит в `http://localhost:8000/api/v1`.

Можно переопределить переменными окружения:

```powershell
setx VITE_API_BASE_URL "http://localhost:8000/api/v1"
setx VITE_API_TOKEN "<Bearer token, если включена защита>"
```

## Сборка и предпросмотр (как на демо)

```powershell
npm run build
npm run preview
```

Preview по умолчанию: http://localhost:4173
