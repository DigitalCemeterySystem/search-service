import base64
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from app.config import settings


SEARCH_API_URL = "https://searchapi.api.cloud.yandex.net/v2/web/searchAsync"
OPERATIONS_URL = "https://operation.api.cloud.yandex.net/operations/"


class YandexSearchError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    if not settings.yandex_api_key:
        raise YandexSearchError("YANDEX_API_KEY не задан.")
    return {
        "Authorization": f"Api-Key {settings.yandex_api_key}",
        "Content-Type": "application/json",
    }


def _decode_rawdata(raw_base64: str) -> str:
    return base64.b64decode(raw_base64).decode("utf-8", errors="replace")


def _extract_links_from_html(html: str, limit: int) -> list[dict[str, str | None]]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[dict[str, str | None]] = []
    seen_urls: set[str] = set()
    seen_domains: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        parsed = urlparse(href)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        domain = parsed.netloc.lower()
        if any(bad in domain for bad in ("yandex", "ya.ru", "yastatic", "zen.yandex")):
            continue
        if href in seen_urls or domain in seen_domains:
            continue
        seen_urls.add(href)
        seen_domains.add(domain)
        links.append({"url": href, "title": a.get_text(" ", strip=True) or None})
        if len(links) >= limit:
            break

    return links


def search_web(query: str, limit: int) -> list[dict[str, str | None]]:
    if not settings.yandex_folder_id:
        raise YandexSearchError("YANDEX_FOLDER_ID не задан.")

    body = {
        "query": {
            "searchType": "SEARCH_TYPE_RU",
            "queryText": query,
        },
        "folderId": settings.yandex_folder_id,
        "responseFormat": "FORMAT_HTML",
        "userAgent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
        ),
    }

    response = requests.post(SEARCH_API_URL, headers=_headers(), json=body, timeout=30)
    response.raise_for_status()
    operation_id = response.json().get("id")
    if not operation_id:
        raise YandexSearchError(f"Yandex Search API не вернул operation id: {response.text[:500]}")

    start = time.time()
    result_json = None
    while time.time() - start < settings.yandex_timeout_seconds:
        status_response = requests.get(OPERATIONS_URL + operation_id, headers=_headers(), timeout=20)
        status_response.raise_for_status()
        status = status_response.json()
        if status.get("done"):
            result_json = status
            break
        time.sleep(settings.yandex_poll_interval_seconds)

    if not result_json:
        raise YandexSearchError("Истекло время ожидания результата от Yandex Search API.")

    raw_b64 = (result_json.get("response") or {}).get("rawData")
    if not raw_b64:
        raise YandexSearchError("В ответе Yandex Search API нет rawData.")

    return _extract_links_from_html(_decode_rawdata(raw_b64), limit=limit)


def download_page(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=settings.page_timeout_seconds)
    if response.status_code >= 400:
        return ""
    response.encoding = response.apparent_encoding or response.encoding
    return response.text
