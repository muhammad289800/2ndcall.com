import os
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request

from .storage import Storage


def parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def load_local_env() -> None:
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def create_app() -> Flask:
    load_local_env()
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    storage = Storage()

    def payload() -> dict[str, Any]:
        if request.is_json:
            return request.get_json(silent=True) or {}
        return request.form.to_dict()

    def parse_int(value: Any, default: int, minimum: int = 0, maximum: int = 500) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = default
        return max(minimum, min(parsed, maximum))

    def parse_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @app.get("/")
    def home():
        return render_template("index.html")

    @app.get("/health")
    def health():
        return jsonify({"ok": True, "service": "Jamia Ajmal ul Madaris LMS"})

    @app.get("/api/summary")
    def summary():
        return jsonify(storage.summary())

    @app.get("/api/students")
    def students_list():
        limit = parse_int(request.args.get("limit"), 500, 1, 1000)
        status = request.args.get("status")
        return jsonify({"students": storage.list_students(limit=limit, status=status)})

    @app.post("/api/students")
    def students_create():
        body = payload()
        full_name = str(body.get("full_name", "")).strip()
        class_name = str(body.get("class_name", "")).strip()
        guardian_name = str(body.get("guardian_name", "")).strip()
        if not full_name or not class_name or not guardian_name:
            return jsonify({"error": "full_name, class_name and guardian_name are required"}), 400
        try:
            student = storage.admit_student(
                full_name=full_name,
                class_name=class_name,
                guardian_name=guardian_name,
                guardian_phone=str(body.get("guardian_phone", "")),
                section_name=str(body.get("section_name", "")),
                arabic_name=str(body.get("arabic_name", "")),
                gender=str(body.get("gender", "")),
                dob=str(body.get("dob", "")),
                address=str(body.get("address", "")),
                notes=str(body.get("notes", "")),
                joined_on=str(body.get("joined_on", "")).strip() or None,
            )
            return jsonify({"student": student}), 201
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/users")
    def users_list():
        role = request.args.get("role")
        limit = parse_int(request.args.get("limit"), 500, 1, 1000)
        return jsonify({"users": storage.list_users(role=role, limit=limit)})

    @app.post("/api/users")
    def users_create():
        body = payload()
        required = {"username", "full_name", "role", "password"}
        if not required.issubset(set(body.keys())):
            return jsonify({"error": "username, full_name, role and password are required"}), 400
        try:
            user = storage.create_user(
                username=str(body.get("username", "")),
                full_name=str(body.get("full_name", "")),
                role=str(body.get("role", "")),
                password=str(body.get("password", "")),
                phone=str(body.get("phone", "")),
                active=parse_bool(body.get("active"), True),
            )
            return jsonify({"user": user}), 201
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/auth/login")
    def auth_login():
        body = payload()
        username = str(body.get("username", "")).strip()
        password = str(body.get("password", "")).strip()
        if not username or not password:
            return jsonify({"error": "username and password are required"}), 400
        user = storage.authenticate_user(username, password)
        if not user:
            return jsonify({"error": "invalid credentials"}), 401
        return jsonify({"user": user})

    @app.get("/api/parents")
    def list_parents():
        return jsonify({"parents": storage.list_parents_with_children()})

    @app.post("/api/parents/link")
    def link_parent():
        body = payload()
        student_id = parse_int(body.get("student_id"), 0, 1, 100000)
        parent_name = str(body.get("parent_name", "")).strip()
        if not student_id or not parent_name:
            return jsonify({"error": "student_id and parent_name are required"}), 400
        try:
            parent = storage.create_or_link_parent(
                student_id=student_id,
                parent_name=parent_name,
                parent_phone=str(body.get("parent_phone", "")),
                relation=str(body.get("relation", "guardian")),
                preferred_username=str(body.get("preferred_username", "")),
                password=str(body.get("password", "")),
            )
            return jsonify({"parent_user": parent})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/parent-portal")
    def parent_portal():
        body = payload()
        username = str(body.get("username", "")).strip()
        password = str(body.get("password", "")).strip()
        if not username or not password:
            return jsonify({"error": "username and password are required"}), 400
        user = storage.authenticate_user(username, password)
        if not user or user["role"] != "parent":
            return jsonify({"error": "invalid parent credentials"}), 401
        portal = storage.parent_portal(int(user["id"]))
        return jsonify({"parent": user, "portal": portal})

    @app.get("/api/teachers")
    def teachers_list():
        limit = parse_int(request.args.get("limit"), 200, 1, 1000)
        return jsonify({"teachers": storage.list_teachers(limit=limit)})

    @app.post("/api/teachers")
    def teachers_create():
        body = payload()
        full_name = str(body.get("full_name", "")).strip()
        subject = str(body.get("subject", "")).strip()
        if not full_name:
            return jsonify({"error": "full_name is required"}), 400
        try:
            teacher = storage.add_teacher(
                full_name=full_name,
                subject=subject,
                phone=str(body.get("phone", "")),
                joined_on=str(body.get("joined_on", "")).strip() or None,
            )
            return jsonify({"teacher": teacher}), 201
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/fees")
    def fees_list():
        student_id = parse_int(request.args.get("student_id"), 0, 0, 100000)
        return jsonify({"fees": storage.list_fee_dues(student_id=student_id or None)})

    @app.post("/api/fees")
    def fees_create():
        body = payload()
        student_id = parse_int(body.get("student_id"), 0, 1, 100000)
        fee_month = str(body.get("fee_month", "")).strip()
        category = str(body.get("category", "tuition")).strip()
        amount = parse_float(body.get("amount"), 0.0)
        due_date = str(body.get("due_date", "")).strip()
        if not student_id or not fee_month or not due_date:
            return jsonify({"error": "student_id, fee_month and due_date are required"}), 400
        try:
            fee = storage.create_fee_charge(
                student_id=student_id,
                fee_month=fee_month,
                category=category,
                amount=amount,
                due_date=due_date,
            )
            return jsonify({"fee": fee}), 201
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/fees/<int:fee_id>/pay")
    def fees_pay(fee_id: int):
        body = payload()
        amount = parse_float(body.get("amount"), 0.0)
        method = str(body.get("method", "cash")).strip()
        if amount <= 0:
            return jsonify({"error": "amount must be greater than zero"}), 400
        try:
            result = storage.record_fee_payment(
                fee_id=fee_id,
                amount=amount,
                method=method,
                reference=str(body.get("reference", "")),
                recorded_by=str(body.get("recorded_by", "system")),
            )
            return jsonify(result)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/attendance/students")
    def attendance_students_list():
        day = request.args.get("day")
        return jsonify({"attendance": storage.list_student_attendance(day=day)})

    @app.post("/api/attendance/students")
    def attendance_students_record():
        body = payload()
        day = str(body.get("day", "")).strip()
        entries = body.get("entries", [])
        if not day or not isinstance(entries, list):
            return jsonify({"error": "day and entries[] are required"}), 400
        try:
            result = storage.record_student_attendance(
                day=day,
                entries=entries,
                recorded_by=str(body.get("recorded_by", "system")),
            )
            return jsonify(result)
        except (ValueError, KeyError, TypeError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/attendance/teachers")
    def attendance_teachers_list():
        day = request.args.get("day")
        return jsonify({"attendance": storage.list_teacher_attendance(day=day)})

    @app.post("/api/attendance/teachers")
    def attendance_teachers_record():
        body = payload()
        day = str(body.get("day", "")).strip()
        entries = body.get("entries", [])
        if not day or not isinstance(entries, list):
            return jsonify({"error": "day and entries[] are required"}), 400
        try:
            result = storage.record_teacher_attendance(
                day=day,
                entries=entries,
                recorded_by=str(body.get("recorded_by", "system")),
            )
            return jsonify(result)
        except (ValueError, KeyError, TypeError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/papers")
    def papers_list():
        return jsonify({"papers": storage.list_papers()})

    @app.post("/api/papers")
    def papers_create():
        body = payload()
        title = str(body.get("title", "")).strip()
        subject = str(body.get("subject", "")).strip()
        class_name = str(body.get("class_name", "")).strip()
        term_name = str(body.get("term_name", "")).strip()
        max_marks = parse_float(body.get("max_marks"), 0.0)
        exam_date = str(body.get("exam_date", "")).strip()
        if not title or not subject or not class_name or not term_name or not exam_date:
            return jsonify({"error": "title, subject, class_name, term_name and exam_date are required"}), 400
        try:
            paper = storage.create_paper(
                title=title,
                subject=subject,
                class_name=class_name,
                term_name=term_name,
                max_marks=max_marks,
                exam_date=exam_date,
                paper_type=str(body.get("paper_type", "written")),
                created_by=str(body.get("created_by", "admin")),
            )
            return jsonify({"paper": paper}), 201
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/papers/<int:paper_id>/scores")
    def paper_scores_list(paper_id: int):
        return jsonify({"scores": storage.list_paper_scores(paper_id)})

    @app.post("/api/papers/<int:paper_id>/scores")
    def paper_scores_upsert(paper_id: int):
        body = payload()
        entries = body.get("entries", [])
        if not isinstance(entries, list):
            return jsonify({"error": "entries[] is required"}), 400
        try:
            result = storage.upsert_paper_scores(paper_id, entries=entries)
            return jsonify(result)
        except (ValueError, TypeError, KeyError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/reports/students/<int:student_id>/progress")
    def progress_report(student_id: int):
        try:
            report = storage.generate_progress_report(student_id)
            return jsonify({"report": report})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 404

    @app.post("/api/reports/students/<int:student_id>/publish")
    def publish_progress_report(student_id: int):
        body = payload()
        try:
            published = storage.publish_parent_report(
                student_id=student_id,
                generated_by=str(body.get("generated_by", "system")),
            )
            return jsonify({"published_report": published})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 404

    @app.get("/api/announcements")
    def announcements_list():
        return jsonify({"announcements": storage.list_announcements()})

    @app.post("/api/announcements")
    def announcements_create():
        body = payload()
        title = str(body.get("title", "")).strip()
        message = str(body.get("body", "")).strip()
        target_group = str(body.get("target_group", "all")).strip()
        if not title or not message:
            return jsonify({"error": "title and body are required"}), 400
        notice = storage.create_announcement(title=title, body=message, target_group=target_group)
        return jsonify({"announcement": notice}), 201

    @app.get("/api/library/books")
    def library_books_list():
        return jsonify({"books": storage.list_library_books()})

    @app.post("/api/library/books")
    def library_books_create():
        body = payload()
        code = str(body.get("book_code", "")).strip()
        title = str(body.get("title", "")).strip()
        copies = parse_int(body.get("total_copies"), 1, 1, 500)
        if not code or not title:
            return jsonify({"error": "book_code and title are required"}), 400
        try:
            book = storage.add_library_book(
                book_code=code,
                title=title,
                author=str(body.get("author", "")),
                category=str(body.get("category", "")),
                total_copies=copies,
            )
            return jsonify({"book": book}), 201
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/library/issues")
    def library_issues_list():
        return jsonify({"issues": storage.list_library_issues()})

    @app.post("/api/library/issues")
    def library_issue_create():
        body = payload()
        book_id = parse_int(body.get("book_id"), 0, 1, 100000)
        student_id = parse_int(body.get("student_id"), 0, 1, 100000)
        due_on = str(body.get("due_on", "")).strip()
        if not book_id or not student_id or not due_on:
            return jsonify({"error": "book_id, student_id and due_on are required"}), 400
        try:
            issue = storage.issue_library_book(book_id=book_id, student_id=student_id, due_on=due_on)
            return jsonify({"issue": issue}), 201
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/library/issues/<int:issue_id>/return")
    def library_issue_return(issue_id: int):
        try:
            issue = storage.return_library_book(issue_id)
            return jsonify({"issue": issue})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/hostel/rooms")
    def hostel_rooms_list():
        return jsonify({"rooms": storage.list_hostel_rooms()})

    @app.post("/api/hostel/rooms")
    def hostel_rooms_create():
        body = payload()
        room_code = str(body.get("room_code", "")).strip()
        capacity = parse_int(body.get("capacity"), 0, 1, 100)
        if not room_code or not capacity:
            return jsonify({"error": "room_code and capacity are required"}), 400
        try:
            room = storage.add_hostel_room(room_code=room_code, capacity=capacity)
            return jsonify({"room": room}), 201
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/hostel/allocations")
    def hostel_allocations_list():
        return jsonify({"allocations": storage.list_hostel_allocations()})

    @app.post("/api/hostel/allocations")
    def hostel_allocate():
        body = payload()
        room_id = parse_int(body.get("room_id"), 0, 1, 100000)
        student_id = parse_int(body.get("student_id"), 0, 1, 100000)
        if not room_id or not student_id:
            return jsonify({"error": "room_id and student_id are required"}), 400
        try:
            allocation = storage.allocate_hostel_room(
                room_id=room_id,
                student_id=student_id,
                start_on=str(body.get("start_on", "")).strip() or None,
            )
            return jsonify({"allocation": allocation}), 201
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/hifz")
    def hifz_list():
        return jsonify({"hifz_logs": storage.list_hifz_progress()})

    @app.post("/api/hifz")
    def hifz_create():
        body = payload()
        student_id = parse_int(body.get("student_id"), 0, 1, 100000)
        surah_name = str(body.get("surah_name", "")).strip()
        para_no = parse_int(body.get("para_no"), 0, 1, 30)
        ayat_from = parse_int(body.get("ayat_from"), 0, 1, 300)
        ayat_to = parse_int(body.get("ayat_to"), 0, 1, 300)
        if not student_id or not surah_name:
            return jsonify({"error": "student_id and surah_name are required"}), 400
        try:
            log = storage.add_hifz_progress(
                student_id=student_id,
                surah_name=surah_name,
                para_no=para_no,
                ayat_from=ayat_from,
                ayat_to=ayat_to,
                revision_grade=str(body.get("revision_grade", "")),
                teacher_name=str(body.get("teacher_name", "")),
                recorded_on=str(body.get("recorded_on", "")).strip() or None,
            )
            return jsonify({"hifz_log": log}), 201
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/incidents")
    def incidents_list():
        return jsonify({"incidents": storage.list_incidents()})

    @app.post("/api/incidents")
    def incidents_create():
        body = payload()
        student_id = parse_int(body.get("student_id"), 0, 1, 100000)
        category = str(body.get("category", "")).strip()
        description = str(body.get("description", "")).strip()
        if not student_id or not category or not description:
            return jsonify({"error": "student_id, category and description are required"}), 400
        try:
            incident = storage.add_incident(
                student_id=student_id,
                category=category,
                description=description,
                action_taken=str(body.get("action_taken", "")),
                reported_by=str(body.get("reported_by", "system")),
                incident_on=str(body.get("incident_on", "")).strip() or None,
            )
            return jsonify({"incident": incident}), 201
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/timetable")
    def timetable_list():
        day_name = request.args.get("day_name")
        return jsonify({"timetable": storage.list_timetable(day_name=day_name)})

    @app.post("/api/timetable")
    def timetable_create():
        body = payload()
        class_name = str(body.get("class_name", "")).strip()
        day_name = str(body.get("day_name", "")).strip()
        period_no = parse_int(body.get("period_no"), 0, 1, 20)
        subject = str(body.get("subject", "")).strip()
        start_time = str(body.get("start_time", "")).strip()
        end_time = str(body.get("end_time", "")).strip()
        if not class_name or not day_name or not period_no or not subject or not start_time or not end_time:
            return jsonify(
                {
                    "error": (
                        "class_name, day_name, period_no, subject, "
                        "start_time and end_time are required"
                    )
                }
            ), 400
        try:
            entry = storage.add_timetable_entry(
                class_name=class_name,
                day_name=day_name,
                period_no=period_no,
                subject=subject,
                teacher_name=str(body.get("teacher_name", "")),
                start_time=start_time,
                end_time=end_time,
            )
            return jsonify({"timetable_entry": entry}), 201
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    return app


app = create_app()


if __name__ == "__main__":
    host = os.environ.get("LMS_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", os.environ.get("LMS_PORT", "5050")))
    debug = parse_bool(os.environ.get("LMS_DEBUG"), False)
    app.run(host=host, port=port, debug=debug)

