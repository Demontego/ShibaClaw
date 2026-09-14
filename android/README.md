# ShibaClaw Android companion (prototype)

Home-screen **Shiba widget** + device tools. The LLM stays on the gateway; the phone is the body.

## What you get

- 2×2 transparent widget: polygonal Shiba face (idle / think / sleep / alert / error / boop)
- **Tap** — boop (haptic, squash face). No LLM call.
- **Double-tap** — short `chat` turn on the server (“user booped the widget”)
- Chat activity for longer talk
- Tools the model can call while that session is active: `list_apps`, `launch_app`, `open_setting`

## Server

Gateway WebSocket (default **19998**) must be reachable from the phone:

```bash
shibaclaw gateway --host 0.0.0.0
```

Docker binds `127.0.0.1` by default — use Tailscale, or publish `19998` on LAN. Phone talks **plain `ws://`** (LAN). Put TLS in front later.

Protocol (after TCP):

1. `{ "type":"hello", "role":"device", "device_id":"…", "label":"Pixel", "token":"" }`
2. Server replies `hello_ok` and registers `list_apps` / `launch_app` / `open_setting`
3. Chat: `{ "type":"request", "id":"c1", "action":"chat", "payload":{ "content":"…" } }`
4. Tool calls arrive as `{ "type":"event", "name":"device.tools.invoke", "payload":{ "id","name","arguments" } }`
5. Phone answers `action: device.tools.result`

## Build the APK

Android Studio: open the `android/` folder, Sync, Run on a device.

CLI (SDK + JDK 17):

```bash
cd android
# echo "sdk.dir=/path/to/Android/Sdk" > local.properties
./gradlew :app:assembleDebug
# apk: app/build/outputs/apk/debug/app-debug.apk
```

Sideload. This is a companion with `QUERY` for launcher apps — Play Store review is a later problem.

## Phone

1. Install APK, allow notifications
2. Host = gateway IP (not `127.0.0.1`), port `19998`
3. Connect
4. Long-press home → Widgets → **Shiba**
5. Tap the dog. Double-tap to talk.

`open_setting` opens the Settings **page**. It does not flip system toggles (Android forbids that without Shizuku).
