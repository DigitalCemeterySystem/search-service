import os


class Settings:
    service_title = "DCS Search Service"
    db_path = os.getenv("SEARCH_DB_PATH", "data/search.db")
    yandex_api_key = os.getenv("YANDEX_API_KEY", "")
    yandex_folder_id = os.getenv("YANDEX_FOLDER_ID", "")
    default_search_limit = int(os.getenv("SEARCH_DEFAULT_LIMIT", "5"))
    max_search_limit = int(os.getenv("SEARCH_MAX_LIMIT", "10"))
    page_timeout_seconds = int(os.getenv("SEARCH_PAGE_TIMEOUT_SECONDS", "12"))
    yandex_timeout_seconds = int(os.getenv("YANDEX_TIMEOUT_SECONDS", "60"))
    yandex_poll_interval_seconds = float(os.getenv("YANDEX_POLL_INTERVAL_SECONDS", "2"))


settings = Settings()
