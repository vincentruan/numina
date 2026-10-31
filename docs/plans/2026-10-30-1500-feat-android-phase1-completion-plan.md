---
title: Android Phase 1 Completion - Plan
type: feat
date: 2026-10-30
topic: android-phase1-completion
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
execution: code
---

## Goal Capsule

- **Objective:** Complete the Phase 1 Android shell so users can deep-link into specific pages, safely exit with the back button, and distribute a signed release APK.
- **Product authority:** `frontend/apps/android/`
- **Open blockers:** None

---

Product Contract preservation: restructured, no scope change — R1 and R3 moved to Scope Boundaries as Phase 2b deferrals (user-confirmed), superseded by KTD1; R2 retained as the Phase 1 deliverable.

## Product Contract

### Summary

Deep link handler (`numina://open/{path}` scheme), back button "press again to exit" toast, release APK signing config, and `NativeEvent` type declarations reserved for Phase 2b. The runtime JS bridge (`navigate`) is deferred to Phase 2b — see Scope Boundaries.

### Problem Frame

The Android shell can launch, configure a server URL, and load the remote Numina H5. However, three interaction gaps remain:

1. **No deep link support** — external triggers (notification taps, shared links) cannot open the app at a specific page. Users must launch the app and navigate manually.
2. **Back button lacks exit confirmation** — when the WebView has no history, pressing back exits immediately. Users may exit accidentally with no way to return.
3. **No release build pipeline** — only debug APKs can be built. Distribution to testers or production requires manual signing.

Completing these items makes the Android shell a fully functional Phase 1 deliverable ready for device testing and distribution.

### Key Decisions

**Back button uses native WebView history, not JS bridge.** After setup, `window.location.href = savedUrl` navigates the WebView to the remote H5. The shell's Vue router is no longer active; the remote H5 manages its own routing. The native `webView.goBack()` correctly walks through WebView history. A JS bridge `goBack → router.back()` pattern would require the H5 to expose a navigation API, adding complexity with no benefit.

**Deep link is `numina://` scheme only, no HTTPS app links.** HTTPS app links require Digital Asset Links verification (a JSON file on the server). Numina is self-hosted — each deployment has a different domain. Hardcoding a domain in the app or requiring every user to configure domain verification is impractical for Phase 1. The `numina://open/{path}` scheme works for any deployment without server-side configuration.

**Minimal bridge scope — NativeEvent types only in Phase 1.** The ideation document §5.7 defines a full bridge protocol (getFile, takePhoto, download, getDeviceInfo, navigate). However, §5.8 shows file picker and camera already work via standard HTML APIs in WebView, and Phase 1 deep links are handled natively. Only the `NativeEvent` interface (pushClick, networkChange, appResume) is declared, as TypeScript types for Phase 2b FCM integration. (session-settled: user-directed — chose minimal over full bridge per ideation §5.7; narrowed further during planning — see Open Questions)

### Requirements

**JS Bridge**

- R1. Bridge protocol supports a `navigate` method (H5 → native) that tells the WebView to load `{serverUrl}/{path}`. **Deferred to Phase 2b** — see Scope Boundaries and KTD1.
- R2. Bridge protocol defines `NativeEvent` types (`pushClick`, `networkChange`, `appResume`) as TypeScript type declarations only. No runtime handler is implemented in Phase 1; the types exist so Phase 2b can add FCM push click navigation without redesigning the bridge.
- R3. Bridge uses `window.postMessage()` for H5→Native messaging and Capacitor's `addListener()` or `postMessage()` for Native→H5. The bridge is a thin message-passing layer, not a full RPC system. **Deferred to Phase 2b** — see Scope Boundaries and KTD1.

**Deep Link**

