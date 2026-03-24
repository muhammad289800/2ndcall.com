import json
import os
import sqlite3
from datetime import date, datetime, timezone
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "jamia_lms.db")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def today_iso() -> str:
    return date.today().isoformat()


class Storage:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or os.environ.get("LMS_DB_PATH", DEFAULT_DB_PATH)
        self._init_db()
        self._seed_defaults()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admission_no TEXT NOT NULL UNIQUE,
                    full_name TEXT NOT NULL,
                    arabic_name TEXT DEFAULT '',
                    dob TEXT DEFAULT '',
                    gender TEXT DEFAULT '',
                    class_name TEXT NOT NULL,
                    section_name TEXT DEFAULT '',
                    guardian_name TEXT NOT NULL,
                    guardian_phone TEXT DEFAULT '',
                    address TEXT DEFAULT '',
                    joined_on TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    full_name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    phone TEXT DEFAULT '',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS parent_students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_user_id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    relation TEXT DEFAULT 'guardian',
                    UNIQUE(parent_user_id, student_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS teachers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_no TEXT NOT NULL UNIQUE,
                    full_name TEXT NOT NULL,
                    subject TEXT DEFAULT '',
                    phone TEXT DEFAULT '',
                    joined_on TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS student_fees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    fee_month TEXT NOT NULL,
                    category TEXT NOT NULL,
                    amount REAL NOT NULL,
                    paid_amount REAL NOT NULL DEFAULT 0,
                    due_date TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'due',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS fee_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fee_id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    paid_on TEXT NOT NULL,
                    method TEXT NOT NULL,
                    reference TEXT DEFAULT '',
                    recorded_by TEXT DEFAULT 'system',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS student_attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    day TEXT NOT NULL,
                    present INTEGER NOT NULL,
                    remark TEXT DEFAULT '',
                    recorded_by TEXT DEFAULT 'system',
                    created_at TEXT NOT NULL,
                    UNIQUE(student_id, day)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS teacher_attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    teacher_id INTEGER NOT NULL,
                    day TEXT NOT NULL,
                    present INTEGER NOT NULL,
                    remark TEXT DEFAULT '',
                    recorded_by TEXT DEFAULT 'system',
                    created_at TEXT NOT NULL,
                    UNIQUE(teacher_id, day)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS papers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    class_name TEXT NOT NULL,
                    term_name TEXT NOT NULL,
                    max_marks REAL NOT NULL,
                    exam_date TEXT NOT NULL,
                    paper_type TEXT DEFAULT 'written',
                    created_by TEXT DEFAULT 'admin',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS paper_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paper_id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    marks REAL NOT NULL,
                    remarks TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    UNIQUE(paper_id, student_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS announcements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    target_group TEXT NOT NULL DEFAULT 'all',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS library_books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_code TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    author TEXT DEFAULT '',
                    category TEXT DEFAULT '',
                    total_copies INTEGER NOT NULL DEFAULT 1,
                    available_copies INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS library_issues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    issued_on TEXT NOT NULL,
                    due_on TEXT NOT NULL,
                    returned_on TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'issued',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS hostel_rooms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_code TEXT NOT NULL UNIQUE,
                    capacity INTEGER NOT NULL,
                    occupied INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS hostel_allocations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    start_on TEXT NOT NULL,
                    end_on TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS parent_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    summary_json TEXT NOT NULL,
                    generated_by TEXT DEFAULT 'system',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS hifz_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    surah_name TEXT NOT NULL,
                    para_no INTEGER NOT NULL,
                    ayat_from INTEGER NOT NULL,
                    ayat_to INTEGER NOT NULL,
                    revision_grade TEXT DEFAULT '',
                    teacher_name TEXT DEFAULT '',
                    recorded_on TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS discipline_incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT NOT NULL,
                    action_taken TEXT DEFAULT '',
                    reported_by TEXT DEFAULT 'system',
                    incident_on TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS timetable_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    class_name TEXT NOT NULL,
                    day_name TEXT NOT NULL,
                    period_no INTEGER NOT NULL,
                    subject TEXT NOT NULL,
                    teacher_name TEXT DEFAULT '',
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(class_name, day_name, period_no)
                )
                """
            )

    def _seed_defaults(self) -> None:
        with self._connect() as conn:
            has_admin = conn.execute(
                "SELECT id FROM users WHERE role = 'admin' LIMIT 1"
            ).fetchone()
            if has_admin:
                return
            conn.execute(
                """
                INSERT INTO users (username, full_name, role, password_hash, phone, active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "admin",
                    "System Administrator",
                    "admin",
                    generate_password_hash("admin123"),
                    "",
                    1,
                    utc_now(),
                ),
            )

    def _admission_no(self) -> str:
        with self._connect() as conn:
            row = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 AS seq FROM students").fetchone()
        seq = int(row["seq"] or 1)
        return f"JAMIA-{seq:04d}"

    def _employee_no(self) -> str:
        with self._connect() as conn:
            row = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 AS seq FROM teachers").fetchone()
        seq = int(row["seq"] or 1)
        return f"TCH-{seq:04d}"

    def _normalize_username(self, base: str) -> str:
        sanitized = "".join(ch for ch in base.lower() if ch.isalnum() or ch == "_")
        sanitized = sanitized.strip("_") or "user"
        return sanitized

    def _unique_username(self, base: str) -> str:
        candidate = self._normalize_username(base)
        index = 0
        with self._connect() as conn:
            while True:
                attempt = candidate if index == 0 else f"{candidate}{index}"
                exists = conn.execute(
                    "SELECT id FROM users WHERE username = ? LIMIT 1", (attempt,)
                ).fetchone()
                if not exists:
                    return attempt
                index += 1

    def summary(self) -> dict[str, Any]:
        today = today_iso()
        with self._connect() as conn:
            students = conn.execute("SELECT COUNT(*) AS count FROM students").fetchone()
            teachers = conn.execute("SELECT COUNT(*) AS count FROM teachers").fetchone()
            parents = conn.execute(
                "SELECT COUNT(*) AS count FROM users WHERE role = 'parent'"
            ).fetchone()
            dues = conn.execute(
                """
                SELECT COUNT(*) AS due_count, COALESCE(SUM(amount - paid_amount), 0) AS balance
                FROM student_fees
                WHERE status IN ('due', 'partial')
                """
            ).fetchone()
            attendance = conn.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN present = 1 THEN 1 ELSE 0 END), 0) AS present_count,
                    COUNT(*) AS total_count
                FROM student_attendance
                WHERE day = ?
                """,
                (today,),
            ).fetchone()
            active_hostel = conn.execute(
                "SELECT COUNT(*) AS count FROM hostel_allocations WHERE status = 'active'"
            ).fetchone()
            issued_books = conn.execute(
                "SELECT COUNT(*) AS count FROM library_issues WHERE status = 'issued'"
            ).fetchone()
        return {
            "students": int(students["count"] or 0),
            "teachers": int(teachers["count"] or 0),
            "parents": int(parents["count"] or 0),
            "pending_fee_records": int(dues["due_count"] or 0),
            "pending_fee_balance": float(dues["balance"] or 0),
            "today_attendance_present": int(attendance["present_count"] or 0),
            "today_attendance_total": int(attendance["total_count"] or 0),
            "hostel_active_allocations": int(active_hostel["count"] or 0),
            "library_issued_books": int(issued_books["count"] or 0),
            "default_admin_user": "admin",
            "default_admin_password": "admin123",
        }

    def list_students(self, limit: int = 500, status: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    """
                    SELECT * FROM students
                    WHERE status = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM students
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [dict(row) for row in rows]

    def get_student(self, student_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        return dict(row) if row else None

    def admit_student(
        self,
        full_name: str,
        class_name: str,
        guardian_name: str,
        guardian_phone: str = "",
        section_name: str = "",
        arabic_name: str = "",
        gender: str = "",
        dob: str = "",
        address: str = "",
        notes: str = "",
        joined_on: str | None = None,
    ) -> dict[str, Any]:
        joined = joined_on or today_iso()
        now = utc_now()
        admission_no = self._admission_no()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO students (
                    admission_no, full_name, arabic_name, dob, gender, class_name, section_name,
                    guardian_name, guardian_phone, address, joined_on, status, notes, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                (
                    admission_no,
                    full_name.strip(),
                    arabic_name.strip(),
                    dob.strip(),
                    gender.strip(),
                    class_name.strip(),
                    section_name.strip(),
                    guardian_name.strip(),
                    guardian_phone.strip(),
                    address.strip(),
                    joined,
                    notes.strip(),
                    now,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM students WHERE admission_no = ?",
                (admission_no,),
            ).fetchone()
        if not row:
            raise RuntimeError("Admission failed.")
        return dict(row)

    def list_users(self, role: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if role:
                rows = conn.execute(
                    """
                    SELECT id, username, full_name, role, phone, active, created_at
                    FROM users
                    WHERE role = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (role, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, username, full_name, role, phone, active, created_at
                    FROM users
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [dict(row) for row in rows]

    def create_user(
        self,
        username: str,
        full_name: str,
        role: str,
        password: str,
        phone: str = "",
        active: bool = True,
    ) -> dict[str, Any]:
        if role not in {"admin", "teacher", "parent", "accountant", "staff"}:
            raise ValueError("role must be one of admin, teacher, parent, accountant, staff")
        if len(password) < 6:
            raise ValueError("password must be at least 6 characters")
        normalized = self._normalize_username(username)
        now = utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (username, full_name, role, password_hash, phone, active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized,
                    full_name.strip(),
                    role,
                    generate_password_hash(password),
                    phone.strip(),
                    1 if active else 0,
                    now,
                ),
            )
            row = conn.execute(
                """
                SELECT id, username, full_name, role, phone, active, created_at
                FROM users WHERE username = ?
                """,
                (normalized,),
            ).fetchone()
        if not row:
            raise RuntimeError("Failed to create user")
        return dict(row)

    def authenticate_user(self, username: str, password: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if not row:
            return None
        record = dict(row)
        if int(record.get("active", 0)) != 1:
            return None
        if not check_password_hash(record["password_hash"], password):
            return None
        return {
            "id": record["id"],
            "username": record["username"],
            "full_name": record["full_name"],
            "role": record["role"],
            "phone": record["phone"],
            "active": record["active"],
            "created_at": record["created_at"],
        }

    def create_or_link_parent(
        self,
        student_id: int,
        parent_name: str,
        parent_phone: str = "",
        relation: str = "guardian",
        preferred_username: str = "",
        password: str = "",
    ) -> dict[str, Any]:
        with self._connect() as conn:
            student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
            if not student:
                raise ValueError("student not found")
        generated_password = password or "jamia123"
        if preferred_username:
            username = self._normalize_username(preferred_username)
            with self._connect() as conn:
                existing = conn.execute(
                    "SELECT id, username FROM users WHERE username = ?",
                    (username,),
                ).fetchone()
        else:
            base = f"{parent_name.split()[0]}_{student['admission_no'].lower()}"
            username = self._unique_username(base)
            existing = None

        if existing:
            parent_user_id = int(existing["id"])
        else:
            user = self.create_user(
                username=username,
                full_name=parent_name,
                role="parent",
                password=generated_password,
                phone=parent_phone,
                active=True,
            )
            parent_user_id = int(user["id"])

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO parent_students (parent_user_id, student_id, relation)
                VALUES (?, ?, ?)
                ON CONFLICT(parent_user_id, student_id) DO NOTHING
                """,
                (parent_user_id, student_id, relation),
            )
            parent = conn.execute(
                """
                SELECT id, username, full_name, role, phone, active, created_at
                FROM users WHERE id = ?
                """,
                (parent_user_id,),
            ).fetchone()
        if not parent:
            raise RuntimeError("Parent user not found after creation/link")
        output = dict(parent)
        output["temporary_password"] = generated_password if not existing else None
        output["linked_student_id"] = student_id
        return output

    def list_parents_with_children(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    u.id AS parent_user_id,
                    u.username,
                    u.full_name AS parent_name,
                    u.phone,
                    ps.student_id,
                    ps.relation,
                    s.admission_no,
                    s.full_name AS student_name,
                    s.class_name
                FROM users u
                JOIN parent_students ps ON ps.parent_user_id = u.id
                JOIN students s ON s.id = ps.student_id
                WHERE u.role = 'parent'
                ORDER BY u.id DESC, s.full_name ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def list_teachers(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM teachers ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_teacher(
        self,
        full_name: str,
        subject: str,
        phone: str = "",
        joined_on: str | None = None,
    ) -> dict[str, Any]:
        employee_no = self._employee_no()
        joined = joined_on or today_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO teachers (employee_no, full_name, subject, phone, joined_on, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'active', ?)
                """,
                (employee_no, full_name.strip(), subject.strip(), phone.strip(), joined, utc_now()),
            )
            row = conn.execute("SELECT * FROM teachers WHERE employee_no = ?", (employee_no,)).fetchone()
        if not row:
            raise RuntimeError("Teacher could not be created")
        return dict(row)

    def create_fee_charge(
        self,
        student_id: int,
        fee_month: str,
        category: str,
        amount: float,
        due_date: str,
    ) -> dict[str, Any]:
        if amount <= 0:
            raise ValueError("amount must be greater than 0")
        with self._connect() as conn:
            student = conn.execute("SELECT id FROM students WHERE id = ?", (student_id,)).fetchone()
            if not student:
                raise ValueError("student not found")
            conn.execute(
                """
                INSERT INTO student_fees (student_id, fee_month, category, amount, paid_amount, due_date, status, created_at)
                VALUES (?, ?, ?, ?, 0, ?, 'due', ?)
                """,
                (student_id, fee_month.strip(), category.strip(), amount, due_date.strip(), utc_now()),
            )
            row = conn.execute("SELECT * FROM student_fees ORDER BY id DESC LIMIT 1").fetchone()
        if not row:
            raise RuntimeError("fee charge failed")
        return dict(row)

    def list_fee_dues(self, student_id: int | None = None, limit: int = 500) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if student_id:
                rows = conn.execute(
                    """
                    SELECT f.*, s.full_name, s.admission_no
                    FROM student_fees f
                    JOIN students s ON s.id = f.student_id
                    WHERE f.student_id = ?
                    ORDER BY f.id DESC
                    LIMIT ?
                    """,
                    (student_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT f.*, s.full_name, s.admission_no
                    FROM student_fees f
                    JOIN students s ON s.id = f.student_id
                    ORDER BY f.id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        output: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["balance"] = float(item["amount"] - item["paid_amount"])
            output.append(item)
        return output

    def record_fee_payment(
        self,
        fee_id: int,
        amount: float,
        method: str,
        reference: str = "",
        recorded_by: str = "system",
    ) -> dict[str, Any]:
        if amount <= 0:
            raise ValueError("payment amount must be greater than 0")
        with self._connect() as conn:
            due = conn.execute("SELECT * FROM student_fees WHERE id = ?", (fee_id,)).fetchone()
            if not due:
                raise ValueError("fee record not found")
            due_amount = float(due["amount"] or 0)
            paid_amount = float(due["paid_amount"] or 0)
            balance = due_amount - paid_amount
            if amount > balance + 1e-9:
                raise ValueError("payment is greater than outstanding amount")

            new_paid_amount = paid_amount + amount
            if abs(new_paid_amount - due_amount) < 1e-9:
                status = "paid"
            elif new_paid_amount > 0:
                status = "partial"
            else:
                status = "due"

            conn.execute(
                """
                UPDATE student_fees
                SET paid_amount = ?, status = ?
                WHERE id = ?
                """,
                (new_paid_amount, status, fee_id),
            )
            conn.execute(
                """
                INSERT INTO fee_payments (fee_id, student_id, amount, paid_on, method, reference, recorded_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fee_id,
                    due["student_id"],
                    amount,
                    today_iso(),
                    method.strip(),
                    reference.strip(),
                    recorded_by.strip(),
                    utc_now(),
                ),
            )
            updated = conn.execute("SELECT * FROM student_fees WHERE id = ?", (fee_id,)).fetchone()
            payment = conn.execute(
                "SELECT * FROM fee_payments ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if not updated or not payment:
            raise RuntimeError("could not persist payment")
        due_dict = dict(updated)
        due_dict["balance"] = float(due_dict["amount"] - due_dict["paid_amount"])
        return {"due": due_dict, "payment": dict(payment)}

    def record_student_attendance(
        self,
        day: str,
        entries: list[dict[str, Any]],
        recorded_by: str = "system",
    ) -> dict[str, Any]:
        recorded = 0
        with self._connect() as conn:
            for entry in entries:
                student_id = int(entry["student_id"])
                present = 1 if bool(entry.get("present", False)) else 0
                remark = str(entry.get("remark", "")).strip()
                conn.execute(
                    """
                    INSERT INTO student_attendance (student_id, day, present, remark, recorded_by, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(student_id, day) DO UPDATE SET
                        present = excluded.present,
                        remark = excluded.remark,
                        recorded_by = excluded.recorded_by,
                        created_at = excluded.created_at
                    """,
                    (student_id, day, present, remark, recorded_by, utc_now()),
                )
                recorded += 1
        return {"day": day, "recorded": recorded}

    def list_student_attendance(self, day: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if day:
                rows = conn.execute(
                    """
                    SELECT a.*, s.full_name, s.admission_no, s.class_name
                    FROM student_attendance a
                    JOIN students s ON s.id = a.student_id
                    WHERE a.day = ?
                    ORDER BY s.full_name
                    LIMIT ?
                    """,
                    (day, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT a.*, s.full_name, s.admission_no, s.class_name
                    FROM student_attendance a
                    JOIN students s ON s.id = a.student_id
                    ORDER BY a.day DESC, s.full_name
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [dict(row) for row in rows]

    def student_attendance_summary(self, student_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_days,
                    COALESCE(SUM(CASE WHEN present = 1 THEN 1 ELSE 0 END), 0) AS present_days
                FROM student_attendance
                WHERE student_id = ?
                """,
                (student_id,),
            ).fetchone()
        total_days = int(row["total_days"] or 0)
        present_days = int(row["present_days"] or 0)
        percentage = round((present_days * 100.0 / total_days), 2) if total_days else 0.0
        return {
            "student_id": student_id,
            "present_days": present_days,
            "total_days": total_days,
            "percentage": percentage,
        }

    def record_teacher_attendance(
        self,
        day: str,
        entries: list[dict[str, Any]],
        recorded_by: str = "system",
    ) -> dict[str, Any]:
        recorded = 0
        with self._connect() as conn:
            for entry in entries:
                teacher_id = int(entry["teacher_id"])
                present = 1 if bool(entry.get("present", False)) else 0
                remark = str(entry.get("remark", "")).strip()
                conn.execute(
                    """
                    INSERT INTO teacher_attendance (teacher_id, day, present, remark, recorded_by, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(teacher_id, day) DO UPDATE SET
                        present = excluded.present,
                        remark = excluded.remark,
                        recorded_by = excluded.recorded_by,
                        created_at = excluded.created_at
                    """,
                    (teacher_id, day, present, remark, recorded_by, utc_now()),
                )
                recorded += 1
        return {"day": day, "recorded": recorded}

    def list_teacher_attendance(self, day: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if day:
                rows = conn.execute(
                    """
                    SELECT a.*, t.full_name, t.employee_no, t.subject
                    FROM teacher_attendance a
                    JOIN teachers t ON t.id = a.teacher_id
                    WHERE a.day = ?
                    ORDER BY t.full_name
                    LIMIT ?
                    """,
                    (day, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT a.*, t.full_name, t.employee_no, t.subject
                    FROM teacher_attendance a
                    JOIN teachers t ON t.id = a.teacher_id
                    ORDER BY a.day DESC, t.full_name
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [dict(row) for row in rows]

    def create_paper(
        self,
        title: str,
        subject: str,
        class_name: str,
        term_name: str,
        max_marks: float,
        exam_date: str,
        paper_type: str = "written",
        created_by: str = "admin",
    ) -> dict[str, Any]:
        if max_marks <= 0:
            raise ValueError("max_marks must be greater than 0")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO papers (
                    title, subject, class_name, term_name, max_marks, exam_date, paper_type, created_by, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    title.strip(),
                    subject.strip(),
                    class_name.strip(),
                    term_name.strip(),
                    max_marks,
                    exam_date.strip(),
                    paper_type.strip(),
                    created_by.strip(),
                    utc_now(),
                ),
            )
            row = conn.execute("SELECT * FROM papers ORDER BY id DESC LIMIT 1").fetchone()
        if not row:
            raise RuntimeError("paper could not be created")
        return dict(row)

    def list_papers(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM papers ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def upsert_paper_scores(self, paper_id: int, entries: list[dict[str, Any]]) -> dict[str, Any]:
        with self._connect() as conn:
            paper = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
            if not paper:
                raise ValueError("paper not found")
            max_marks = float(paper["max_marks"])
            updated = 0
            for entry in entries:
                student_id = int(entry["student_id"])
                marks = float(entry["marks"])
                if marks < 0 or marks > max_marks:
                    raise ValueError(f"marks must be between 0 and {max_marks}")
                remarks = str(entry.get("remarks", "")).strip()
                conn.execute(
                    """
                    INSERT INTO paper_scores (paper_id, student_id, marks, remarks, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(paper_id, student_id) DO UPDATE SET
                        marks = excluded.marks,
                        remarks = excluded.remarks,
                        created_at = excluded.created_at
                    """,
                    (paper_id, student_id, marks, remarks, utc_now()),
                )
                updated += 1
        return {"paper_id": paper_id, "updated_scores": updated}

    def list_paper_scores(self, paper_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT ps.*, s.full_name, s.admission_no
                FROM paper_scores ps
                JOIN students s ON s.id = ps.student_id
                WHERE ps.paper_id = ?
                ORDER BY s.full_name
                """,
                (paper_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def generate_progress_report(self, student_id: int) -> dict[str, Any]:
        student = self.get_student(student_id)
        if not student:
            raise ValueError("student not found")
        attendance = self.student_attendance_summary(student_id)
        with self._connect() as conn:
            fee_rows = conn.execute(
                """
                SELECT id, fee_month, category, amount, paid_amount, due_date, status
                FROM student_fees
                WHERE student_id = ?
                ORDER BY id DESC
                """,
                (student_id,),
            ).fetchall()
            scores = conn.execute(
                """
                SELECT
                    p.id AS paper_id,
                    p.title,
                    p.subject,
                    p.term_name,
                    p.max_marks,
                    ps.marks,
                    ROUND((ps.marks * 100.0) / p.max_marks, 2) AS percentage
                FROM paper_scores ps
                JOIN papers p ON p.id = ps.paper_id
                WHERE ps.student_id = ?
                ORDER BY p.exam_date DESC
                """,
                (student_id,),
            ).fetchall()
        fee_items = [dict(row) for row in fee_rows]
        for item in fee_items:
            item["balance"] = float(item["amount"] - item["paid_amount"])
        score_items = [dict(row) for row in scores]
        if score_items:
            average_percentage = round(
                sum(float(row["percentage"] or 0) for row in score_items) / len(score_items),
                2,
            )
        else:
            average_percentage = 0.0

        if average_percentage >= 85:
            grade = "A"
        elif average_percentage >= 70:
            grade = "B"
        elif average_percentage >= 55:
            grade = "C"
        elif average_percentage >= 40:
            grade = "D"
        else:
            grade = "E"

        total_fee_balance = round(sum(float(item["balance"]) for item in fee_items), 2)
        report = {
            "student": student,
            "attendance": attendance,
            "fees": {
                "records": fee_items,
                "outstanding_balance": total_fee_balance,
            },
            "academics": {
                "scores": score_items,
                "average_percentage": average_percentage,
                "grade": grade,
            },
            "generated_at": utc_now(),
        }
        return report

    def publish_parent_report(self, student_id: int, generated_by: str = "system") -> dict[str, Any]:
        report = self.generate_progress_report(student_id)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO parent_reports (student_id, summary_json, generated_by, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (student_id, json.dumps(report), generated_by, utc_now()),
            )
            row = conn.execute("SELECT * FROM parent_reports ORDER BY id DESC LIMIT 1").fetchone()
        if not row:
            raise RuntimeError("parent report publish failed")
        output = dict(row)
        output["summary"] = json.loads(output.pop("summary_json"))
        return output

    def parent_portal(self, parent_user_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            links = conn.execute(
                """
                SELECT
                    s.id AS student_id,
                    s.admission_no,
                    s.full_name,
                    s.class_name,
                    ps.relation
                FROM parent_students ps
                JOIN students s ON s.id = ps.student_id
                WHERE ps.parent_user_id = ?
                ORDER BY s.full_name
                """,
                (parent_user_id,),
            ).fetchall()
            reports = conn.execute(
                """
                SELECT pr.*, s.full_name AS student_name, s.admission_no
                FROM parent_reports pr
                JOIN students s ON s.id = pr.student_id
                JOIN parent_students ps ON ps.student_id = pr.student_id
                WHERE ps.parent_user_id = ?
                ORDER BY pr.id DESC
                LIMIT 50
                """,
                (parent_user_id,),
            ).fetchall()
        children = [dict(row) for row in links]
        report_items = []
        for row in reports:
            item = dict(row)
            item["summary"] = json.loads(item.pop("summary_json"))
            report_items.append(item)
        return {"children": children, "reports": report_items}

    def create_announcement(self, title: str, body: str, target_group: str = "all") -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO announcements (title, body, target_group, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (title.strip(), body.strip(), target_group.strip(), utc_now()),
            )
            row = conn.execute("SELECT * FROM announcements ORDER BY id DESC LIMIT 1").fetchone()
        if not row:
            raise RuntimeError("announcement could not be created")
        return dict(row)

    def list_announcements(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM announcements ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_library_book(
        self,
        book_code: str,
        title: str,
        author: str = "",
        category: str = "",
        total_copies: int = 1,
    ) -> dict[str, Any]:
        if total_copies <= 0:
            raise ValueError("total_copies must be greater than 0")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO library_books (
                    book_code, title, author, category, total_copies, available_copies, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    book_code.strip().upper(),
                    title.strip(),
                    author.strip(),
                    category.strip(),
                    total_copies,
                    total_copies,
                    utc_now(),
                ),
            )
            row = conn.execute("SELECT * FROM library_books WHERE book_code = ?", (book_code.strip().upper(),)).fetchone()
        if not row:
            raise RuntimeError("book could not be added")
        return dict(row)

    def list_library_books(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM library_books ORDER BY id DESC").fetchall()
        return [dict(row) for row in rows]

    def issue_library_book(self, book_id: int, student_id: int, due_on: str) -> dict[str, Any]:
        with self._connect() as conn:
            book = conn.execute("SELECT * FROM library_books WHERE id = ?", (book_id,)).fetchone()
            student = conn.execute("SELECT id FROM students WHERE id = ?", (student_id,)).fetchone()
            if not book:
                raise ValueError("book not found")
            if not student:
                raise ValueError("student not found")
            if int(book["available_copies"] or 0) <= 0:
                raise ValueError("book is not available")
            conn.execute(
                "UPDATE library_books SET available_copies = available_copies - 1 WHERE id = ?",
                (book_id,),
            )
            conn.execute(
                """
                INSERT INTO library_issues (book_id, student_id, issued_on, due_on, returned_on, status, created_at)
                VALUES (?, ?, ?, ?, '', 'issued', ?)
                """,
                (book_id, student_id, today_iso(), due_on.strip(), utc_now()),
            )
            issue = conn.execute("SELECT * FROM library_issues ORDER BY id DESC LIMIT 1").fetchone()
        if not issue:
            raise RuntimeError("issue record failed")
        return dict(issue)

    def return_library_book(self, issue_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            issue = conn.execute("SELECT * FROM library_issues WHERE id = ?", (issue_id,)).fetchone()
            if not issue:
                raise ValueError("issue not found")
            if issue["status"] == "returned":
                raise ValueError("book is already returned")
            conn.execute(
                """
                UPDATE library_issues
                SET status = 'returned', returned_on = ?
                WHERE id = ?
                """,
                (today_iso(), issue_id),
            )
            conn.execute(
                "UPDATE library_books SET available_copies = available_copies + 1 WHERE id = ?",
                (issue["book_id"],),
            )
            updated = conn.execute("SELECT * FROM library_issues WHERE id = ?", (issue_id,)).fetchone()
        if not updated:
            raise RuntimeError("return record failed")
        return dict(updated)

    def list_library_issues(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT i.*, b.title AS book_title, b.book_code, s.full_name AS student_name, s.admission_no
                FROM library_issues i
                JOIN library_books b ON b.id = i.book_id
                JOIN students s ON s.id = i.student_id
                ORDER BY i.id DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def add_hostel_room(self, room_code: str, capacity: int) -> dict[str, Any]:
        if capacity <= 0:
            raise ValueError("capacity must be greater than 0")
        code = room_code.strip().upper()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO hostel_rooms (room_code, capacity, occupied, created_at)
                VALUES (?, ?, 0, ?)
                """,
                (code, capacity, utc_now()),
            )
            row = conn.execute("SELECT * FROM hostel_rooms WHERE room_code = ?", (code,)).fetchone()
        if not row:
            raise RuntimeError("room creation failed")
        return dict(row)

    def allocate_hostel_room(self, room_id: int, student_id: int, start_on: str | None = None) -> dict[str, Any]:
        start = start_on or today_iso()
        with self._connect() as conn:
            room = conn.execute("SELECT * FROM hostel_rooms WHERE id = ?", (room_id,)).fetchone()
            student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
            active = conn.execute(
                """
                SELECT id FROM hostel_allocations
                WHERE student_id = ? AND status = 'active'
                LIMIT 1
                """,
                (student_id,),
            ).fetchone()
            if not room:
                raise ValueError("room not found")
            if not student:
                raise ValueError("student not found")
            if active:
                raise ValueError("student already has an active hostel allocation")
            if int(room["occupied"] or 0) >= int(room["capacity"] or 0):
                raise ValueError("room is full")
            conn.execute(
                """
                INSERT INTO hostel_allocations (room_id, student_id, start_on, end_on, status, created_at)
                VALUES (?, ?, ?, '', 'active', ?)
                """,
                (room_id, student_id, start, utc_now()),
            )
            conn.execute(
                "UPDATE hostel_rooms SET occupied = occupied + 1 WHERE id = ?",
                (room_id,),
            )
            allocation = conn.execute(
                "SELECT * FROM hostel_allocations ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if not allocation:
            raise RuntimeError("allocation failed")
        return dict(allocation)

    def list_hostel_rooms(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM hostel_rooms ORDER BY id DESC").fetchall()
        return [dict(row) for row in rows]

    def list_hostel_allocations(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT a.*, r.room_code, s.full_name AS student_name, s.admission_no
                FROM hostel_allocations a
                JOIN hostel_rooms r ON r.id = a.room_id
                JOIN students s ON s.id = a.student_id
                ORDER BY a.id DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def add_hifz_progress(
        self,
        student_id: int,
        surah_name: str,
        para_no: int,
        ayat_from: int,
        ayat_to: int,
        revision_grade: str = "",
        teacher_name: str = "",
        recorded_on: str | None = None,
    ) -> dict[str, Any]:
        if ayat_to < ayat_from:
            raise ValueError("ayat_to must be greater than or equal to ayat_from")
        on_date = recorded_on or today_iso()
        with self._connect() as conn:
            student = conn.execute("SELECT id FROM students WHERE id = ?", (student_id,)).fetchone()
            if not student:
                raise ValueError("student not found")
            conn.execute(
                """
                INSERT INTO hifz_progress (
                    student_id, surah_name, para_no, ayat_from, ayat_to,
                    revision_grade, teacher_name, recorded_on, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    student_id,
                    surah_name.strip(),
                    para_no,
                    ayat_from,
                    ayat_to,
                    revision_grade.strip(),
                    teacher_name.strip(),
                    on_date,
                    utc_now(),
                ),
            )
            row = conn.execute("SELECT * FROM hifz_progress ORDER BY id DESC LIMIT 1").fetchone()
        if not row:
            raise RuntimeError("hifz progress record failed")
        return dict(row)

    def list_hifz_progress(self, limit: int = 300) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT h.*, s.full_name AS student_name, s.admission_no, s.class_name
                FROM hifz_progress h
                JOIN students s ON s.id = h.student_id
                ORDER BY h.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_incident(
        self,
        student_id: int,
        category: str,
        description: str,
        action_taken: str = "",
        reported_by: str = "system",
        incident_on: str | None = None,
    ) -> dict[str, Any]:
        on_date = incident_on or today_iso()
        with self._connect() as conn:
            student = conn.execute("SELECT id FROM students WHERE id = ?", (student_id,)).fetchone()
            if not student:
                raise ValueError("student not found")
            conn.execute(
                """
                INSERT INTO discipline_incidents (
                    student_id, category, description, action_taken,
                    reported_by, incident_on, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    student_id,
                    category.strip(),
                    description.strip(),
                    action_taken.strip(),
                    reported_by.strip(),
                    on_date,
                    utc_now(),
                ),
            )
            row = conn.execute(
                "SELECT * FROM discipline_incidents ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if not row:
            raise RuntimeError("incident record failed")
        return dict(row)

    def list_incidents(self, limit: int = 300) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT i.*, s.full_name AS student_name, s.admission_no, s.class_name
                FROM discipline_incidents i
                JOIN students s ON s.id = i.student_id
                ORDER BY i.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_timetable_entry(
        self,
        class_name: str,
        day_name: str,
        period_no: int,
        subject: str,
        teacher_name: str,
        start_time: str,
        end_time: str,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO timetable_entries (
                    class_name, day_name, period_no, subject, teacher_name,
                    start_time, end_time, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(class_name, day_name, period_no) DO UPDATE SET
                    subject = excluded.subject,
                    teacher_name = excluded.teacher_name,
                    start_time = excluded.start_time,
                    end_time = excluded.end_time,
                    created_at = excluded.created_at
                """,
                (
                    class_name.strip(),
                    day_name.strip(),
                    period_no,
                    subject.strip(),
                    teacher_name.strip(),
                    start_time.strip(),
                    end_time.strip(),
                    utc_now(),
                ),
            )
            row = conn.execute(
                """
                SELECT * FROM timetable_entries
                WHERE class_name = ? AND day_name = ? AND period_no = ?
                """,
                (class_name.strip(), day_name.strip(), period_no),
            ).fetchone()
        if not row:
            raise RuntimeError("timetable entry failed")
        return dict(row)

    def list_timetable(self, day_name: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if day_name:
                rows = conn.execute(
                    """
                    SELECT * FROM timetable_entries
                    WHERE day_name = ?
                    ORDER BY class_name, period_no
                    LIMIT ?
                    """,
                    (day_name, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM timetable_entries
                    ORDER BY day_name, class_name, period_no
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [dict(row) for row in rows]

