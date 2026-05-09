# Search Service

FastAPI-сервис системы Digital Cemetery System для сбора релевантной публичной информации о человеке. Формирует поисковый запрос, запускает Yandex Search API, скачивает найденные страницы, очищает HTML, извлекает релевантные текстовые фрагменты и сохраняет результат в SQLite для дальнейшей генерации биографии.

## Стек

- Python 3.11;
- FastAPI;
- Pydantic;
- Uvicorn;
- Yandex Search API;
- Requests;
- BeautifulSoup;
- SQLite для задач и найденных записей;
- Prometheus FastAPI Instrumentator.

## Пайплайн поиска

1. Принять параметры поиска: ФИО, город, даты, кладбище, дополнительные слова.
2. Сформировать поисковый запрос.
3. Запустить asynchronous Yandex Search API operation.
4. Дождаться результата операции и извлечь ссылки из HTML-ответа.
5. Скачать найденные страницы.
6. Очистить HTML от служебных блоков.
7. Выделить релевантные строки по ФИО, ключевым словам и датам.
8. Сохранить source record и job logs в SQLite.

## API

| Метод | Путь | Назначение |
| --- | --- | --- |
| `GET` | `/health` | Healthcheck сервиса |
| `GET` | `/metrics` | Prometheus metrics |
| `POST` | `/api/search/jobs` | Создать фоновую задачу поиска |
| `GET` | `/api/search/jobs/{job_id}` | Получить статус, logs и результат задачи |
| `GET` | `/api/search/records` | Список сохранённых source records |
| `GET` | `/api/search/records/{record_id}` | Детали source record с релевантным текстом |
| `GET` | `/api/search/records/{record_id}/download` | Скачать релевантный текст как `.txt` |

Swagger UI доступен на `http://localhost:8082/swagger-ui`, OpenAPI docs - на `http://localhost:8082/api-docs`.

Через API Gateway сервис доступен по префиксу `http://localhost:8080/api/search/**`. В gateway этот префикс защищён ролью `ADMIN`.

## Локальный запуск всей системы

Полный локальный контур запускается из репозитория `ops-monitoring`:

```powershell
cd D:\NSU\Diploma\DigitalCemeterySystem\ops-monitoring
docker compose -f compose/docker-compose.local.yml --env-file .env.local up -d --build
```

В этом режиме:

- `SEARCH_DB_PATH=/data/search.db`;
- SQLite хранится в Docker volume `search_data`;
- `YANDEX_API_KEY` и `YANDEX_FOLDER_ID` берутся из `ops-monitoring/.env.local`.

## Standalone-запуск

PowerShell:

```powershell
cd D:\NSU\Diploma\DigitalCemeterySystem\search-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:SEARCH_DB_PATH = 'data/search.db'
$env:YANDEX_API_KEY = '<your-yandex-api-key>'
$env:YANDEX_FOLDER_ID = '<your-yandex-folder-id>'
uvicorn app.main:app --host 0.0.0.0 --port 8082 --reload
```

Bash:

```bash
cd search-service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
SEARCH_DB_PATH=data/search.db \
YANDEX_API_KEY='<your-yandex-api-key>' \
YANDEX_FOLDER_ID='<your-yandex-folder-id>' \
uvicorn app.main:app --host 0.0.0.0 --port 8082 --reload
```

## Переменные окружения

| Переменная | Значение по умолчанию | Назначение |
| --- | --- | --- |
| `SEARCH_DB_PATH` | `data/search.db` | Путь к SQLite базе задач и source records |
| `YANDEX_API_KEY` | empty | API key для Yandex Search API |
| `YANDEX_FOLDER_ID` | empty | Folder ID Yandex Cloud |
| `SEARCH_DEFAULT_LIMIT` | `5` | Лимит ссылок по умолчанию |
| `SEARCH_MAX_LIMIT` | `10` | Максимальный лимит ссылок |
| `SEARCH_PAGE_TIMEOUT_SECONDS` | `12` | Timeout скачивания страницы |
| `YANDEX_TIMEOUT_SECONDS` | `60` | Timeout ожидания Yandex operation |
| `YANDEX_POLL_INTERVAL_SECONDS` | `2` | Интервал polling Yandex operation |

Если `YANDEX_API_KEY` или `YANDEX_FOLDER_ID` не задан, search job завершится ошибкой.

## Проверка

```powershell
curl http://localhost:8082/health
curl http://localhost:8082/metrics
curl http://localhost:8082/api/search/records
```

Через gateway:

```powershell
curl http://localhost:8080/search-service/api-docs
```

Пример создания job напрямую из Windows PowerShell:

```powershell
$body = @{
  full_name = 'Иванов Иван Иванович'
  city = 'Новосибирск'
  cemetery = 'Южное кладбище'
  limit = 5
} | ConvertTo-Json
$body = -join ($body.ToCharArray() | ForEach-Object {
  if ([int][char]$_ -gt 127) { '\u{0:x4}' -f [int][char]$_ } else { $_ }
})

curl -Method POST http://localhost:8082/api/search/jobs `
  -ContentType 'application/json' `
  -Body ([System.Text.Encoding]::ASCII.GetBytes($body))
```

## Тесты

Команды запускаются из корня `search-service`. Если в трассировке виден путь вида `C:\Python314\...`, используется системный Python без зависимостей сервиса; нужно активировать `.venv` или запускать Python из неё.

```powershell
cd D:\NSU\Diploma\DigitalCemeterySystem\search-service
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m unittest discover -s tests
```

## Сборка Docker-образа

```powershell
docker build -t dcs-search-service .
```

Контейнер слушает порт `8082`.
