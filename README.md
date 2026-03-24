# Jamia Ajmal ul Madaris LMS

This repository contains a standalone Flask-based LMS for a Jamia / Mudrassa college
with support for institutions up to around 500 students.

## Core Features

- Student admission and student profile management.
- Fees management (dues, partial payments, payment recording).
- Student and teacher attendance management.
- Papers/exams setup and marks entry.
- Student progress report generation and publishing.
- Parent user management with parent portal login access.

## Additional Mudrassa Features

- Hifz progress tracking (surah/para/ayat/revision grade).
- Discipline incident tracking.
- Class timetable management.
- Announcements for students/parents/staff.
- Library management (book stock, issue, return).
- Hostel room allocation management.

## Run locally

1. Install dependencies:
   - `pip install -r requirements.txt`
2. Start:
   - `python3 -m non_voip_numbers_app.app`
3. Open:
   - `http://127.0.0.1:5050`

Default seeded admin credentials:

- username: `admin`
- password: `admin123`

## Run locally

1. Install dependencies:
   - `pip install -r requirements.txt`
2. Optional configuration:
   - copy `non_voip_numbers_app/.env.example` to `non_voip_numbers_app/.env`
3. Start:
   - `python3 -m non_voip_numbers_app.app`
4. Open:
   - `http://127.0.0.1:5050`

## Deploy on Railway

`railway.json` is included and starts:

- `gunicorn --workers 2 --threads 4 --timeout 120 --bind 0.0.0.0:$PORT non_voip_numbers_app.app:app`

Health check path:

- `/health`

