# SVOD backend on Windows Server (service + auto-restart)

Эти скрипты предназначены для сервера Windows, где репозиторий уже лежит (например `C:\svod\SVOD_SOFT`) и обновляется через `git pull`.

Что дают:
- Backend как служба Windows (через NSSM): автозапуск после перезагрузки + автоперезапуск при падении.
- Авто-«подхват обновлений» после `git pull`: планировщик (Task Scheduler) раз в минуту проверяет изменился ли `HEAD`, и если да — перезапускает службу (и при необходимости обновляет зависимости).

Важно про адреса:
- `127.0.0.1` / `localhost` — это ТОЛЬКО текущая машина.
- Если открываешь фронт/бек с другого ПК, используй `http://<IP_СЕРВЕРА>:PORT`.

Важно:
- Секреты НЕ коммитятся. На сервере должен быть файл `backend\.env`.
- Скрипты требуют запуска от Администратора.

Файлы:
- `setup_backend_service_nssm.ps1` — установка/обновление службы backend через NSSM.
- `uninstall_backend_service.ps1` — удаление службы.
- `setup_frontend_service_nssm.ps1` — установка/обновление службы frontend (build + preview) через NSSM.
- `uninstall_frontend_service.ps1` — удаление службы frontend.
- `install_update_watcher_task.ps1` — установка задачи-проверки обновлений.
- `uninstall_update_watcher_task.ps1` — удаление задачи.
- `watch_repo_and_restart.ps1` — логика проверки `git HEAD` и рестарта.
- `restart_backend_service.ps1` — ручной рестарт службы.

Пример установки службы:

`powershell -NoProfile -ExecutionPolicy Bypass -File C:\svod\SVOD_SOFT\scripts\server\windows\setup_backend_service_nssm.ps1 -RepoRoot C:\svod\SVOD_SOFT -NssmExe C:\tools\nssm\nssm.exe -ServiceName SVOD-Backend -BindHost 0.0.0.0 -Port 8000`

Пример установки фронтенда (preview, порт 4173):

`powershell -NoProfile -ExecutionPolicy Bypass -File C:\svod\SVOD_SOFT\scripts\server\windows\setup_frontend_service_nssm.ps1 -RepoRoot C:\svod\SVOD_SOFT -NssmExe C:\tools\nssm\nssm.exe -ServiceName SVOD-Frontend -BindHost 0.0.0.0 -Port 4173`
