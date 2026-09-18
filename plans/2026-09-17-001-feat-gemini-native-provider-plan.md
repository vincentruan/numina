---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
title: Gemini Native Protocol Integration - Plan
type: feat
date: 2026-09-17
---

# Gemini Native Protocol Integration — Plan

## Goal Capsule

**Objective:** Add Google Gemini Native (`generateContent`) as the 4th AI provider protocol in Numina, alongside existing `anthropic`, `openai`, and `openai_compatible`. Changes span settings UI, agent LLM client, DeerFlow config mapping, backend validation, and provider documentation.

**Product authority:** Existing multi-provider architecture (`docs/brainstorms/2026-05-16-multi-provider-model-selection-requirements.md`).

**Execution profile:** Standard depth, 5 implementation units. Follows the established provider-branching pattern — no new abstractions.

---

## Product Contract

*Product Contract unchanged from ce-brainstorm.*

### Requirements

**UI and configuration**

- R1. The `/settings/ai` provider picker sheet must offer "Gemini Native" (`gemini`) as a selectable option with the Google Gemini sparkle logo.
- R2. Both `zh-CN` and `en-US` locale files must include `providerGemini` label.

**Agent LLM client**

- R3. `core/llm.py` must support `provider == "gemini"` branches in `complete()`, `complete_json()`, `stream_text()`, and `complete_vision()`, calling Google's `generateContent` API via `google-genai` SDK.

**DeerFlow multi-step config**

- R4. `packages/core/model_entry.py` must map `provider=gemini` to `langchain_google_genai:ChatGoogleGenerativeAI` so multi-step agent dispatch works with Gemini models.

**Backend validation**

- R5. `_VALID_PROVIDERS` must include `gemini`. `ModelInfo.provider` type comment must list it.

**Documentation**

- R6. Supported AI providers markdown must include a Gemini section listing supported models (`gemini-2.5-pro`, `gemini-2.0-flash`) and capabilities (vision ✓, thinking ✗).

### Key Decisions

