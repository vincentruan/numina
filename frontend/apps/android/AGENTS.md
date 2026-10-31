# AGENTS.md — Android Shell

Capacitor-based WebView wrapper that connects to a self-hosted Numina server.

## What This Is

A thin native shell — not a full app. After initial server setup, the WebView navigates to the remote H5 and the shell just provides native back-button handling and deep-link support.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Native | Capacitor 8 + Android (Kotlin/Java) |
| Web runtime | Vue 3 + TypeScript + Vite |
| Storage | `@capacitor/preferences` (SharedPreferences) |

## Commands

```bash
pnpm run dev              # Vite dev server on :5175
pnpm run build            # Type-check + Vite build
pnpm run typecheck        # vue-tsc --noEmit
pnpm run test             # Same as typecheck (no unit tests yet)
pnpm run cap:sync         # Sync web assets to native project
pnpm run android:build-debug  # Full debug APK build
```

Native tests (run from `android/` directory):
```bash
./gradlew test            # JUnit tests for BackExitGuard + DeepLink
```

## Architecture

```
src/
├── App.vue               # Auto-connect if server saved, else <router-view />
├── main.ts               # Vue bootstrap
├── router/index.ts       # Two routes: / (setup) and /advanced
├── pages/
│   ├── SetupPage.vue     # Server URL input + validation
│   └── AdvancedSettingsPage.vue  # Clear config, HTTP toggle, about
├── utils/server-config.ts  # Capacitor Preferences wrapper + URL classifier
└── bridge/types.ts       # Native↔web bridge type definitions

android/app/src/main/java/app/numina/mobile/
├── MainActivity.java     # Back-button exit guard, deep-link routing
├── BackExitGuard.java    # Double-tap-back to exit logic
└── DeepLink.java         # numina:// URL parsing
```

## Key Constraints

- **`@capacitor/app`** — JS-side back-button handler is disabled (`disableBackButtonHandler: true` in `capacitor.config.ts`) because `MainActivity.java` owns history walking. The native plugin is still installed and provides the `App` plugin config namespace.
- **`allowNavigation: ['*']`** — Required because the user configures their own server host at setup time. Without it, Capacitor's bridge would route the post-setup redirect to the system browser.
- **No mixed content** — `allowMixedContent` stays at default (false). LAN cleartext is allowed via `usesCleartextTraffic` in AndroidManifest, but mixed content would downgrade HTTPS subresources.
- **Version string** — `__APP_VERSION__` is injected at build time from `package.json` via Vite `define`. Bump version in `package.json`, not in the Vue file.
- **URL classification** — `classifyUrl()` in `server-config.ts` classifies URLs for UX messaging. Security enforcement (blocking public HTTP, gating LAN HTTP behind advanced mode) also lives there.

## Touch Targets

All interactive elements must be ≥ 44×44px per WCAG/mobile H5 guidelines. Check `min-height: 44px` or equivalent padding when adding new buttons/links.