- R4. `AndroidManifest.xml` declares an intent filter for the `numina://open/{path}` scheme. The filter matches `ACTION_VIEW` with category `DEFAULT`.
- R5. Deep link handler extracts the path from the intent URI and navigates the WebView to `{serverUrl}/{path}`. If the app is in the foreground with the WebView showing the remote H5, the handler calls `webView.loadUrl()` within the existing WebView instance.
- R6. When the app is killed and a deep link arrives, the app launches, shows the setup page (if no server URL is configured) or loads the server URL, then navigates to the deep link path. The deep link path is queued until the WebView is ready.

**Back Button**

- R7. Back handling walks WebView history first, then confirms before exiting. If `webView.canGoBack()` is true it navigates back; otherwise it shows a "Press back again to exit" toast. Implemented via `OnBackPressedDispatcher`, since predictive back (default at the project's `targetSdk` 36) bypasses the legacy `onBackPressed()` callback.
- R8. The exit confirmation toast disappears after 2 seconds. A second back press within 2 seconds calls `finish()` to exit the app. A second back press after 2 seconds shows the toast again (the timer resets).
- R9. The toast uses Android's native `Toast.makeText()` with `Toast.LENGTH_SHORT`. The 2-second timeout is tracked via a `lastBackPressTime` field in `MainActivity`.

**Release Build**

- R10. `android/app/build.gradle` includes a `signingConfigs` block that reads from `keystore.properties` (located at `android/keystore.properties`). The properties file contains `storeFile`, `storePassword`, `keyAlias`, `keyPassword`.
- R11. The `buildTypes.release` block applies the signing config. If `keystore.properties` does not exist, the release build falls back to debug signing (so CI or fresh clones can still build).
- R12. `keystore.properties` is added to `.gitignore` so signing credentials are never committed. A `keystore.properties.example` file documents the expected format.

### Key Flows

- F1. **Deep link from killed state**
  - **Trigger:** User taps `numina://open/reminders` while app is not running.
  - **Actors:** Android system, MainActivity, WebView
  - **Steps:** System launches app with `ACTION_VIEW` intent. `MainActivity.onCreate()` extracts the URI. If no server URL is configured, the setup page loads first; after setup, the deep link path is navigated. If a server URL exists, the WebView loads `{serverUrl}/reminders`.
  - **Outcome:** App opens at the /reminders page.

- F2. **Deep link from background/foreground**
  - **Trigger:** User taps `numina://open/ai/chat/thread_123` while app is running.
  - **Actors:** Android system, MainActivity, WebView
  - **Steps:** System delivers intent to existing `MainActivity` via `onNewIntent()`. Handler extracts path `/ai/chat/thread_123` and calls `webView.loadUrl(serverUrl + "/ai/chat/thread_123")`.
  - **Outcome:** WebView navigates to the AI chat thread.

- F3. **Back button exit sequence**
  - **Trigger:** User presses Android back button when WebView has no history.
  - **Actors:** User, MainActivity
  - **Steps:** First press: `webView.canGoBack()` returns false. `MainActivity` shows toast "Press back again to exit" and records `lastBackPressTime = System.currentTimeMillis()`. Second press within 2 seconds: `System.currentTimeMillis() - lastBackPressTime < 2000` is true. `MainActivity` calls `finish()`. Second press after 2 seconds: timer expired. Toast shown again, `lastBackPressTime` updated.
  - **Outcome:** App exits on second press within 2 seconds; otherwise toast resets.

### Scope Boundaries

- **Full bridge protocol (getFile, takePhoto, download, getDeviceInfo)** — deferred. File picker and camera already work via standard HTML APIs in WebView. Native file download and device info can be added in a future phase if needed.
- **Runtime JS bridge (R1 navigate method, R3 postMessage handling)** — deferred to Phase 2b (user-confirmed). Deep links are handled natively in Phase 1; the runtime bridge is only needed when FCM push clicks require Native→H5 messaging.
- **HTTPS app links / Digital Asset Links** — deferred. Requires per-deployment domain verification, impractical for self-hosted Numina.
- **CI/CD pipeline for release builds** — deferred. Local signing config is sufficient for Phase 1. CI integration can be added later.
- **iOS support** — deferred. Phase 1 focuses on Android. Capacitor is cross-platform; iOS can be added with minimal additional work.
- **Phase 2 items (FCM push, device registration, notification preferences, quiet hours)** — not in scope. These belong to Phase 2a and Phase 2b.

### Acceptance Examples

- AE1. **Deep link navigates to correct page from killed state**
  - **Covers R4, R5, R6.**
  - **Given:** App is not running. Server URL is configured.
  - **When:** User taps `numina://open/reminders`.
  - **Then:** App launches, WebView loads `{serverUrl}/reminders`.

- AE2. **Deep link navigates from background**
  - **Covers R4, R5.**
  - **Given:** App is running in foreground, WebView shows dashboard.
  - **When:** User taps `numina://open/ai/chat/thread_123`.
  - **Then:** WebView navigates to `{serverUrl}/ai/chat/thread_123`.

- AE3. **Back button exits after double-press**
  - **Covers R7, R8, R9.**
  - **Given:** WebView has no history (at root).
  - **When:** User presses back once, sees toast. User presses back again within 2 seconds.
  - **Then:** App exits.

- AE4. **Release APK installs and runs**
  - **Covers R10, R11, R12.**
  - **Given:** `keystore.properties` is configured with valid signing credentials.
  - **When:** Developer runs `./gradlew assembleRelease`.
  - **Then:** Signed release APK is produced at `android/app/build/outputs/apk/release/app-release.apk`. APK installs on an Android device and runs.

### Open Questions

None. R1 and R3 are deferred to Phase 2b (user-confirmed) — see Scope Boundaries and KTD1.

### Dependencies / Assumptions

- **Dependencies:** Capacitor 5.x (already installed in `frontend/apps/android/`). Android SDK (platform-tools, build-tools 34.0.0). Java 17+.
- **Assumptions:** The remote Numina H5 handles its own routing correctly when the WebView loads a deep link URL. The server URL is already configured (or the setup page flow handles first-time configuration before deep link navigation).

### Sources / Research

- Ideation document: `docs/ideation/2026-10-30-android-app-push-architecture-ideation.html` — Phase 1 backlog (P1-4, P1-5, P1-6, P1-8), §5.6-5.9 (architecture details).
- Existing Android shell: `frontend/apps/android/` — current implementation (setup page, WebView host, back button basic handler).

---

## Planning Contract

### Key Technical Decisions

KTD1. **Runtime JS bridge deferred to Phase 2b; only NativeEvent types ship in Phase 1.** The shell's `App.vue` is replaced by the remote H5 after setup, so a bridge listener there never executes; deep links are handled natively via `webView.loadUrl()`. The remote H5 cannot import code from `frontend/apps/android/`, so a runtime bridge would be unreachable. `NativeEvent` types ship now as a contract for Phase 2b FCM push click navigation.

KTD2. **Deep link handler queues the path until WebView is ready.** When a deep link arrives and the WebView is still loading the setup page or the initial server URL, the handler stores the path in a `pendingDeepLink` field. `webViewReady` is set in a custom `WebViewClient` installed on `getBridge().getWebView()` in `MainActivity.onCreate()`; `onPageFinished()` sets the flag and drains `pendingDeepLink`. This prevents race conditions where the deep link arrives before the WebView can navigate.

KTD3. **Back handling registers an `OnBackPressedCallback` on the dispatcher, not `onBackPressed()`.** With predictive back enabled by default at `targetSdk` 36, the legacy override is never invoked, which would silently disable both WebView history walking and the exit prompt. The confirmation timing lives in a framework-free `BackExitGuard` so it is unit-testable without an emulator.

KTD4. **Release signing config reads from a properties file, not hardcoded values.** The `keystore.properties` file contains sensitive credentials (storePassword, keyPassword) and is gitignored. The `build.gradle` reads the file at build time and falls back to debug signing if the file is missing. This allows CI environments to build without the properties file while keeping credentials out of version control.

### Assumptions

- The remote Numina H5 handles its own routing correctly when the WebView loads a deep link URL (e.g., `{serverUrl}/reminders` loads the reminders page).
- The Capacitor version in `frontend/apps/android/` supports `postMessage` and `addListener` APIs (Capacitor 5.x does).
- Android SDK build-tools 34.0.0 and platform 34 are available (already specified in the README prerequisites).

---

## Implementation Units

### U1. NativeEvent Type Declarations (Phase 2b Prep)

**Goal:** Declare NativeEvent TypeScript types for Phase 2b FCM push click navigation. The runtime bridge (H5→Native navigate method) is deferred to Phase 2b when FCM integration requires Native→H5 messaging.

**Requirements:** R2 (R1 and R3 deferred to Phase 2b)

**Dependencies:** None

**Files:**
- `frontend/apps/android/src/bridge/types.ts` (create)

**Approach:**
1. Create `types.ts` with the NativeEvent interface:
   ```typescript
   export interface NativeEvent {
     type: 'pushClick' | 'networkChange' | 'appResume';
     data: unknown;
   }
   ```
2. Export the type for use by Phase 2b FCM integration.
3. The runtime bridge (navigate method, postMessage handling) is deferred to Phase 2b when:
   - FCM push clicks require Native→H5 messaging to navigate the WebView
   - The remote H5 is modified to listen for NativeEvent messages
   - The native side implements the postMessage sender

**Rationale:** Phase 1 deep links are handled natively by U2 (intent filter + webView.loadUrl()). The shell's App.vue is replaced by the remote H5 after setup, so a bridge listener in App.vue would never execute. The bridge runtime is only needed in Phase 2b for FCM push click navigation.

**Patterns to follow:**
- TypeScript interface declarations for event types.

**Test scenarios:**
- Test expectation: none — this unit only declares types with no runtime behavior.

**Verification:** The types.ts file compiles without errors and exports the NativeEvent interface.

---

### U2. Deep Link Handler

**Goal:** Add intent filter for `numina://open/{path}` scheme and implement a handler that navigates the WebView to the deep link path.

**Requirements:** R4, R5, R6

**Dependencies:** None

**Files:**
- `frontend/apps/android/android/app/src/main/AndroidManifest.xml` (modify)
- `frontend/apps/android/android/app/src/main/java/app/numina/mobile/MainActivity.java` (modify)
- `frontend/apps/android/android/app/src/main/java/app/numina/mobile/DeepLink.java` (create)
- `frontend/apps/android/android/app/src/test/java/app/numina/mobile/DeepLinkTest.java` (create)

**Approach:**
1. Add an intent filter to `AndroidManifest.xml` inside the `<activity>` tag:
   ```xml
   <intent-filter>
     <action android:name="android.intent.action.VIEW" />
     <category android:name="android.intent.category.DEFAULT" />
     <category android:name="android.intent.category.BROWSABLE" />
     <data android:scheme="numina" android:host="open" />
   </intent-filter>
   ```
2. Create `DeepLink.java` holding the URL rules with no Android framework state, so they unit-test on the JVM: `isDeepLink` (scheme + host match), `routeFrom` (path retained, query and fragment preserved, bare host yields `/`), and `targetUrl` (joins server URL and route, tolerating trailing/leading slashes).
3. Modify `MainActivity.java`:
   - Hold a nullable `pendingRoute` and a `webViewReady` flag.
   - In `onCreate()`, register a `WebViewListener` on `getBridge()`; its `onPageLoaded` sets `webViewReady = true` and drains the queue. This uses Capacitor's own listener hook instead of replacing `BridgeWebViewClient`, which would break the bridge.
   - Override `onNewIntent()` to resolve the intent's URI through `DeepLink.routeFrom`, store it as `pendingRoute`, and attempt to drain.
   - `drainPendingRoute()` navigates only when both a route and a ready WebView exist; if no server URL is configured yet it leaves the route queued, since the setup page's own page load re-triggers the drain.
4. Read `serverUrl` from SharedPreferences (`CapacitorStorage` group, `numina_server_url` key) — the same store `@capacitor/preferences` writes from the setup page — stripping trailing slashes.

**Patterns to follow:**
- Android intent filter pattern: `<intent-filter>` with `ACTION_VIEW`, `DEFAULT`, `BROWSABLE` categories.
- Capacitor's `WebViewListener` extension point, rather than overriding or replacing Capacitor's `BridgeWebViewClient`.

**Test scenarios:**
- Covers F1. Deep link from killed state: Launch app with `adb shell am start -a android.intent.action.VIEW -d "numina://open/reminders"` and verify WebView loads `{serverUrl}/reminders`.
- Covers F2. Deep link from background: While app is running, trigger a deep link and verify WebView navigates to the target path.
- `DeepLinkTest` (JVM, no emulator): `numina://open/reminders` → `/reminders`; nested path preserved; bare `numina://open` and `numina://open/` → `/`; query and fragment preserved; non-`numina` scheme and non-`open` host rejected; malformed and null input rejected.
- `DeepLinkTest`: `targetUrl` joins server and route, tolerates a trailing slash on the server and a missing leading slash on the route, and returns null when no server is configured (so the route stays queued).

**Verification:** Deep links launch the app and navigate to the correct page in all three states (killed, background, foreground).

---

### U3. Back Button Enhancement

**Goal:** Add "press back again to exit" toast logic to the back button handler.

**Requirements:** R7, R8, R9

**Dependencies:** None

**Files:**
- `frontend/apps/android/android/app/src/main/java/app/numina/mobile/MainActivity.java` (modify)
- `frontend/apps/android/android/app/src/main/java/app/numina/mobile/BackExitGuard.java` (create)
- `frontend/apps/android/android/app/src/test/java/app/numina/mobile/BackExitGuardTest.java` (create)
- `frontend/apps/android/android/app/src/main/res/values/strings.xml` (modify)

**Approach:**
1. Add a `BackExitGuard` field (framework-free timing class) alongside a `pendingRoute`/`webViewReady` pair in `MainActivity`.
2. In `onCreate()`, register an `OnBackPressedCallback` via `getOnBackPressedDispatcher()`. Its handler:
   - Calls `webView.goBack()` and resets the guard when `webView.canGoBack()` is true.
   - Otherwise asks `BackExitGuard.onBackPressed(System.currentTimeMillis())`; `EXIT` calls `finish()`, `PROMPT` shows a `Toast` from the `press_back_again_to_exit` string resource.
3. `BackExitGuard` owns the two-second window as a named constant (`CONFIRM_WINDOW_MS`), with no Android dependencies so it unit-tests on the JVM.

**Patterns to follow:**
- `OnBackPressedDispatcher` with an `OnBackPressedCallback`, the supported path under predictive back.
- Toast text from a string resource, so it can be localized later.

**Test scenarios:**
- `BackExitGuardTest` (JVM, no emulator): first press returns `PROMPT`; a second press inside the window returns `EXIT`; a press exactly at the boundary and one past it both return `PROMPT`; a lapsed press re-arms so the following press exits; a press after `EXIT` starts fresh; `reset()` disarms; a non-positive clock never exits.
- `BackExitGuardTest`: the window constant equals 2000ms, asserted literally so a wrong value cannot pass.
- On-device: press back once (toast shown), press again within 2 seconds (app exits).
- On-device: WebView has history; back navigates without showing the toast.

**Verification:** Back button walks through WebView history, then shows toast, then exits on second press within 2 seconds.

---

### U4. Release Build Configuration

**Goal:** Add signing configuration for release APK builds.

**Requirements:** R10, R11, R12

**Dependencies:** None

**Files:**
- `frontend/apps/android/android/app/build.gradle` (modify)
- `frontend/apps/android/android/keystore.properties.example` (create)
- `frontend/apps/android/android/.gitignore` (modify)

**Approach:**
1. Create `keystore.properties.example` with placeholder values:
   ```
   storeFile=path/to/keystore.jks
   storePassword=your_store_password
   keyAlias=your_key_alias
   keyPassword=your_key_password
   ```
2. Add `android/keystore.properties` to `.gitignore` (alongside existing entries).
3. Modify `build.gradle`:
   - At the top, add:
     ```gradle
     def keystorePropertiesFile = file("keystore.properties")
     def keystoreProperties = new Properties()
     if (keystorePropertiesFile.exists()) {
       keystoreProperties.load(new FileInputStream(keystorePropertiesFile))
     }
     ```
   - Inside the `android {}` block, add:
     ```gradle
     signingConfigs {
       release {
         if (keystorePropertiesFile.exists()) {
           storeFile file(keystoreProperties['storeFile'])
           storePassword keystoreProperties['storePassword']
           keyAlias keystoreProperties['keyAlias']
           keyPassword keystoreProperties['keyPassword']
         }
       }
     }
     buildTypes {
       release {
         signingConfig signingConfigs.release
         minifyEnabled false
         proguardFiles getDefaultProguardFile('proguard-android.txt'), 'proguard-rules.pro'
       }
     }
     ```
   - If `keystorePropertiesFile` does not exist, the `release` signing config is incomplete, and Gradle falls back to debug signing.

**Patterns to follow:**
- Gradle signing config pattern: `signingConfigs {}` block with properties loaded from a file.
- Gitignore pattern: Add `keystore.properties` to `.gitignore` to prevent credential leakage.

**Test scenarios:**
- Happy path: With `keystore.properties` present, run `./gradlew assembleRelease` and verify a signed APK is produced at `android/app/build/outputs/apk/release/app-release.apk`.
- Edge case: Without `keystore.properties`, run `./gradlew assembleRelease` and verify it falls back to debug signing (build succeeds but APK is not signed with release key).
- Integration: Install the release APK on an Android device and verify it runs.

**Verification:** Release APK builds successfully with and without the properties file, and the signed APK installs and runs on a device.

---

## Verification Contract

| Command | Scope | Done signal |
|---------|-------|-------------|
| `cd frontend/apps/android && pnpm typecheck` | Web assets | `vue-tsc` reports no errors |
| `cd frontend/apps/android && pnpm build` | Web assets | Build completes without errors |
| `cd frontend/apps/android/android && ./gradlew testDebugUnitTest` | JVM unit tests | `DeepLinkTest` and `BackExitGuardTest` pass |
| `cd frontend/apps/android/android && ./gradlew assembleDebug` | Debug APK | APK produced at `app/build/outputs/apk/debug/app-debug.apk` |
| `cd frontend/apps/android/android && ./gradlew assembleRelease` | Release APK | APK produced at `app/build/outputs/apk/release/app-release.apk` (with or without signing, depending on `keystore.properties`) |
| `adb shell am start -a android.intent.action.VIEW -d "numina://open/reminders"` | Deep link | App launches and WebView navigates to `/reminders` |
| Manual: Press back button twice within 2 seconds | Back button | App exits after second press |

---

## Definition of Done

**Global criteria:**
- All requirements (R2, R4-R12) are satisfied; R1 and R3 are deferred to Phase 2b.
- All implementation units (U1-U4) pass their verification criteria.
- The app builds in both debug and release modes.
- Deep links work from killed, background, and foreground states.
- Back button exits after double-press when WebView has no history.
- Release APK can be signed with a keystore and installed on a device.

**Per-unit criteria:**
- U1: `types.ts` compiles and exports the `NativeEvent` interface.
- U2: Deep links navigate to the correct page in all three app states.
- U3: Back button walks through WebView history, then shows toast, then exits.
- U4: Release build succeeds with and without `keystore.properties`.

**Cleanup criterion:**
- No experimental or dead-end code remains in the diff. All files are production-ready.
