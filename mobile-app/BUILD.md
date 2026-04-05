# 2ndCall Mobile App Build Guide

## Prerequisites

- Node.js 18+ and npm
- Android Studio (for Android APK)
- Xcode 15+ (for iOS, Mac only)

## Setup

```bash
cd mobile-app
npm install
npx cap sync
```

## Android APK

```bash
# Open in Android Studio
npx cap open android

# OR build from command line (requires ANDROID_HOME set):
cd android
./gradlew assembleRelease

# APK output: android/app/build/outputs/apk/release/app-release.apk
```

### Sign the APK for Play Store

```bash
# Generate keystore (one-time)
keytool -genkey -v -keystore 2ndcall.keystore -alias 2ndcall -keyalg RSA -keysize 2048 -validity 10000

# Sign
jarsigner -verbose -keystore 2ndcall.keystore android/app/build/outputs/apk/release/app-release-unsigned.apk 2ndcall

# Align
zipalign -v 4 app-release-unsigned.apk 2ndcall-signed.apk
```

## iOS

```bash
# Open in Xcode (Mac only)
npx cap open ios

# Then: Product > Archive in Xcode
# Upload to App Store Connect via Xcode Organizer
```

## Configuration

The app connects to the production backend:
`https://2ndcallcom-production-dcdb.up.railway.app`

To change, edit `capacitor.config.json` > `server.url`
