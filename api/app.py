"""Shared Study Planner reminder API backed by PostgreSQL."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

try:
    import psycopg  # type: ignore[import-not-found]
    from psycopg.rows import dict_row  # type: ignore[import-not-found]
except ModuleNotFoundError:  # Keep validation tests runnable without the DB driver.
    psycopg: Any = None
    dict_row: Any = None

ROOT = Path(__file__).parent
MIGRATION = (ROOT / "migrations" / "001_reminders.sql").read_text()
ID_RE = re.compile(r"^[0-9]+$")
FIELDS = {"title", "details", "remind_at", "completed"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("must be an RFC3339 timestamp or null")
    raw = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        raise ValueError("must include a timezone")
    return parsed.astimezone(timezone.utc)


def rfc3339(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z") if value else None


def reminder(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "details": row["details"],
        "remind_at": rfc3339(row["remind_at"]),
        "completed": row["completed"],
        "created_at": rfc3339(row["created_at"]),
        "updated_at": rfc3339(row["updated_at"]),
    }


def db_kwargs() -> dict[str, Any]:
    return {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.getenv("DB_NAME", "study_planner"),
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
    }


def migrate() -> None:
    with psycopg.connect(**db_kwargs()) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("study-planner:migrations",))
            cur.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())")
            cur.execute("SELECT 1 FROM schema_migrations WHERE version = %s", ("001_reminders",))
            if cur.fetchone() is None:
                cur.execute(MIGRATION)
                cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", ("001_reminders",))


def connect():
    if psycopg is None or dict_row is None:
        raise RuntimeError("psycopg is required for database operations")
    return psycopg.connect(**db_kwargs(), row_factory=dict_row)


def validate_id(raw: str) -> int:
    if not ID_RE.fullmatch(raw):
        raise ValueError("id must be an unsigned decimal string")
    return int(raw)


def validate_payload(payload: Any, partial: bool) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    unknown = set(payload) - FIELDS
    if unknown:
        raise ValueError(f"unknown field: {sorted(unknown)[0]}")
    if partial and not payload:
        raise ValueError("patch must not be empty")
    if not partial and "title" not in payload:
        raise ValueError("title is required")
    if not partial:
        payload.setdefault("details", None)
        payload.setdefault("remind_at", None)
    if "title" in payload:
        if not isinstance(payload["title"], str) or not payload["title"].strip():
            raise ValueError("title must not be blank")
        payload["title"] = payload["title"].strip()
    for field in ("details", "remind_at"):
        if field in payload and payload[field] is not None and not isinstance(payload[field], str):
            raise ValueError(f"{field} must be a string or null")
    if "remind_at" in payload:
        try:
            payload["remind_at"] = timestamp(payload["remind_at"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"remind_at {exc}") from exc
    if "completed" in payload and not isinstance(payload["completed"], bool):
        raise ValueError("completed must be a boolean")
    return payload


class Handler(BaseHTTPRequestHandler):
    server_version = "study-planner-api/1"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def send_json(self, status: int, value: Any) -> None:
        body = json.dumps(value, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def error(self, status: int, code: str, message: str, details: dict[str, str] | None = None) -> None:
        error: dict[str, Any] = {"code": code, "message": message}
        if details:
            error["details"] = details
        self.send_json(status, {"error": error})

    def body(self) -> Any:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValueError("Content-Length must be a non-negative integer") from exc
        if length < 0:
            raise ValueError("Content-Length must be a non-negative integer")
        if length > 1_000_000:
            raise ValueError("request body is too large")
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as exc:
            raise ValueError("request body must be valid JSON") from exc

    def do_GET(self) -> None:
        try:
            if self.path == "/api/healthz":
                try:
                    with connect() as conn:
                        conn.execute("SELECT 1")
                    self.send_json(200, {"status": "ok"})
                except Exception:
                    self.error(503, "service_unavailable", "database is not ready")
                return
            if self.path not in ("/api/reminders", "/api/reminders/due"):
                self.error(404, "not_found", "resource not found")
                return
            due = self.path.endswith("/due")
            query = "SELECT id,title,details,remind_at,completed,created_at,updated_at FROM reminders "
            query += "WHERE completed = FALSE AND remind_at <= %(now)s " if due else ""
            query += "ORDER BY remind_at ASC NULLS LAST, id ASC"
            with connect() as conn:
                rows = conn.execute(query, {"now": now_utc()}).fetchall()
            self.send_json(200, [reminder(row) for row in rows])
        except Exception:
            self.error(500, "internal_error", "storage operation failed")

    def do_POST(self) -> None:
        if self.path != "/api/reminders":
            self.error(404, "not_found", "resource not found")
            return
        try:
            data = validate_payload(self.body(), partial=False)
            with connect() as conn:
                row = conn.execute("""INSERT INTO reminders (title,details,remind_at) VALUES (%(title)s,%(details)s,%(remind_at)s) RETURNING id,title,details,remind_at,completed,created_at,updated_at""", data).fetchone()
            self.send_json(201, reminder(row))
        except ValueError as exc:
            self.error(400, "validation_error", str(exc))
        except Exception:
            self.error(500, "internal_error", "storage operation failed")

    def do_PATCH(self) -> None:
        self.mutate("PATCH")

    def do_DELETE(self) -> None:
        self.mutate("DELETE")

    def mutate(self, method: str) -> None:
        prefix = "/api/reminders/"
        if not self.path.startswith(prefix):
            self.error(404, "not_found", "resource not found")
            return
        raw_id = self.path[len(prefix):]
        if not ID_RE.fullmatch(raw_id):
            self.error(404, "not_found", "reminder not found")
            return
        try:
            ident = validate_id(raw_id)
            data = validate_payload(self.body(), partial=True) if method == "PATCH" else {}
            with connect() as conn:
                if method == "DELETE":
                    cur = conn.execute("DELETE FROM reminders WHERE id = %s", (ident,))
                    if cur.rowcount == 0:
                        self.error(404, "not_found", "reminder not found")
                        return
                    self.send_response(204)
                    self.end_headers()
                    return
                assignments = ", ".join(f"{field} = %({field})s" for field in data)
                data["id"] = ident
                row = conn.execute(f"UPDATE reminders SET {assignments}, updated_at = now() WHERE id = %(id)s RETURNING id,title,details,remind_at,completed,created_at,updated_at", data).fetchone()
            if row is None:
                self.error(404, "not_found", "reminder not found")
                return
            self.send_json(200, reminder(row))
        except ValueError as exc:
            self.error(400, "validation_error", str(exc))
        except Exception:
            self.error(500, "internal_error", "storage operation failed")


def main() -> None:
    migrate()
    server = ThreadingHTTPServer((os.getenv("BIND_HOST", "127.0.0.1"), int(os.getenv("PORT", "8081"))), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
