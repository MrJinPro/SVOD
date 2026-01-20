# Шпаргалка для ВМ (SVOD)

Цель: быстро обновить код из Git и поднять backend+frontend на ВМ.

Ориентир по путям:
- Репозиторий: `/home/user/svod`
- Backend: `/home/user/svod/backend`
- Frontend: `/home/user/svod/svod-command-center`
- Виртуальное окружение Python (пример): `/home/user/svod/backend/.venv`

---

## 1) Обновление кода из Git

Проверить статус и ветку:

```bash
cd /home/user/svod
git status
git branch -vv
```

Подтянуть обновления (делайте в обеих папках, если так удобнее):

```bash
cd /home/user/svod/backend
git pull

cd /home/user/svod/svod-command-center
git pull
```

Проверить, что подтянулось последнее:

```bash
cd /home/user/svod
git log -5 --oneline
```

---

## 2) Backend (FastAPI / uvicorn)

### 2.1 Включить виртуальное окружение

```bash
cd /home/user/svod/backend
source /home/user/svod/backend/.venv/bin/activate
```

### 2.2 Установить зависимости (если нужно)

```bash
cd /home/user/svod/backend
source /home/user/svod/backend/.venv/bin/activate
pip install -r /home/user/svod/backend/requirements.txt
```

### 2.3 Перезапуск (ручной запуск)

Если backend уже запущен и занимает порт 8000 — найдите процесс:

```bash
sudo lsof -nP -iTCP:8000 -sTCP:LISTEN
```

Остановить (вариант 1: по PID из lsof):

```bash
sudo kill -TERM <PID>
```

Остановить (вариант 2: грубо по имени процесса):

```bash
pkill -f "uvicorn app.main:app"
```

Запуск (как вы делали):

```bash
cd /home/user/svod/backend
source /home/user/svod/backend/.venv/bin/activate
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Запуск в dev-режиме с авто-перезагрузкой:

```bash
cd /home/user/svod/backend
source /home/user/svod/backend/.venv/bin/activate
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2.4 Запуск в фоне (если не используете systemd)

Через `nohup`:

```bash
cd /home/user/svod/backend
source /home/user/svod/backend/.venv/bin/activate
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /home/user/svod/backend/uvicorn.log 2>&1 &
```

Смотреть лог:

```bash
tail -n 200 -f /home/user/svod/backend/uvicorn.log
```

---

## 3) Frontend (Vite)

### 3.1 Установка зависимостей (если нужно)

```bash
cd /home/user/svod/svod-command-center
npm install
```

### 3.2 Запуск dev-сервера (как вы делали)

```bash
cd /home/user/svod/svod-command-center
npm run dev -- --host 0.0.0.0 --port 5173
```

### 3.3 Запуск в фоне

```bash
cd /home/user/svod/svod-command-center
nohup npm run dev -- --host 0.0.0.0 --port 5173 > /home/user/svod/svod-command-center/vite.log 2>&1 &
```

Лог:

```bash
tail -n 200 -f /home/user/svod/svod-command-center/vite.log
```

---

## 4) Быстрая проверка доступности

Порты:

```bash
sudo lsof -nP -iTCP:8000 -sTCP:LISTEN
sudo lsof -nP -iTCP:5173 -sTCP:LISTEN
```

Проверка API:

```bash
curl -sS http://127.0.0.1:8000/health || true
curl -sS http://127.0.0.1:8000/docs | head
```

Если нет `/health`, просто проверьте `/docs`:

```bash
curl -sS -I http://127.0.0.1:8000/docs
```

Проверка фронта:

```bash
curl -sS -I http://127.0.0.1:5173/
```

---

## 5) Полезные URL

- Backend Swagger: `http://<IP_ВМ>:8000/docs`
- Frontend (dev): `http://<IP_ВМ>:5173`

---

## 6) Типовые проблемы

### 6.1 «Порт занят»

```bash
sudo lsof -nP -iTCP:8000 -sTCP:LISTEN
sudo lsof -nP -iTCP:5173 -sTCP:LISTEN
```

### 6.2 «После обновления в БД не хватает колонок»

В проекте есть авто-обновление схемы при старте (без миграций). Обычно достаточно перезапустить backend.

### 6.3 «Node/Python версии»

```bash
python3 --version
node --version
npm --version
```

---

## 7) (Опционально) Systemd-шаблон (если захотите сделать красиво)

Проверка сервисов (если они у вас уже заведены):

```bash
sudo systemctl status svod-backend
sudo systemctl status svod-frontend
```

Перезапуск:

```bash
sudo systemctl restart svod-backend
sudo systemctl restart svod-frontend
```

Логи:

```bash
sudo journalctl -u svod-backend -n 200 -f
sudo journalctl -u svod-frontend -n 200 -f
```
