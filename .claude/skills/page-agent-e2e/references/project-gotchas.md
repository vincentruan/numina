# Project Gotchas for PageAgent E2E

These are project-specific traps that AI agents commonly fall into when writing assertions or interpreting test results for the Numina project.

---

### Gotcha: Snowflake ID Serialization

[陷阱]
AI assumes asset/user IDs are numeric integers and writes assertions comparing numbers. In reality, all IDs are serialized as **strings** in API responses because JavaScript loses precision on integers > 2⁵³.

[正确做法]
- All ID fields in API responses are strings, not numbers
- TypeScript types use `string` for any `id` or `*_id` field
- Assertions checking API responses must compare string values
- `SnowflakeBase` in response schemas handles the int→str conversion automatically

[证据]
- `server/packages/core/` — SnowflakeBase class
- `server/apps/backend/CLAUDE.md` §Snowflake ID Serialization
- All response schemas inherit from SnowflakeBase

---

### Gotcha: No Trailing Slash on API Routes

[陷阱]
AI writes test assertions or API calls with trailing slashes (e.g., `/api/v1/assets/`). FastAPI issues a 307 redirect, which breaks behind nginx with HTTPS.

[正确做法]
- All API URLs must omit trailing slashes
- Route decorators use `""` not `"/"`
- Assertions checking URLs should never expect a trailing slash
- Network failure assertions will fire on 307 redirects

[证据]
- `server/apps/backend/app/main.py` — `redirect_slashes=False`
- All router files use `@router.get("")` pattern

---

### Gotcha: Auth Endpoints Return 200, Not 201

[陷阱]
AI expects `register`, `login`, and `join-family` to return HTTP 201 (Created). They actually return 200 with a `TokenResponse`.

[正确做法]
- Auth endpoints: expect 200
- Asset/Liability POST endpoints: expect 201
- Don't write `network_no_failures` assertions that would fail on "unexpected" 200s

[证据]
- `server/apps/backend/app/routers/auth.py` — no `status_code=201` on auth routes
- Asset routes have explicit `status_code=201` in decorators

---

### Gotcha: TokenResponse Has No User Field

[陷阱]
AI assumes login response includes user profile data (name, email, role). The `TokenResponse` only contains `access_token` and `token_type`. Frontend must call `/auth/me` separately.

[正确做法]
- After login, don't assert on user data from the login response
- If testing "user sees their name after login," the assertion must wait for the `/auth/me` call to complete
- PageAgent tasks should describe waiting for the dashboard/profile to load, not just the login response

[证据]
- `TokenResponse` schema in backend auth module
- Frontend auth store calls `/auth/me` after storing token

---

### Gotcha: Dashboard Allocation Returns Nested Object

[陷阱]
AI expects the dashboard allocation endpoint to return a flat array of items. It actually returns `{ items: [...], total: float }`.

[正确做法]
- Dashboard allocation: `{ items: [...], total: float }`
- Dashboard trend: `{ points: [...] }`
- Assertions on dashboard data must account for this nesting
- `text_visible` assertions on allocation amounts should look for the rendered values, not raw API structure

[证据]
- Frontend dashboard store/API types
- Backend dashboard router response schemas

---

### Gotcha: i18n Required for All UI Strings

[陷阱]
AI writes `text_visible` assertions with hardcoded Chinese strings that don't match the actual rendered text because the app uses i18n keys that may resolve differently.

[正确做法]
- All UI strings go through `t('key')` in the Vue templates
- Use `text_visible` assertions with the actual rendered text from `zh-CN.ts` locale file
- Check `frontend/apps/main/src/i18n/locales/zh-CN.ts` for the exact strings
- Never assume a Chinese string will appear exactly as written — verify against the locale file

[证据]
- `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- `frontend/apps/child/src/i18n/locales/zh-CN.ts`
- All `.vue` files use `{{ t('key') }}` pattern

---

### Gotcha: Child App Uses Emoji PIN Auth (Two-Phase)

[陷阱]
AI treats child login as a simple username/password form. The child app uses a two-phase emoji PIN system: first select the child profile, then enter a sequence of emoji characters as the PIN.

[正确做法]
- Child login is PIN-based, not password-based
- PIN is a sequence of emojis (e.g., 🐱,🐶,🌟,🌈)
- The login flow has two phases: profile selection → PIN entry
- PageAgent task must describe both phases
- `E2E_CHILD_PIN` env var contains comma-separated emojis

[证据]
- `frontend/apps/child/` — PIN input component
- Test helpers: `loginAsChild` function in test utilities
- `.env.example` — `E2E_CHILD_PIN=🐱,🐶,🌟,🌈`
