import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


class SearchStorage:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL,
                    query TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    urls_json TEXT NOT NULL,
                    relevant_text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    query TEXT,
                    urls_json TEXT NOT NULL,
                    record_id INTEGER,
                    logs_json TEXT NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def create_job(self, job_id: str, request: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        row = {
            "id": job_id,
            "status": "pending",
            "stage": "created",
            "request": request,
            "query": None,
            "urls": [],
            "record_id": None,
            "logs": [],
            "error": None,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (id, status, stage, request_json, query, urls_json, record_id, logs_json, error, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row["status"],
                    row["stage"],
                    json.dumps(row["request"], ensure_ascii=False),
                    row["query"],
                    json.dumps(row["urls"], ensure_ascii=False),
                    row["record_id"],
                    json.dumps(row["logs"], ensure_ascii=False),
                    row["error"],
                    row["created_at"],
                    row["updated_at"],
                ),
            )
        return row

    def append_log(self, job_id: str, stage: str, level: str, message: str) -> None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT logs_json FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if not row:
                return
            logs = json.loads(row["logs_json"])
            logs.append(
                {
                    "timestamp": utc_now(),
                    "stage": stage,
                    "level": level,
                    "message": message,
                }
            )
            conn.execute(
                "UPDATE jobs SET stage = ?, logs_json = ?, updated_at = ? WHERE id = ?",
                (stage, json.dumps(logs, ensure_ascii=False), utc_now(), job_id),
            )

    def update_job(self, job_id: str, **values: Any) -> None:
        allowed = {
            "status": "status",
            "stage": "stage",
            "query": "query",
            "urls": "urls_json",
            "record_id": "record_id",
            "error": "error",
        }
        assignments: list[str] = []
        params: list[Any] = []
        for key, value in values.items():
            if key not in allowed:
                continue
            column = allowed[key]
            assignments.append(f"{column} = ?")
            if key == "urls":
                params.append(json.dumps(value, ensure_ascii=False))
            else:
                params.append(value)
        assignments.append("updated_at = ?")
        params.append(utc_now())
        params.append(job_id)
        with self._lock, self._connect() as conn:
            conn.execute(f"UPDATE jobs SET {', '.join(assignments)} WHERE id = ?", params)

    def create_record(
        self,
        full_name: str,
        query: str,
        request: dict[str, Any],
        urls: list[dict[str, Any]],
        relevant_text: str,
    ) -> int:
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO records (full_name, query, request_json, urls_json, relevant_text, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    full_name,
                    query,
                    json.dumps(request, ensure_ascii=False),
                    json.dumps(urls, ensure_ascii=False),
                    relevant_text,
                    utc_now(),
                ),
            )
            return int(cursor.lastrowid)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._job_from_row(row) if row else None

    def list_records(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT * FROM records ORDER BY created_at DESC").fetchall()
        return [self._record_from_row(row, include_text=False) for row in rows]

    def get_record(self, record_id: int, include_text: bool = True) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
        return self._record_from_row(row, include_text=include_text) if row else None

    def _job_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        record = self.get_record(row["record_id"]) if row["record_id"] else None
        return {
            "id": row["id"],
            "status": row["status"],
            "stage": row["stage"],
            "request": json.loads(row["request_json"]),
            "query": row["query"],
            "urls": json.loads(row["urls_json"]),
            "record_id": row["record_id"],
            "relevant_preview": record["relevant_preview"] if record else None,
            "relevant_text_length": record["relevant_text_length"] if record else 0,
            "logs": json.loads(row["logs_json"]),
            "error": row["error"],
            "created_at": parse_dt(row["created_at"]),
            "updated_at": parse_dt(row["updated_at"]),
        }

    def _record_from_row(self, row: sqlite3.Row, include_text: bool) -> dict[str, Any]:
        relevant_text = row["relevant_text"]
        data = {
            "id": row["id"],
            "full_name": row["full_name"],
            "query": row["query"],
            "request": json.loads(row["request_json"]),
            "urls": json.loads(row["urls_json"]),
            "relevant_preview": make_preview(relevant_text),
            "relevant_text_length": len(relevant_text),
            "created_at": parse_dt(row["created_at"]),
        }
        if include_text:
            data["relevant_text"] = relevant_text
        return data


def make_preview(text: str, limit: int = 800) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip() + "..."
