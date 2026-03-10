# AGENTS.md

## Cursor Cloud specific instructions

### Overview

This is a single-service Python/Flask app ("Non-VoIP Virtual Number Manager") that manages virtual phone numbers via telecom provider APIs. It uses SQLite (auto-created, zero config) and ships with a built-in **mock provider** so the full workflow can be tested locally without any API keys.

### Running the app

```
python3 -m non_voip_numbers_app.app
```

Serves on `http://127.0.0.1:5050`. Health check: `GET /health`.

See `README.md` for full details.

### Key caveats

- No linter, formatter, or test framework is configured in this repo. There are no automated tests to run.
- The app loads env vars from `non_voip_numbers_app/.env` if it exists (custom parser, not python-dotenv). Copy `.env.example` to `.env` for local config; all values are optional for mock-provider usage.
- SQLite DB is created at `non_voip_numbers_app/non_voip_numbers.db` on first run. Delete this file to reset state.
- `requirements.txt` includes many unused dependencies (telethon, openai, pandas, etc.) from a broader project. Only `flask`, `gunicorn`, and `requests` are actually imported.
- The mock provider is always available and requires no configuration. Use `"provider": "mock"` in API calls or select "Mock Provider (Local Testing)" in the UI dropdown.
- Twilio/Telnyx providers require env vars (`TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN`, `TELNYX_API_KEY`) and are optional for local development.