- **Provider ID:** `gemini`
- **Auth:** Google AI Studio API Key (not Vertex AI service account). No custom `base_url` — Google's endpoint is fixed.
- **Models:** `gemini-2.5-pro` (primary), `gemini-2.0-flash` (secondary)
- **Capabilities:** Vision ✓, Thinking ✗ (matching DeerFlow's definition)
- **UI base_url field:** Hidden when `gemini` selected (Google's endpoint is not user-configurable for the native API)

### Flows

- F1. **User adds Gemini provider.** Navigate to `/settings/ai` → add provider → select "Gemini Native" → form shows provider name + API key + timeout (base_url hidden) → enter name + API key, select model → save → backend validates `gemini` is in `_VALID_PROVIDERS`.
- F2. **Agent LLM call via Gemini.** `LLMClient` receives `provider=gemini` → constructor instantiates `google.genai.Client(api_key=...)` → `complete()` calls `client.models.generate_content(model=..., contents=...)` → response parsed → returned as string.
- F3. **Multi-step agent dispatch via Gemini.** `family_adapter_cache` generates per-family `config.yaml` → `provider=gemini` → `build_model_entry()` produces `use: langchain_google_genai:ChatGoogleGenerativeAI` with `google_api_key` → DeerFlow `create_chat_model()` resolves the class → all downstream agent logic works unchanged.

### Acceptance Examples

- AE1. Selecting "Gemini Native" in provider picker shows the Gemini sparkle logo with Google blue gradient background.
- AE2. `LLMClient(provider="gemini", api_key="...", model_id="gemini-2.5-pro").complete("Hello")` returns a text response from Google's API.
- AE3. Adding a Gemini provider in settings and running the connection test returns `success: true` with latency.
- AE4. The supported-providers markdown doc lists Gemini with model info and capabilities.

---

## Planning Contract

### Key Technical Decisions

KTD1. **Dual SDK strategy.** Lightweight single-call path (`suggest`, `input_polish`, `title`, connection test) uses `google-genai` (Google's official SDK) for direct `generateContent` calls. Multi-step DeerFlow path uses `langchain-google-genai` (LangChain integration) via the existing `build_model_entry()` → `config.yaml` → DeerFlow `create_chat_model()` chain. This mirrors how the existing providers work: `anthropic.AsyncAnthropic` for lightweight, `langchain_anthropic:ChatAnthropic` for DeerFlow.

KTD2. **Gemini API key parameter naming.** In the DeerFlow model entry, the API key is emitted as `gemini_api_key` (matching `ChatGoogleGenerativeAI`'s constructor parameter name, confirmed by DeerFlow's `providers.py:api_key_field="gemini_api_key"` and `config.example.yaml`) instead of the generic `api_key` used by other providers. This is a Gemini-specific branch in `build_model_entry()`.

KTD3. **`stream_with_thinking` not supported for Gemini.** Gemini has no thinking/reasoning output. `stream_with_thinking()` raises `ValueError` for `provider == "gemini"`. `model_tester.test_thinking()` short-circuits with a "not supported" result for Gemini. The DB `thinking_supported` column defaults to `False` for Gemini configs.

KTD4. **`base_url` hidden in UI for Gemini.** The `AIProviderFormPage.vue` form hides the `base_url` field when `form.provider === 'gemini'`. Google's native API endpoint is fixed and not user-configurable.

### Scope Boundaries

**Deferred for later:**
- Vertex AI service account authentication (different auth model — OAuth2 credentials, not API key)
- Gemini extended thinking / thinking tokens (not yet available in the native API)
- Gemini function calling / tool use in the lightweight LLM client path (DeerFlow handles tool calling via LangChain)

**Not in scope:**
- Changes to DeerFlow harness code itself — `langchain_google_genai` provider is already defined in DeerFlow's `scripts/wizard/providers.py`
- Database migration — `String(20)` column accommodates `"gemini"` (6 chars) without alteration

---

## Implementation Units

### U1. Backend schema validation and model comments

**Goal:** Register `gemini` as a valid provider in the backend validation layer so the API accepts Gemini configs.

**Requirements:** R5

**Dependencies:** none

**Files:**
- `server/apps/backend/app/schemas/ai_config.py`
- `server/apps/backend/app/models/ai_provider_config.py`

**Approach:**
1. Add `"gemini"` to the `_VALID_PROVIDERS` tuple in `schemas/ai_config.py` line 9
2. Update the `ModelInfo.provider` type comment to include `"gemini"`
3. Update the `AIProviderConfig.provider` column comment in the SQLAlchemy model to include `'gemini'`

No DB migration needed — `String(20)` already fits `"gemini"`.

**Test scenarios:**
- Creating an `AIConfigCreate` with `provider="gemini"` passes validation (no `ValueError`)
- Creating an `AIConfigCreate` with `provider="invalid"` still raises `ValueError`
- `AIConfigUpdate` with `provider="gemini"` passes validation

**Verification:** `cd server && uv run pytest tests/backend/ -k "ai_config" -v` passes

---

### U2. Dependency addition

**Goal:** Add `google-genai` and `langchain-google-genai` to the server workspace so both the lightweight LLM client and DeerFlow integration can import them.

**Requirements:** R3, R4

**Dependencies:** none

**Files:**
- `server/pyproject.toml`

**Approach:**
1. Add `google-genai>=1.0.0` to the `[project.optional-dependencies]` `agent` group (lightweight LLM client uses this)
2. Add `langchain-google-genai>=2.0.0` to the same group (DeerFlow integration uses this — provides `ChatGoogleGenerativeAI`)
3. Run `cd server && uv lock` to update the lockfile

**Test expectation:** none — dependency declaration is verified by U3/U4 imports succeeding

**Verification:** `cd server && uv sync --extra agent` completes without errors; `uv run python -c "from google import genai; from langchain_google_genai import ChatGoogleGenerativeAI"` succeeds

---

### U3. Agent LLM client — Gemini dispatch

**Goal:** Add Gemini branches to `LLMClient` so lightweight single-call paths (`suggest`, `input_polish`, `title`, connection test) work with Gemini providers.

**Requirements:** R3

**Dependencies:** U2

**Files:**
- `server/apps/agent/core/llm.py`
- `server/apps/agent/services/model_tester.py` (Gemini thinking test short-circuit)

**Approach:**

In `LLMClient`:
1. Add `self._gemini_client = None` in `__init__`
2. Add `elif provider == "gemini"` branch: `from google import genai; self._gemini_client = genai.Client(api_key=api_key)` — note: `base_url` is ignored for Gemini (Google endpoint is fixed)
3. Add `_complete_gemini()` private method: calls `client.models.generate_content(model=..., contents=...)` with system instruction support. Extract text from `response.text`. Raise `LLMResponseError` on empty response (matching existing pattern)
4. Update `complete()`: add `elif self.provider == "gemini": return await self._complete_gemini(...)` — note: `google-genai` `Client` may need `asyncio.to_thread()` wrapping if the SDK is sync-only
5. Update `complete_json()`: add Gemini branch using system prompt JSON hint (same pattern as Anthropic — Gemini has no native `response_format`)
6. Update `stream_text()`: add Gemini branch using `client.models.generate_content_stream(...)`. Yield text chunks from the async iterator
7. Update `complete_vision()`: add Gemini branch using `Part.from_bytes(data=..., mime_type=...)` for image input alongside text
8. Update `stream_with_thinking()`: add explicit Gemini guard — raise `ValueError("Gemini 不支持思考模式")` since Gemini has no thinking output

In `model_tester.py`:
9. In `test_thinking()`: add `if provider == "gemini"` short-circuit returning `{"success": False, "message": "Gemini 不支持思考模式"}`

**Execution note:** The `google-genai` SDK provides native async via `client.aio` — use `await client.aio.models.generate_content(...)` for single calls and `async for chunk in await client.aio.models.generate_content_stream(...)` for streaming. No `asyncio.to_thread()` wrapping needed. System instructions are passed via `config=types.GenerateContentConfig(system_instruction=...)`. Vision uses `types.Part.from_bytes(data=..., mime_type=...)`. Response text is accessed via `response.text`.

**Patterns to follow:**
- Lazy SDK import inside the provider branch (matching `anthropic` and `openai` patterns at lines 156-169)
- `LLMResponseError` for empty responses (matching `_complete_anthropic` line 422 and `_complete_openai` line 472)
- System prompt as `system_instruction` parameter or prepended to contents (check SDK docs at implementation time)

**Test scenarios:**
- Happy path: `LLMClient(provider="gemini", ...).complete("hi")` returns non-empty string (requires valid API key)
- Happy path: `stream_text()` yields text chunks for Gemini provider
- Happy path: `complete_vision()` with base64 image data returns text description
- Edge case: empty response from Gemini raises `LLMResponseError` (not silent failure)
- Error path: `stream_with_thinking()` raises `ValueError` for Gemini provider
- Error path: invalid API key raises a clear authentication error (not a generic crash)
- Integration: `test_connection("gemini", ...)` returns `{"connected": True, "latency_ms": N}` with valid key
- Integration: `test_thinking("gemini", ...)` returns `{"success": False, "message": "Gemini 不支持思考模式"}`

**Verification:** `cd server && uv run pytest tests/agent/ -v` passes; manual connection test with valid Gemini API key returns expected response

---

### U4. DeerFlow model entry — Gemini config mapping

**Goal:** Map `provider=gemini` to the correct LangChain class in the DeerFlow config generation so multi-step agent dispatch (chat, asset-report, etc.) works with Gemini models.

**Requirements:** R4

**Dependencies:** U1, U2

**Files:**
- `server/packages/core/model_entry.py`

**Approach:**
1. Add `"gemini": "langchain_google_genai:ChatGoogleGenerativeAI"` to `_PROVIDER_CLASS_MAP`
2. In `build_model_entry()`, add a Gemini-specific branch for API key naming: when `provider == "gemini"`, emit `google_api_key` instead of `api_key` in the entry dict (matching `ChatGoogleGenerativeAI`'s constructor parameter)
3. Gemini has no thinking support — `thinking_supported` is always `False` for Gemini. No `_THINKING_CLASS_OVERRIDES` entry needed. No `_build_thinking_config()` branch needed (the existing `return {}` at line 254 handles it)
4. Gemini has no `base_url` — ignore `base_url` in the model entry when provider is Gemini

**Patterns to follow:**
- `_PROVIDER_CLASS_MAP` dict extension (lines 36-40)
- Entry dict construction matching existing pattern (lines 150-157)
- Conditional key naming: `api_key` for Anthropic/OpenAI, `google_api_key` for Gemini

**Test scenarios:**
- `build_model_entry({"ai_provider": "gemini", "ai_model_id": "gemini-2.5-pro", "api_key": "test-key"})` returns entry with `use: "langchain_google_genai:ChatGoogleGenerativeAI"` and `gemini_api_key: "test-key"` (not `api_key`)
- Entry includes `supports_thinking: False` and `supports_vision: True` (from capabilities)
- Entry does NOT include `base_url` even if `ai_base_url` is provided in input
- Entry does NOT include `thinking` config keys

**Verification:** `cd server && uv run pytest tests/packages/core/ -v` passes; `build_model_entry` with Gemini input produces correct DeerFlow config dict

---

### U5. Frontend — Gemini option in provider picker and form

**Goal:** Add Gemini as a selectable provider in the settings UI with the sparkle logo, Google blue branding, and hidden `base_url` field.

**Requirements:** R1, R2

**Dependencies:** U1

**Files:**
- `frontend/apps/main/src/components/ai/ProviderPickerSheet.vue`
- `frontend/apps/main/src/pages/AIProviderFormPage.vue`
- `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- `frontend/apps/main/src/i18n/locales/en-US.ts`

**Approach:**

In `ProviderPickerSheet.vue`:
1. Add 4th entry to `providers` computed: `{ value: 'gemini', label: t('aiConfig.providerGemini'), subtitle: 'generateContent endpoint' }`
2. Add Gemini sparkle SVG logo in the template (new `v-else-if="provider.value === 'gemini'"` branch before the `v-else` catch-all)
3. Add `.provider-item__icon--gemini` CSS class: Google blue gradient background (`#4285f4`), light/dark variants

In `AIProviderFormPage.vue`:
4. Add Gemini SVG logo in the provider cell logo area (new `v-else-if="form.provider === 'gemini'"` branch)
5. Add `if (provider === 'gemini') return t('aiConfig.providerGemini')` to `providerLabel()` function
6. Add `.logo--gemini` CSS class matching the picker sheet colors
7. Add `v-if="form.provider !== 'gemini'"` to the `base_url` field to hide it for Gemini (KTD4)

In i18n files:
8. `zh-CN.ts`: add `providerGemini: 'Google Gemini Native'` (or `'Gemini 原生协议'`)
9. `en-US.ts`: add `providerGemini: 'Google Gemini Native'`

**Patterns to follow:**
- Inline SVG logo pattern (matching Anthropic/OpenAI SVGs in both files)
- CSS class naming: `.provider-item__icon--gemini` in picker, `.logo--gemini` in form page
- Color scheme: Google blue `#4285f4`, dark variant `#669df6` (matching the Gemini sparkle logo brand colors)
- The Gemini sparkle logo SVG should be the 4-pointed star shape provided by the user (saved at `.cc-connect/attachments/img_1789613334773_0.png`)

**Test scenarios:**
- Provider picker displays 4 options including Gemini Native with sparkle logo
- Selecting Gemini shows Google blue icon background
- Form page shows Gemini logo + label in provider cell
- `base_url` field is hidden when Gemini is selected
- `base_url` field is visible when switching back to other providers
- zh-CN locale displays correct Chinese label for Gemini
- en-US locale displays correct English label for Gemini

**Verification:** `cd frontend && pnpm -r typecheck` passes; `pnpm -r test:run` passes; visual verification in dev server shows correct Gemini option in picker

---

### U6. Provider documentation

**Goal:** Create a supported AI providers reference document listing Gemini alongside existing providers.

**Requirements:** R6

**Dependencies:** U1

**Files:**
- `docs/supported-ai-providers.md` (new file)

**Approach:**
1. Create a new markdown document listing all 4 supported providers
2. For each provider, document: provider ID, API protocol, supported models, capabilities (thinking, vision), and authentication method
3. Gemini section should include:
   - Provider ID: `gemini`
   - Protocol: Google Gemini Native `generateContent`
   - Models: `gemini-2.5-pro`, `gemini-2.0-flash`
   - Capabilities: Vision ✓, Thinking ✗
   - Auth: Google AI Studio API Key

**Test expectation:** none — documentation file

**Verification:** Document renders correctly in markdown preview; all 4 providers are listed with accurate model and capability information

---

## Verification Contract

| Gate | Command | Scope |
|------|---------|-------|
| Backend lint | `cd server && uv run ruff check apps/backend/app/schemas/ai_config.py apps/backend/app/models/ai_provider_config.py` | U1 |
| Backend typecheck | `cd server && uv run mypy apps/backend/app/schemas/` | U1 |
| Agent lint | `cd server && uv run ruff check apps/agent/core/llm.py apps/agent/services/model_tester.py` | U3 |
| Core lint + test | `cd server && uv run ruff check packages/core/model_entry.py && uv run pytest tests/packages/core/ -v` | U4 |
| Frontend typecheck | `cd frontend && pnpm -r typecheck` | U5 |
| Frontend tests | `cd frontend && pnpm -r test:run` | U5 |
| Dependency install | `cd server && uv sync --extra agent` | U2 |
| Full agent tests | `cd server && uv run pytest tests/agent/ -v` | U3 |

---

## Definition of Done

**Global:**
- All 6 units pass their verification gates
- `uv run ruff check` clean on all touched server files
- `pnpm -r typecheck && pnpm -r test:run` clean on frontend
- No speculative code — only the 6 units' scope implemented
- Gemini provider can be added via settings UI and passes connection test
- Lightweight LLM calls (suggest, input_polish, title) work with Gemini provider
- DeerFlow multi-step dispatch (chat) works with Gemini provider via `langchain_google_genai`

**Per-unit:**
- U1: `_VALID_PROVIDERS` includes `"gemini"`, Pydantic validation accepts it
- U2: `google-genai` and `langchain-google-genai` importable in agent environment
- U3: `LLMClient(provider="gemini")` completes text, streams text, handles vision, rejects thinking
- U4: `build_model_entry()` with Gemini input produces valid DeerFlow config with `ChatGoogleGenerativeAI`
- U5: Gemini appears in picker + form with sparkle logo, blue branding, hidden base_url
- U6: Documentation lists all 4 providers with accurate Gemini info

**Cleanup:**
- No dead-end or experimental code from approaches that did not pan out
- No unused imports left by the implementation
- Temporary test artifacts removed
