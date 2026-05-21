## Запуск сервера

```shell
uv run uvicorn app.main:app --reload
```

## Запуск Celery

```shell
`uv run celery -A app.worker.celery_app:celery_app worker --loglevel=info
```
