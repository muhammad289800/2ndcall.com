import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _resolve_db_path() -> str:
    """Resolve SQLite DB path — prefer a Railway-style persistent volume mount at /data,
    then fall back to the NUMBER_APP_DB_PATH env var, then the app directory."""
    explicit = os.environ.get("NUMBER_APP_DB_PATH", "").strip()
    if explicit:
        os.makedirs(os.path.dirname(os.path.abspath(explicit)), exist_ok=True)
        return explicit
    # Railway persistent volume is typically mounted at /data
    if os.path.isdir("/data"):
        return "/data/non_voip_numbers.db"
    return os.path.join(BASE_DIR, "non_voip_numbers.db")

DEFAULT_DB_PATH = _resolve_db_path()


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
                    direction TEXT NOT NULL DEFAULT 'outbound',
                    from_number TEXT NOT NULL,
                    to_number TEXT NOT NULL,
                    body TEXT NOT NULL,
                    status TEXT NOT NULL,
                    provider_message_id TEXT,
                    event_type TEXT DEFAULT '',
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
                    direction TEXT NOT NULL DEFAULT 'outbound',
                    from_number TEXT NOT NULL,
                    to_number TEXT NOT NULL,
                    say_text TEXT DEFAULT '',
                    status TEXT NOT NULL,
                    provider_call_id TEXT,
                    event_type TEXT DEFAULT '',
                    response_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS wallet_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    amount REAL NOT NULL,
                    tx_type TEXT NOT NULL,
                    provider TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    reference_id TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS provider_webhook_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

            # Lightweight migrations for existing databases.
            self._ensure_column(conn, "message_logs", "direction", "TEXT NOT NULL DEFAULT 'outbound'")
            self._ensure_column(conn, "message_logs", "event_type", "TEXT DEFAULT ''")
            self._ensure_column(conn, "call_logs", "direction", "TEXT NOT NULL DEFAULT 'outbound'")
            self._ensure_column(conn, "call_logs", "event_type", "TEXT DEFAULT ''")

    def _ensure_column(
        self,
        conn: sqlite3.Connection,
        table: str,
        column: str,
        column_definition: str,
    ) -> None:
        existing = conn.execute(f"PRAGMA table_info({table})").fetchall()
        if any(row["name"] == column for row in existing):
            return
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_definition}")

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
        direction: str = "outbound",
        event_type: str = "",
        response: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO message_logs (
                    provider, direction, from_number, to_number, body, status,
                    provider_message_id, event_type, response_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    provider,
                    direction,
                    from_number,
                    to_number,
                    body,
                    status,
                    provider_message_id,
                    event_type,
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
        direction: str = "outbound",
        event_type: str = "",
        response: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO call_logs (
                    provider, direction, from_number, to_number, say_text, status,
                    provider_call_id, event_type, response_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    provider,
                    direction,
                    from_number,
                    to_number,
                    say_text,
                    status,
                    provider_call_id,
                    event_type,
                    json.dumps(response or {}),
                    utc_now(),
                ),
            )

    def list_message_logs(self, limit: int = 100, direction: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if direction:
                rows = conn.execute(
                    """
                    SELECT * FROM message_logs
                    WHERE direction = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (direction, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM message_logs
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        output: list[dict[str, Any]] = []
        for row in rows:
            row_dict = dict(row)
            row_dict["response"] = json.loads(row_dict.pop("response_json") or "{}")
            output.append(row_dict)
        return output

    def list_call_logs(self, limit: int = 100, direction: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if direction:
                rows = conn.execute(
                    """
                    SELECT * FROM call_logs
                    WHERE direction = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (direction, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM call_logs
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        output: list[dict[str, Any]] = []
        for row in rows:
            row_dict = dict(row)
            row_dict["response"] = json.loads(row_dict.pop("response_json") or "{}")
            output.append(row_dict)
        return output

    def record_webhook_event(self, provider: str, event_type: str, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO provider_webhook_events (provider, event_type, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (provider, event_type, json.dumps(payload), utc_now()),
            )

    def get_wallet_balance(self) -> float:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) AS balance FROM wallet_transactions"
            ).fetchone()
        return float(row["balance"] or 0.0)

    def list_wallet_transactions(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, amount, tx_type, provider, description, reference_id, created_at
                FROM wallet_transactions
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_wallet_transaction(
        self,
        amount: float,
        tx_type: str,
        provider: str = "",
        description: str = "",
        reference_id: str = "",
    ) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO wallet_transactions (
                    amount, tx_type, provider, description, reference_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (amount, tx_type, provider, description, reference_id, utc_now()),
            )
            row = conn.execute(
                """
                SELECT id, amount, tx_type, provider, description, reference_id, created_at
                FROM wallet_transactions
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            raise RuntimeError("Failed to create wallet transaction.")
        return dict(row)

    def top_up_wallet(self, amount: float, method: str = "manual") -> dict[str, Any]:
        if amount <= 0:
            raise ValueError("Top-up amount must be greater than zero.")
        tx = self.create_wallet_transaction(
            amount=amount,
            tx_type="topup",
            description=f"Wallet top-up via {method}",
        )
        return {"transaction": tx, "balance": self.get_wallet_balance()}

    def charge_wallet(
        self,
        amount: float,
        tx_type: str,
        provider: str,
        description: str,
        reference_id: str = "",
    ) -> dict[str, Any]:
        if amount <= 0:
            raise ValueError("Charge amount must be greater than zero.")
        balance = self.get_wallet_balance()
        if balance < amount:
            raise ValueError(
                f"Insufficient wallet balance. Required ${amount:.2f}, available ${balance:.2f}."
            )
        tx = self.create_wallet_transaction(
            amount=-amount,
            tx_type=tx_type,
            provider=provider,
            description=description,
            reference_id=reference_id,
        )
        return {"transaction": tx, "balance": self.get_wallet_balance()}

