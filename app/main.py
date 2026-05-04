import uuid
from typing import Annotated

from fastapi import BackgroundTasks, FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.extractor import build_query, clean_html, extract_relevant_info, trim_combined_text
from app.schemas import (
    HealthResponse,
    RelevantInfoRecord,
    RelevantInfoRecordDetail,
    SearchJobResponse,
    SearchRequest,
)
from app.storage import SearchStorage
from app.yandex_client import download_page, search_web


app = FastAPI(
    title=settings.service_title,
    version="1.0.0",
    docs_url="/swagger-ui",
    openapi_url="/api-docs",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

storage = SearchStorage(settings.db_path)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/api/search/jobs", response_model=SearchJobResponse, status_code=202, tags=["search"])
def create_search_job(request: SearchRequest, background_tasks: BackgroundTasks) -> dict:
    normalized = request.model_dump()
    normalized["limit"] = min(normalized["limit"], settings.max_search_limit)
    job_id = str(uuid.uuid4())
    storage.create_job(job_id, normalized)
    background_tasks.add_task(run_search_job, job_id, SearchRequest(**normalized))
    return storage.get_job(job_id)


@app.get("/api/search/jobs/{job_id}", response_model=SearchJobResponse, tags=["search"])
def get_search_job(job_id: str) -> dict:
    job = storage.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Search job not found")
    return job


@app.get("/api/search/records", response_model=list[RelevantInfoRecord], tags=["records"])
def list_records() -> list[dict]:
    return storage.list_records()


@app.get("/api/search/records/{record_id}", response_model=RelevantInfoRecordDetail, tags=["records"])
def get_record(record_id: Annotated[int, Path(ge=1)]) -> dict:
    record = storage.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Relevant information record not found")
    return record


@app.get("/api/search/records/{record_id}/download", response_class=PlainTextResponse, tags=["records"])
def download_record(record_id: Annotated[int, Path(ge=1)]) -> PlainTextResponse:
    record = storage.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Relevant information record not found")
    filename = f"relevant-info-{record_id}.txt"
    return PlainTextResponse(
        record["relevant_text"],
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def log(job_id: str, stage: str, level: str, message: str) -> None:
    storage.append_log(job_id, stage, level, message)


def run_search_job(job_id: str, request: SearchRequest) -> None:
    try:
        storage.update_job(job_id, status="running", stage="search")
        query = build_query(
            request.full_name,
            city=request.city,
            birth_date=request.birth_date,
            death_date=request.death_date,
            cemetery=request.cemetery,
            extra_terms=request.extra_terms,
        )
        storage.update_job(job_id, query=query)
        log(job_id, "search", "info", f"Сформирован поисковый запрос: {query}")

        urls = search_web(query, limit=request.limit)
        storage.update_job(job_id, urls=urls)
        if not urls:
            raise RuntimeError("Yandex Search API не вернул подходящие ссылки.")
        log(job_id, "search", "success", f"Найдено страниц: {len(urls)}")
        for index, item in enumerate(urls, start=1):
            log(job_id, "search", "info", f"{index}. {item['url']}")

        storage.update_job(job_id, stage="parse")
        combined_sections: list[str] = []
        for index, item in enumerate(urls, start=1):
            url = item["url"]
            log(job_id, "parse", "info", f"Скачивание страницы {index}/{len(urls)}: {url}")
            try:
                html = download_page(url)
            except Exception as exc:
                log(job_id, "parse", "warning", f"Не удалось скачать страницу: {exc}")
                continue
            if not html:
                log(job_id, "parse", "warning", "Страница не вернула доступный HTML-текст.")
                continue
            text = clean_html(html)
            log(job_id, "parse", "success", f"Получено символов после очистки: {len(text)}")

            storage.update_job(job_id, stage="extract")
            relevant = extract_relevant_info(
                text,
                request.full_name,
                extra_keywords=[request.city or "", request.cemetery or "", request.extra_terms or ""],
            )
            if relevant.strip():
                combined_sections.append(f"Источник: {url}\n{relevant.strip()}")
                log(job_id, "extract", "success", f"Извлечено релевантных символов: {len(relevant)}")
            else:
                log(job_id, "extract", "warning", "На странице не найдено релевантных фрагментов.")

        combined_text = trim_combined_text("\n\n---\n\n".join(combined_sections).strip())
        if not combined_text:
            raise RuntimeError("Не удалось собрать релевантную информацию по найденным страницам.")

        record_id = storage.create_record(
            full_name=request.full_name,
            query=query,
            request=request.model_dump(),
            urls=urls,
            relevant_text=combined_text,
        )
        storage.update_job(job_id, status="succeeded", stage="done", record_id=record_id)
        log(job_id, "done", "success", f"Релевантная информация сохранена, запись #{record_id}.")
    except Exception as exc:
        storage.update_job(job_id, status="failed", stage="failed", error=str(exc))
        log(job_id, "failed", "error", str(exc))
