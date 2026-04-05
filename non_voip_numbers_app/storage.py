import hashlib
import json
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Any


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _resolve_db_path() -> str:
    """Resolve SQLite DB path.
    Priority: NUMBER_APP_DB_PATH env var → /data (Railway persistent volume) → app directory.
    /data is created by Railway when a volume is mounted at that path, ensuring data
    survives redeployments, restarts, and scaling events."""
    explicit = os.environ.get("NUMBER_APP_DB_PATH", "").strip()
    if explicit:
        os.makedirs(os.path.dirname(os.path.abspath(explicit)), exist_ok=True)
        return explicit
    # Railway persistent volume is mounted at /data — always prefer it when present.
    if os.path.isdir("/data"):
        path = "/data/non_voip_numbers.db"
        print(f"[storage] Using persistent volume: {path}", flush=True)
        return path
    # Local / non-Railway fallback
    path = os.path.join(BASE_DIR, "non_voip_numbers.db")
    print(f"[storage] Warning: no persistent volume found. DB stored at {path} — data will be lost on redeploy!", flush=True)
    return path

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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    name TEXT DEFAULT '',
                    password_hash TEXT NOT NULL,
                    role TEXT DEFAULT 'user',
                    avatar_color TEXT DEFAULT '#1f6feb',
                    created_at TEXT NOT NULL,
                    last_login TEXT,
                    last_seen TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS payment_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    order_id TEXT NOT NULL UNIQUE,
                    paydify_txn_id TEXT DEFAULT '',
                    amount_usd REAL NOT NULL,
                    currency TEXT DEFAULT 'USDT',
                    status TEXT DEFAULT 'pending',
                    deeplink TEXT DEFAULT '',
                    from_address TEXT DEFAULT '',
                    tx_hash TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    paid_at TEXT,
                    metadata_json TEXT DEFAULT '{}'
                )
                """
            )
            # Lightweight migrations — safe to run on every startup, ignored if column exists
            self._ensure_column(conn, "message_logs", "direction", "TEXT NOT NULL DEFAULT 'outbound'")
            self._ensure_column(conn, "message_logs", "event_type", "TEXT DEFAULT ''")
            self._ensure_column(conn, "call_logs", "direction", "TEXT NOT NULL DEFAULT 'outbound'")
            self._ensure_column(conn, "call_logs", "event_type", "TEXT DEFAULT ''")
            # Users table migrations (for DBs created before the users feature)
            self._ensure_column(conn, "users", "avatar_color", "TEXT DEFAULT '#1f6feb'")
            self._ensure_column(conn, "users", "last_seen", "TEXT")
            # Per-user wallet: user_id = NULL means global/admin transaction
            self._ensure_column(conn, "wallet_transactions", "user_id", "INTEGER DEFAULT NULL")
            # Per-user number isolation
            self._ensure_column(conn, "managed_numbers", "user_id", "INTEGER DEFAULT NULL")

    # Allowed identifiers for _ensure_column — prevents SQL injection via dynamic DDL
    _ALLOWED_TABLES = frozenset({
        "managed_numbers", "message_logs", "call_logs",
        "wallet_transactions", "provider_webhook_events", "users", "payment_orders",
    })
    _ALLOWED_COLUMNS = frozenset({
        "direction", "event_type", "avatar_color", "last_seen",
        "user_id", "metadata_json",
    })

    def _ensure_column(
        self,
        conn: sqlite3.Connection,
        table: str,
        column: str,
        column_definition: str,
    ) -> None:
        if table not in self._ALLOWED_TABLES:
            raise ValueError(f"_ensure_column: disallowed table '{table}'")
        if column not in self._ALLOWED_COLUMNS:
            raise ValueError(f"_ensure_column: disallowed column '{column}'")
        existing = conn.execute(f"PRAGMA table_info({table})").fetchall()
        if any(row["name"] == column for row in existing):
            return
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_definition}")

    def list_numbers(self, user_id: int | None = None, admin: bool = False) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if admin or user_id is None:
                rows = conn.execute(
                    """
                    SELECT id, provider, phone_number, provider_number_id, line_type, status,
                           metadata_json, created_at, updated_at, user_id
                    FROM managed_numbers
                    ORDER BY created_at DESC
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, provider, phone_number, provider_number_id, line_type, status,
                           metadata_json, created_at, updated_at, user_id
                    FROM managed_numbers
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    """,
                    (user_id,),
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
        user_id: int | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        metadata_json = json.dumps(metadata or {})
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO managed_numbers (
                    provider, phone_number, provider_number_id, line_type, status,
                    metadata_json, created_at, updated_at, user_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(phone_number) DO UPDATE SET
                    provider = excluded.provider,
                    provider_number_id = excluded.provider_number_id,
                    line_type = excluded.line_type,
                    status = excluded.status,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at,
                    user_id = excluded.user_id
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
                    user_id,
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

    def transfer_number(self, number_id: int, from_user_id: int, to_user_id: int) -> dict[str, Any]:
        """Transfer a number from one user to another."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM managed_numbers WHERE id = ?", (number_id,)).fetchone()
            if not row:
                raise ValueError("Number not found.")
            row_dict = dict(row)
            if row_dict.get("user_id") != from_user_id:
                raise ValueError("You do not own this number.")
            # Verify target user exists
            target = conn.execute("SELECT id, email, name FROM users WHERE id = ?", (to_user_id,)).fetchone()
            if not target:
                raise ValueError("Target user not found.")
            conn.execute(
                "UPDATE managed_numbers SET user_id = ?, updated_at = ? WHERE id = ?",
                (to_user_id, utc_now(), number_id),
            )
            updated = conn.execute("SELECT * FROM managed_numbers WHERE id = ?", (number_id,)).fetchone()
            result = dict(updated)
            result["metadata"] = json.loads(result.pop("metadata_json", "{}") or "{}")
            result["transferred_to"] = dict(target)
            return result

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

    def list_message_logs(
        self,
        limit: int = 100,
        direction: str | None = None,
        user_numbers: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            clauses: list[str] = []
            params: list[Any] = []
            if direction:
                clauses.append("direction = ?")
                params.append(direction)
            if user_numbers is not None:
                if not user_numbers:
                    return []
                placeholders = ",".join("?" for _ in user_numbers)
                clauses.append(f"(from_number IN ({placeholders}) OR to_number IN ({placeholders}))")
                params.extend(user_numbers)
                params.extend(user_numbers)
            where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
            params.append(limit)
            rows = conn.execute(
                f"""
                SELECT * FROM message_logs
                {where}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                params,
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

    def get_wallet_balance(self, user_id: int | None = None) -> float:
        """Return wallet balance. If user_id given, returns that user's balance; else global."""
        with self._connect() as conn:
            if user_id is not None:
                row = conn.execute(
                    "SELECT COALESCE(SUM(amount), 0) AS balance FROM wallet_transactions WHERE user_id=?",
                    (user_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COALESCE(SUM(amount), 0) AS balance FROM wallet_transactions WHERE user_id IS NULL"
                ).fetchone()
        return float(row["balance"] or 0.0)

    def list_wallet_transactions(self, limit: int = 100, user_id: int | None = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if user_id is not None:
                rows = conn.execute(
                    """
                    SELECT id, amount, tx_type, provider, description, reference_id, created_at, user_id
                    FROM wallet_transactions WHERE user_id=?
                    ORDER BY created_at DESC LIMIT ?
                    """,
                    (user_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, amount, tx_type, provider, description, reference_id, created_at, user_id
                    FROM wallet_transactions WHERE user_id IS NULL
                    ORDER BY created_at DESC LIMIT ?
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
        user_id: int | None = None,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO wallet_transactions (
                    amount, tx_type, provider, description, reference_id, created_at, user_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (amount, tx_type, provider, description, reference_id, utc_now(), user_id),
            )
            row = conn.execute(
                """
                SELECT id, amount, tx_type, provider, description, reference_id, created_at, user_id
                FROM wallet_transactions
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            raise RuntimeError("Failed to create wallet transaction.")
        return dict(row)

    def top_up_wallet(self, amount: float, method: str = "manual", user_id: int | None = None) -> dict[str, Any]:
        if amount <= 0:
            raise ValueError("Top-up amount must be greater than zero.")
        tx = self.create_wallet_transaction(
            amount=amount,
            tx_type="topup",
            description=f"Wallet top-up via {method}",
            user_id=user_id,
        )
        return {"transaction": tx, "balance": self.get_wallet_balance(user_id=user_id)}

    def charge_wallet(
        self,
        amount: float,
        tx_type: str,
        provider: str,
        description: str,
        reference_id: str = "",
        user_id: int | None = None,
    ) -> dict[str, Any]:
        if amount <= 0:
            raise ValueError("Charge amount must be greater than zero.")
        balance = self.get_wallet_balance(user_id=user_id)
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
            user_id=user_id,
        )
        return {"transaction": tx, "balance": self.get_wallet_balance(user_id=user_id)}

    # ── User / Auth ────────────────────────────────────────────────────────

    @staticmethod
    def hash_password(password: str) -> str:
        salt = secrets.token_hex(16)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
        return f"pbkdf2:{salt}:{dk.hex()}"

    @staticmethod
    def verify_password(password: str, stored_hash: str) -> bool:
        try:
            _, salt, dk_hex = stored_hash.split(":")
            dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
            return secrets.compare_digest(dk.hex(), dk_hex)
        except Exception:
            return False

    _AVATAR_COLORS = [
        "#1f6feb","#3fb950","#d29922","#a371f7",
        "#f85149","#58a6ff","#56d364","#e3b341",
    ]

    def _avatar_color_for_email(self, email: str) -> str:
        h = 0
        for c in email:
            h = (h * 31 + ord(c)) & 0xFFFFFF
        return self._AVATAR_COLORS[abs(h) % len(self._AVATAR_COLORS)]

    def create_user(self, email: str, name: str, password: str, role: str = "user") -> dict[str, Any]:
        now = utc_now()
        pw_hash = self.hash_password(password)
        color = self._avatar_color_for_email(email)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (email, name, password_hash, role, avatar_color, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (email.lower().strip(), name.strip(), pw_hash, role, color, now),
            )
        return self.get_user_by_email(email)  # type: ignore[return-value]

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id,email,name,role,avatar_color,created_at,last_login,last_seen FROM users WHERE email=?",
                (email.lower().strip(),),
            ).fetchone()
        return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id,email,name,role,avatar_color,created_at,last_login,last_seen FROM users WHERE id=?",
                (user_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_user_password_hash(self, email: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT password_hash FROM users WHERE email=?",
                (email.lower().strip(),),
            ).fetchone()
        return row["password_hash"] if row else None

    def touch_user_login(self, user_id: int) -> None:
        now = utc_now()
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET last_login=?, last_seen=? WHERE id=?",
                (now, now, user_id),
            )

    def touch_user_seen(self, user_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET last_seen=? WHERE id=?",
                (utc_now(), user_id),
            )

    def update_user_profile(self, user_id: int, name: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            conn.execute("UPDATE users SET name=? WHERE id=?", (name.strip(), user_id))
        return self.get_user_by_id(user_id)

    def change_user_password(self, user_id: int, new_password: str) -> None:
        pw_hash = self.hash_password(new_password)
        with self._connect() as conn:
            conn.execute("UPDATE users SET password_hash=? WHERE id=?", (pw_hash, user_id))

    def list_users(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id,email,name,role,avatar_color,created_at,last_login,last_seen FROM users ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def user_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()
        return int(row["cnt"] or 0)

    # ── Payment Orders ────────────────────────────────────────────────────

    def create_payment_order(
        self,
        order_id: str,
        amount_usd: float,
        currency: str = "USDT",
        deeplink: str = "",
        paydify_txn_id: str = "",
        user_id: int | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO payment_orders
                    (order_id, paydify_txn_id, amount_usd, currency, deeplink, status, created_at, user_id)
                VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (order_id, paydify_txn_id, amount_usd, currency, deeplink, now, user_id),
            )
        return self.get_payment_order(order_id)  # type: ignore[return-value]

    def get_payment_order(self, order_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM payment_orders WHERE order_id=?",
                (order_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_payment_order_by_tx_hash(self, tx_hash: str) -> dict[str, Any] | None:
        """Find a paid order by its tx_hash — used to prevent replay attacks."""
        if not tx_hash:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM payment_orders WHERE tx_hash=? AND status='paid' LIMIT 1",
                (tx_hash,),
            ).fetchone()
        return dict(row) if row else None

    def mark_payment_order_paid(
        self,
        order_id: str,
        paydify_txn_id: str = "",
        tx_hash: str = "",
        from_address: str = "",
        paid_amount: float | None = None,
    ) -> dict[str, Any] | None:
        now = utc_now()
        with self._connect() as conn:
            order_row = conn.execute(
                "SELECT * FROM payment_orders WHERE order_id=?", (order_id,)
            ).fetchone()
            if not order_row:
                return None
            order = dict(order_row)
            if order["status"] == "paid":
                return order  # already processed — idempotent

            # Mark order paid
            conn.execute(
                """
                UPDATE payment_orders
                SET status='paid', paid_at=?, paydify_txn_id=?, tx_hash=?, from_address=?
                WHERE order_id=?
                """,
                (now, paydify_txn_id or order["paydify_txn_id"], tx_hash, from_address, order_id),
            )

            # Credit the user's wallet
            credit_amount = paid_amount if paid_amount else order["amount_usd"]
            conn.execute(
                """
                INSERT INTO wallet_transactions
                    (amount, tx_type, provider, description, reference_id, created_at, user_id)
                VALUES (?, 'topup', 'bitget', ?, ?, ?, ?)
                """,
                (
                    credit_amount,
                    f"Bitget Pay top-up — order {order_id}",
                    order_id,
                    now,
                    order.get("user_id"),
                ),
            )
        return self.get_payment_order(order_id)

    def mark_payment_order_failed(self, order_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE payment_orders SET status='failed' WHERE order_id=? AND status='pending'",
                (order_id,),
            )

    def list_payment_orders(self, user_id: int | None = None, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if user_id is not None:
                rows = conn.execute(
                    "SELECT * FROM payment_orders WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
                    (user_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM payment_orders ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

