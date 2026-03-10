import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "non_voip_numbers.db")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Storage:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or os.environ.get("NUMBER_APP_DB_PATH", DEFAULT_DB_PATH)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS managed_numbers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    phone_number TEXT NOT NULL UNIQUE,
                    provider_number_id TEXT,
                    line_type TEXT DEFAULT 'unknown',
                    status TEXT DEFAULT 'active',
                    metadata_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS message_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    from_number TEXT NOT NULL,
                    to_number TEXT NOT NULL,
                    body TEXT NOT NULL,
                    status TEXT NOT NULL,
                    provider_message_id TEXT,
                    response_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS call_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    from_number TEXT NOT NULL,
                    to_number TEXT NOT NULL,
                    say_text TEXT DEFAULT '',
                    status TEXT NOT NULL,
                    provider_call_id TEXT,
                    response_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """
            )

    def list_numbers(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, provider, phone_number, provider_number_id, line_type, status,
                       metadata_json, created_at, updated_at
                FROM managed_numbers
                ORDER BY created_at DESC
                """
            ).fetchall()
        output: list[dict[str, Any]] = []
        for row in rows:
            row_dict = dict(row)
            row_dict["metadata"] = json.loads(row_dict.pop("metadata_json") or "{}")
            output.append(row_dict)
        return output

    def get_number(self, number_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, provider, phone_number, provider_number_id, line_type, status,
                       metadata_json, created_at, updated_at
                FROM managed_numbers
                WHERE id = ?
                """,
                (number_id,),
            ).fetchone()
        if row is None:
            return None
        row_dict = dict(row)
        row_dict["metadata"] = json.loads(row_dict.pop("metadata_json") or "{}")
        return row_dict

    def upsert_number(
        self,
        provider: str,
        phone_number: str,
        provider_number_id: str | None,
        line_type: str = "unknown",
        status: str = "active",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        metadata_json = json.dumps(metadata or {})
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO managed_numbers (
                    provider, phone_number, provider_number_id, line_type, status,
                    metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(phone_number) DO UPDATE SET
                    provider = excluded.provider,
                    provider_number_id = excluded.provider_number_id,
                    line_type = excluded.line_type,
                    status = excluded.status,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    provider,
                    phone_number,
                    provider_number_id,
                    line_type,
                    status,
                    metadata_json,
                    now,
                    now,
                ),
            )
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM managed_numbers WHERE phone_number = ?",
                (phone_number,),
            ).fetchone()
        if row is None:
            raise RuntimeError("Failed to persist managed number.")
        row_dict = dict(row)
        row_dict["metadata"] = json.loads(row_dict.pop("metadata_json") or "{}")
        return row_dict

    def remove_number(self, number_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM managed_numbers WHERE id = ?", (number_id,))

    def log_message(
        self,
        provider: str,
        from_number: str,
        to_number: str,
        body: str,
        status: str,
        provider_message_id: str | None,
        response: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO message_logs (
                    provider, from_number, to_number, body, status,
                    provider_message_id, response_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    provider,
                    from_number,
                    to_number,
                    body,
                    status,
                    provider_message_id,
                    json.dumps(response or {}),
                    utc_now(),
                ),
            )

    def log_call(
        self,
        provider: str,
        from_number: str,
        to_number: str,
        say_text: str,
        status: str,
        provider_call_id: str | None,
        response: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO call_logs (
                    provider, from_number, to_number, say_text, status,
                    provider_call_id, response_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    provider,
                    from_number,
                    to_number,
                    say_text,
                    status,
                    provider_call_id,
                    json.dumps(response or {}),
                    utc_now(),
                ),
            )

