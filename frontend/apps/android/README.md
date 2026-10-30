# Numina Android Shell

Thin Capacitor WebView wrapper for the Numina self-hosted family asset platform.

## Architecture

This is **not** a separate app — it's a thin native shell that:

1. Shows a server URL setup page on first launch (native Vue)
2. After setup, navigates the WebView to the remote Numina H5
3. Acts as a browser-like wrapper with native back button handling

All business logic runs in the remote Numina H5. This shell adds ~10MB of Capacitor runtime and nothing else.

## Development

```bash
# Install dependencies (from workspace root)
pnpm install

# Dev mode (browser testing of setup page)
pnpm dev          # http://localhost:5175

# Build web assets
pnpm build

# Sync web assets to Android project
pnpm cap:sync

# Open in Android Studio
pnpm cap:open

# Build debug APK (requires Android SDK)
pnpm android:build-debug
```

## Prerequisites

### Android SDK

Install Android command-line tools or Android Studio:

```bash
# Option 1: Android Studio (recommended for development)
# Download from https://developer.android.com/studio

# Option 2: Command-line tools only
# Download from https://developer.android.com/studio#command-line-tools-only
# Then:
sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"
```

Set environment variables:

```bash
export ANDROID_HOME="$HOME/Library/Android/sdk"  # macOS
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export PATH="$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"
```

### Java

Java 17+ is required. The project uses OpenJDK 25 (installed via Zulu).

## Server URL Configuration

On first launch, the app shows a setup page where users enter their Numina server URL.

### Supported URL types

| Type | Example | Policy |
|------|---------|--------|
| HTTPS | `https://numina.example.com` | ✅ Recommended |
| LAN HTTP | `http://192.168.1.100:80` | ⚠️ Requires "Advanced Mode" toggle |
| localhost | `http://localhost:5173` | 🛠 Dev only |
| Public HTTP | `http://numina.example.com` | 🚫 Blocked |

### How it works

1. Server URL is saved to `SharedPreferences` via `@capacitor/preferences`
2. WebView navigates to `{serverUrl}/` — the remote Numina H5 loads
3. Cookie auth works transparently (same-origin for the WebView)
4. Login state persists across app restarts

## Back Button

The Android back button walks through WebView history. When there is no history
left, the first press shows a "Press back again to exit" toast and the second
press within two seconds exits the app — a stray press can't drop you out of a
long-lived session.

Handled through `OnBackPressedDispatcher` rather than `onBackPressed()`, because
predictive back (default for `targetSdk` 34+) bypasses the legacy callback.

## Deep Links

`numina://open/<path>` opens the app at that route:

```bash
adb shell am start -a android.intent.action.VIEW -d "numina://open/reminders"
```

The `<path>` is appended to the configured server URL, so the example loads
`{serverUrl}/reminders`. Query and fragment survive the hop
(`numina://open/reminders?tab=due`). A link arriving before the WebView is ready
is queued and applied on the first page load; if no server is configured yet, it
is held until setup completes.

HTTPS app links are deliberately not used — they require Digital Asset Links
verification of a domain, which does not fit self-hosted deployments on
arbitrary domains.

## Release Build

Release builds read signing credentials from `android/keystore.properties`,
which is gitignored. Start from the template:

```bash
cp android/keystore.properties.example android/keystore.properties
# edit it, then:
cd android && ./gradlew assembleRelease
```

Without that file the release build still completes, signed with the debug key —
fine for local installs, not for distribution.

## Project Structure

```
frontend/apps/android/
├── src/
│   ├── pages/
│   │   ├── SetupPage.vue           # Server URL configuration
│   │   └── AdvancedSettingsPage.vue # Advanced options (HTTP toggle)
│   ├── bridge/types.ts             # NativeEvent types (Phase 2b contract)
│   ├── router/index.ts             # Hash-based routing
│   ├── utils/server-config.ts      # URL persistence + validation
│   ├── App.vue                     # Root component + auto-redirect
│   └── main.ts                     # Entry point
├── android/                        # Native Android project (Capacitor)
│   ├── keystore.properties.example # Release signing template
│   └── app/src/main/
│       ├── AndroidManifest.xml     # cleartext traffic + deep link filter
│       └── java/.../
│           ├── MainActivity.java   # Back button, deep links
│           ├── DeepLink.java       # Deep link URL translation
│           └── BackExitGuard.java  # Exit confirmation timing
├── capacitor.config.ts             # Capacitor configuration
├── package.json
└── vite.config.ts
```

## Future Enhancements

- **Native push**: FCM integration plus the `NativeEvent` runtime bridge
- **Full native bridge**: file picker, camera, download via Capacitor plugins
- **iOS Support**: Add iOS platform via `npx cap add ios`
