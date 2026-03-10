# Non-VoIP Virtual Number Manager

This is a standalone Flask app for:

- searching available virtual numbers from API providers,
- buying and managing numbers,
- sending SMS,
- starting outbound calls,
- enforcing a **non-VoIP-only** filter when line-type lookup is available.

## Why this setup is low-cost

The app includes a provider ranking to keep costs predictable:

1. **Telnyx** (integrated) - commonly low monthly rental for local numbers.
2. **Plivo** (recommended, not wired in this version) - very low rental rates in some regions.
3. **Twilio** (integrated) - reliable and widely available, often a bit higher cost.

> Prices vary by country/number type and can change. Treat displayed values as directional estimates.

## Features

- Unified number management dashboard.
- Provider adapters:
  - `mock` (works instantly for local testing),
  - `telnyx` (real API),
  - `twilio` (real API).
- SQLite persistence for managed numbers and call/SMS logs.
- Sync owned numbers from providers into the local dashboard.

## Setup

From repo root:

1. Optional: create local env file:
   - Copy `non_voip_numbers_app/.env.example` to `non_voip_numbers_app/.env`
   - Fill API credentials.
2. Run the app:
   - `python3 -m non_voip_numbers_app.app`
3. Open:
   - `http://127.0.0.1:5050`

## Railway deployment

This repo now includes a root `railway.json` that deploys this app with Gunicorn:

- Start command:
  - `gunicorn --workers 2 --threads 4 --timeout 120 --bind 0.0.0.0:$PORT non_voip_numbers_app.app:app`
- Health check:
  - `/health`

### Deploy steps (Railway UI)

1. Create a new Railway project from this GitHub repo/branch.
2. Ensure root directory is repo root (`/`), not subfolder.
3. Add environment variables:
   - `TELNYX_API_KEY` (for Telnyx),
   - `TELNYX_CONNECTION_ID` (for Telnyx outbound calls),
   - `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` (if using Twilio).
4. Deploy.
5. Verify:
   - `GET https://<your-railway-domain>/health` returns `{"ok": true}`.

## Environment variables

See `.env.example` for all options.

Important keys:

- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TELNYX_API_KEY`
- `TELNYX_CONNECTION_ID` (required for Telnyx outbound calls)

## Non-VoIP filtering behavior

- The dashboard defaults to `non_voip_only=true`.
- Line-type detection is provider lookup-based:
  - Twilio: Lookup API (line type intelligence)
  - Telnyx: Number Lookup API (`portability.line_type` / `carrier.type`)
- If line type cannot be determined, result is `unknown`.

