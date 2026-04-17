# search-service

FastAPI-сервис поиска информации о человеке через Yandex Search API.

## Возможности

- запуск асинхронной задачи поиска;
- поэтапные логи: поиск, парсинг страниц, извлечение релевантной информации;
- сохранение найденной релевантной информации в SQLite;
- список сохраненных записей и скачивание результата `.txt`;
- Swagger UI: `http://localhost:8082/swagger-ui`.

## Переменные окружения

- `YANDEX_API_KEY` - API key Yandex Cloud;
- `YANDEX_FOLDER_ID` - folder id Yandex Cloud;
- `SEARCH_DB_PATH` - путь к SQLite-файлу, по умолчанию `data/search.db`.

## Локальный запуск

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8082 --reload
```
