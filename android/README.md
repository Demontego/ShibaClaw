# ShibaClaw Android companion

Native Kotlin app (no WebView). Talks to the **same WebUI URL** you already open in a browser.

## Pair

1. Sideload the APK
2. Paste the Shiba URL (`https://your-host`), WebUI username + password
3. Connect — app logs in (`POST /api/auth/login`) then opens `wss://…/ws`
4. Long-press home → Widgets → **Shiba**

Tap = boop (local). Double-tap = short chat. Chat screen is native bubbles.

Nginx / Caddy must already proxy `/ws` (browser chat uses it). No extra 19998 port.

## Phone tools (this branch on the server)

After you deploy this repo’s WebUI/gateway, the agent can call `list_apps`, `launch_app`, `open_setting` on the phone. Chat works against an already-running WebUI even before that deploy.

## Build

```bash
cd android
./gradlew :app:assembleDebug
```

APK: `android/ShibaClaw-companion-debug.apk` (also `app/build/outputs/apk/debug/`).
