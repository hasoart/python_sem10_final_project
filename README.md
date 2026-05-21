# Object Detection Service

Backend-сервис для асинхронной детекции объектов на изображениях.

Пользователь загружает фотографии, затем создает задачу обработки из нужных `photo_id`. API кладет задачу в очередь Redis, Celery worker запускает YOLO, сохраняет результаты в PostgreSQL и annotated preview в MinIO.

## Стек

- FastAPI
- PostgreSQL
- SQLAlchemy + Alembic
- MinIO
- Redis
- Celery
- Ultralytics YOLO
- pytest

## Быстрый запуск через Docker Compose

Скопировать пример env:

```bash
cp .env.example .env
```

Запустить все сервисы:

```bash
sudo docker compose up --build
```

Compose поднимет:

- `api` на `http://localhost:8000`
- `worker`
- `migrate`, который применит Alembic-миграции и завершится
- `postgres`, опубликованный наружу на `localhost:5433`
- `redis`
- `minio` на `http://localhost:9000`
- MinIO console на `http://localhost:9001`

При первом запуске worker может скачать веса YOLO, если файла из `YOLO_MODEL_PATH` еще нет в контейнере.

Swagger UI:

```text
http://localhost:8000/docs
```

MinIO login/password по умолчанию:

```text
minioadmin / minioadmin
```

Если какой-то порт уже занят, поменять его можно в `.env`. Например:

```env
POSTGRES_PORT=5434
DATABASE_URL="postgresql+psycopg://app:app@localhost:5434/object_detection"
```

Для полного запуска в Docker Compose `DATABASE_URL` внутри `api`, `worker` и `migrate` все равно будет указывать на `postgres:5432`; внешний порт нужен только для подключения с хоста.

## Локальный запуск без контейнера API

Инфраструктура:

```bash
docker compose up -d postgres redis minio minio-create-bucket
```

Миграции:

```bash
uv run alembic upgrade head
```

API:

```bash
uv run uvicorn app.main:app --reload
```

Worker:

```bash
uv run celery -A app.worker.celery_app:celery_app worker --loglevel=info
```

## Как пользоваться API

1. Загрузить фотографию:

```bash
curl -X POST http://localhost:8000/photos \
  -F "file=@/path/to/image.jpg"
```

Ответ:

```json
{
  "photo_id": "..."
}
```

2. Создать задачу обработки из одной или нескольких фотографий:

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"photo_ids": ["PHOTO_ID_1", "PHOTO_ID_2"]}'
```

Ответ:

```json
{
  "task_id": "...",
  "photo_ids": ["PHOTO_ID_1", "PHOTO_ID_2"]
}
```

3. Проверить статус задачи:

```bash
curl http://localhost:8000/tasks/TASK_ID
```

4. Получить результаты детекции:

```bash
curl http://localhost:8000/tasks/TASK_ID/results
```

Если задача еще не завершена, endpoint вернет `202 Accepted`.

5. Получить original/preview image:

```text
GET /photos/{photo_id}/file
GET /photos/{photo_id}/preview
```

## Как это работает

1. `POST /photos` сохраняет файл в MinIO и создает запись `Photo` в PostgreSQL.
2. `POST /tasks` принимает список `photo_id`, создает `Task`, привязывает фотографии к задаче и ставит task в Redis-очередь.
3. Celery worker берет task из очереди.
4. Worker скачивает фотографии из MinIO.
5. YOLO находит объекты.
6. Worker сохраняет detections в `photos.detections`.
7. Worker сохраняет annotated preview в MinIO.
8. Статус task становится `completed`.

## Тесты

```bash
uv run pytest
```

Подробнее: [docs/testing.md](docs/testing.md).

## Миграции

```bash
uv run alembic upgrade head
```

Подробнее: [docs/migrations.md](docs/migrations.md).
