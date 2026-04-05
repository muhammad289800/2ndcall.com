# 2ndcall.com - Non-VoIP Number Manager

This repository contains the standalone app for managing non-VoIP virtual numbers.

## Features

- Search available numbers from provider APIs.
- Buy and manage numbers in one dashboard.
- Send SMS from owned numbers.
- Start outbound calls from owned numbers.
- **WebRTC calling** - make and receive real-time calls directly in the browser or Android app.
- Filter/purchase only non-VoIP numbers (line-type lookup based).

## Android App

The `mobile-app/` directory contains a Capacitor-based Android wrapper with:

- Telnyx WebRTC Android SDK (`com.telnyx.webrtc.lib:library:1.0.1`) for native calling
- WebView WebRTC permission grants for browser-based calling
- Audio permissions (microphone, Bluetooth, audio settings)

To build the Android app:

1. `cd mobile-app && npm install`
2. `npx cap sync android`
3. `npx cap open android` (opens in Android Studio)

## Providers

- Telnyx (integrated)
- Twilio (integrated)
- Mock provider (local testing)

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

