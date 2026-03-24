# Jamia Ajmal ul Madaris LMS

This is a Flask-based LMS for mudrassa/college administration and parent reporting.

## Core modules implemented

- Student admission and lifecycle records.
- Fee charging, partial/full payment, and pending dues tracking.
- Student and teacher attendance management.
- Papers/exams management and marks entry.
- Progress report generation with attendance + academics + fee summary.
- User management (admin, teacher, parent, accountant, staff).
- Parent account linking and parent portal access.

## Additional mudrassa-focused modules

- Hifz progress tracking (surah/para/ayat + revision grade).
- Discipline incidents and action-taken records.
- Class timetable management.
- Announcements for parents/students/teachers.
- Library management (books, issue/return workflow).
- Hostel management (rooms + allocations).

## Default admin login

- Username: `admin`
- Password: `admin123`

## Setup

From repo root:

1. Optional: create local env file:
   - Copy `non_voip_numbers_app/.env.example` to `non_voip_numbers_app/.env`
2. Run the app:
   - `python3 -m non_voip_numbers_app.app`
3. Open:
   - `http://127.0.0.1:5050`

## Typical usage flow

1. Admit students and create teachers.
2. Create/link parent users for each student.
3. Record fees and submit payments.
4. Mark student/teacher attendance daily.
5. Create papers and enter marks.
6. Publish parent reports and access them from parent portal.
7. Use Hifz, library, hostel, timetable, and announcements modules as needed.

## Railway deployment

This repo now includes a root `railway.json` that deploys this app with Gunicorn:

- Start command:
  - `gunicorn --workers 2 --threads 4 --timeout 120 --bind 0.0.0.0:$PORT non_voip_numbers_app.app:app`
- Health check:
  - `/health`

### Deploy steps (Railway UI)

1. Create a new Railway project from this GitHub repo/branch.
2. Ensure root directory is repo root (`/`), not subfolder.
3. Deploy.
4. Verify:
   - `GET https://<your-railway-domain>/health` returns `{"ok": true, "service": "Jamia Ajmal ul Madaris LMS"}`.

