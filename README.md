# FileManager

Веб-интерфейс находится в `frontend/`. Он использует API FastAPI и PostgreSQL из `app/`.

## Локальный запуск

Соберите интерфейс из корня проекта. Для сборки нужны Node.js 22.12+ и pnpm 11.

```powershell
cd frontend
pnpm install --frozen-lockfile
pnpm build
cd ../app
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Откройте [FileManager](http://127.0.0.1:8000/). FastAPI отдаёт собранный интерфейс из `frontend/dist`, поэтому сайт и API работают на одном адресе.

Для разработки с Vite оставьте FastAPI запущенным и выполните `pnpm dev` из `frontend/`. Интерфейс доступен на [127.0.0.1:5173](http://127.0.0.1:5173/). Если API запущен на другом адресе, задайте `FILEMANAGER_API_URL` в `frontend/.env.local`. При переопределении `ALLOWED_ORIGINS` в `app/.env` добавьте туда адрес Vite.
