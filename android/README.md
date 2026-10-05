# ShibaClaw Android companion

Native Jetpack Compose app. Talks to the **same WebUI URL** you already open in a browser.

## Pair

1. Sideload the APK
2. Paste the Shiba URL (`https://your-host`), WebUI username + password
3. Connect — app logs in (`POST /api/auth/login`) then opens `wss://…/ws`
4. Long-press home → Widgets → **Shiba**

## App

- Chat with streaming, markdown, tool/thinking chips, stop, queue/steer
- Sessions drawer (list, search, rename, archive, delete) — web + android sessions together
- Model / profile picker
- Photo & file attachments via `/api/upload`
- Agent reply notifications when the app is backgrounded
- Theme: system / dark / light (WebUI gold palette)

## Widget

- Tap plays a short clip (boop / wag / jump). Frames are pushed by the service, so the pet moves even on launchers that ignore `ViewFlipper`. Idle blinks on its own.
- Bubble rotates: phone notification counts → world news → fact → mood (server digest)
- Double-tap starts a short chat turn
- Notification access (Settings → Allow notification access) is optional; counts stay on-device

Digest: phone sends `digest_request` on connect and hourly; WebUI runs a dedicated `android:{id}:digest` agent turn with `web_search`.

## Phone tools

After you deploy this repo’s WebUI/gateway, the agent can call `list_apps`, `launch_app`, `open_setting` on the phone.

## Build

```bash
cd android
./gradlew :app:assembleDebug
```

Regenerate pet frames from `assets/shiba_pet/`:

```bash
uv run --with pillow python scripts/gen_shiba_widget_assets.py
```

APK: `android/ShibaClaw-companion-debug.apk` (also `app/build/outputs/apk/debug/`).
