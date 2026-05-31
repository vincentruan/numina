---
status: active
date: 2026-05-31
type: feat
title: "feat: Enhanced skill creation — command install, AI generation, manual edit"
origin: docs/brainstorms/2026-05-31-skill-management-enhanced-creation-requirements.md
deepened: null
---

# feat: Enhanced Skill Creation — Command Install + AI Generation + Manual Edit

## Summary

Add two new skill creation channels alongside the existing manual flow: (1) command-based install from external sources (skills.sh, GitHub) with safe regex parsing + AI fallback for complex inputs, (2) AI-assisted generation via a skill-creator builtin skill. Both channels write to the same tenant-isolated directory and DB table as the existing manual flow, with a new `creation_type` field tracking provenance.

(see origin: `docs/brainstorms/2026-05-31-skill-management-enhanced-creation-requirements.md`)

---

## Problem Frame

Users can only create skills by manually filling a form. This produces inconsistent SKILL.md quality and prevents leveraging the external skill ecosystem (skills.sh, GitHub). The feature adds structured creation channels that produce higher-quality output while maintaining strict tenant isolation and security.

---

## Key Technical Decisions

- **Command parser lives in backend service, not agent** — The regex parsing and HTTP download are pure I/O operations that don't need LLM involvement. Only the AI fallback path dispatches to the agent service via internal HTTP.
- **skill-creator and skill-installer execute via `DeerFlowAdapter.dispatch()`** — Follows the mandatory architecture constraint. Both are registered as builtin skills with their own SKILL.md definitions.
- **Sentinel exclusion via filter in `_resolve_skills()`** — A 3-line addition: `INTERNAL_ONLY_SKILLS = {"skill-creator", "skill-installer"}` constant + list comprehension filter when `"*" in agent_skills`. Minimal change, maximum safety.
- **DB migration adds nullable columns with backfill** — `creation_type` defaults to `'manual'` for existing rows; `source_url` defaults to `NULL`. No data loss, backward compatible.
- **Frontend: tabbed interface inside existing popup** — Reuses the `showForm` popup in `SkillsManagePage.vue`, adding Vant `<van-tabs>` for the three creation modes. Minimal structural change to the page.
- **AI generation is two-step (preview → save)** — The AI-create endpoint returns generated SKILL.md text; the frontend shows it in a preview pane; user confirms → calls existing `createCustomSkill` endpoint to persist.
- **Frontmatter parsing uses a shared utility** — A new `parse_skill_frontmatter(content: str) -> dict` function in a service module, reused by both command-install and AI-create flows.

---

## Scope Boundaries

- No skills.sh browsing/search UI — paste-only input
- No version management or upgrade detection
- No changes to tab 3 (manual edit) existing logic
- No changes to numina/ai-assistant agent soul or behavior
- No skill export/sharing functionality
- Frontend tab UI details (animation, default tab) decided at implementation time

### Deferred to Follow-Up Work

- Private repository support (requires credential management)
- Skill update/upgrade flow (detect newer version at source)
- Batch install (multiple skills from one command)

---

## System-Wide Impact

| Surface | Impact |
|---------|--------|
| `ai_skills` DB table | +2 columns (`creation_type`, `source_url`) |
| `agent_dispatch.py` | Sentinel exclusion filter in `_resolve_skills()` |
| `skills/builtin/` directory | +2 new skill definitions (skill-creator, skill-installer) |
| Backend router `ai_skills.py` | +2 new endpoints (install, ai-create) |
| Agent service | New internal endpoint to proxy skill dispatch for backend |
| Frontend `SkillsManagePage.vue` | Popup form → tabbed interface |
| Frontend `api/ai.ts` | +2 new API functions |
| Frontend i18n (`zh-CN.ts`, `en-US.ts`) | +10 new translation keys for tab labels and skill creation UI |

---

## High-Level Technical Design

*This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (SkillsManagePage)                │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │ Tab 1:   │  │ Tab 2:       │  │ Tab 3:             │    │
│  │ Install  │  │ AI Generate  │  │ Manual (existing)  │    │
│  └────┬─────┘  └──────┬───────┘  └─────────┬──────────┘    │
└───────┼────────────────┼────────────────────┼───────────────┘
        │                │                    │
        ▼                ▼                    ▼
  POST /ai/skills/   POST /ai/skills/    POST /ai/skills/
     install            ai-create            custom (existing)
        │                │                    │
        ▼                ▼                    │
  ┌───────────┐   ┌────────────┐             │
  │ Command   │   │ Call agent  │             │
  │ Parser    │   │ dispatch    │             │
  │ (regex)   │   │ skill-      │             │
  └─────┬─────┘   │ creator    │             │
        │         └─────┬──────┘             │
   ┌────┴────┐          │                    │
   │ Match?  │          ▼                    │
   │ A or B  │   Return SKILL.md text        │
   └─┬────┬──┘   (user confirms → save)     │
     │    │                                   │
  Yes│    │No (fallback)                      │
     │    ▼                                   │
     │  Call agent dispatch                   │
     │  skill-installer                       │
     │    │                                   │
     ▼    ▼                                   ▼
  ┌─────────────────────────────────────────────┐
  │         Shared Save Logic                    │
  │  1. Validate skill_id (SKILL_ID_PATTERN)    │
  │  2. Parse frontmatter → name/description    │
  │  3. workspace.create_custom_skill()         │
  │  4. Write SkillRegistry row                 │
  └─────────────────────────────────────────────┘
```

---

## Implementation Units

### U1. DB migration — add `creation_type` and `source_url` columns

**Goal:** Extend `ai_skills` table with provenance tracking fields.

**Requirements:** R6

**Dependencies:** None

**Files:**
- Modify: `server/apps/backend/app/models/skill_registry.py`
- Create: `server/apps/backend/alembic/versions/<auto>_add_skill_creation_type.py`
- Test: `server/tests/backend/unit/test_skill_registry_model.py`

**Approach:**
- Add `creation_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="manual")` — values: `'manual'`, `'cmd'`, `'ai_created'`
- Add `source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)`
- Migration: `ALTER TABLE ai_skills ADD COLUMN creation_type VARCHAR(16) NOT NULL DEFAULT 'manual'` + `ADD COLUMN source_url VARCHAR(512) NULL`
- Existing rows get `creation_type='manual'` via server_default

**Patterns to follow:** Existing migration pattern in `server/apps/backend/alembic/versions/` — use `op.add_column` with `server_default`.

**Test scenarios:**
- New SkillRegistry record defaults `creation_type` to `'manual'` when not specified
- `creation_type` accepts all three valid values
- `source_url` is nullable and stores URLs up to 512 chars

**Verification:** `uv run alembic upgrade head` succeeds; `uv run pytest tests/backend/unit/test_skill_registry_model.py` passes.

---

### U2. Shared frontmatter parser utility

**Goal:** Create a reusable function to parse SKILL.md YAML frontmatter, used by both install and AI-create flows.

**Requirements:** R13

**Dependencies:** None

**Files:**
- Create: `server/apps/backend/app/services/skill_parser.py`
- Test: `server/tests/backend/unit/test_skill_parser.py`

**Approach:**
- Function `parse_skill_frontmatter(content: str) -> dict` — extracts YAML between `---` delimiters
- Returns `{"name": str | None, "description": str | None, "raw_frontmatter": dict}` 
- Uses `yaml.safe_load()` — never `yaml.load()`
- On parse failure (malformed YAML, missing delimiters): returns `{"name": None, "description": None, "raw_frontmatter": {}}`
- Function `validate_skill_content(content: str) -> bool` — checks that content has valid frontmatter with at least a `name` field

**Patterns to follow:** The agent's `capability_registry.py` already has `_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)` — reuse the same regex pattern.

**Test scenarios:**
- Happy path: valid SKILL.md with name and description in frontmatter
- Frontmatter with extra fields (trigger_phrases, allowed-tools) — only name/description extracted
- Missing `---` delimiters — returns None fallbacks
- Malformed YAML (invalid syntax) — returns None fallbacks without raising
- Empty content string — returns None fallbacks
- Content with only frontmatter, no body — still parses successfully
- Unicode content in name/description — handled correctly

**Verification:** `uv run pytest tests/backend/unit/test_skill_parser.py -v` passes.

---

### U3. Command parser — safe regex extraction + validation

**Goal:** Build the security-critical command parser that extracts skill identifiers from user input without executing anything.

**Requirements:** R1, R2

**Dependencies:** None

**Files:**
- Create: `server/apps/backend/app/services/skill_command_parser.py`
- Test: `server/tests/backend/unit/test_skill_command_parser.py`

**Approach:**
- Class `SkillCommandParser` with method `parse(raw_input: str) -> ParseResult`
- `ParseResult` is a dataclass: `{ match_type: 'cli' | 'url' | 'unmatched', provider: str | None, skill_name: str | None, repo_url: str | None, raw_input: str }`
- Regex patterns for variant A: `r"(?:npx\s+skills\s+add|skillhub\s+install)\s+([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)"`
- Regex patterns for variant B: `r"https?://github\.com/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)"` and `r"https?://skills\.sh/v1/skills/([a-zA-Z0-9_-]+)"`
- Security validations (applied to extracted identifiers):
  - **URL-decode and Unicode-normalize (NFKC)** extracted identifiers before any validation
  - Reject if contains `..`, `/`, `\`, null bytes, shell metacharacters (`;`, `|`, `&`, `$`, `` ` ``)
  - Reject if length > 128 characters
  - Reject if doesn't match `SKILL_ID_PATTERN` after normalization (lowercase, replace invalid chars)
  - Truncate raw_input to 2048 chars before processing (DoS prevention)
- When no regex matches → `match_type='unmatched'` (signals AI fallback needed)

**Patterns to follow:** `SKILL_ID_PATTERN` from `ai_skills.py` for final skill_id validation.

**Test scenarios:**
- Covers AE1. Variant A: `npx skills add anthropics/deploy-staging` → extracts `anthropics`, `deploy-staging`
- Variant A: `skillhub install user/my-skill` → extracts `user`, `my-skill`
- Variant B: `https://github.com/anthropics/skills` → extracts repo URL
- Variant B: `https://skills.sh/v1/skills/deploy-staging` → extracts skill-id
- Covers AE2. Path traversal: `npx skills add ../../etc/passwd` → rejected
- Shell injection: `npx skills add foo/bar; rm -rf /` → rejected (semicolon in input)
- Null bytes: `npx skills add foo/bar\x00evil` → rejected
- Oversized input (>2048 chars) → truncated before processing
- Variant C: `curl -fsSL https://skills.sh/install.sh | sh -s -- deploy` → `match_type='unmatched'`
- Empty string → `match_type='unmatched'`
- Whitespace-only → `match_type='unmatched'`
- Mixed case in provider/name → normalized to lowercase

**Verification:** `uv run pytest tests/backend/unit/test_skill_command_parser.py -v` — all security tests pass.

---

### U4. Skill downloader — safe HTTP fetch of SKILL.md

**Goal:** HTTP client that downloads SKILL.md from GitHub or skills.sh given a parsed command result.

**Requirements:** R1, R2, R5

**Dependencies:** U2

**Files:**
- Create: `server/apps/backend/app/services/skill_downloader.py`
- Test: `server/tests/backend/unit/test_skill_downloader.py`

**Approach:**
- Class `SkillDownloader` with async method `download(parse_result: ParseResult) -> DownloadResult`
- `DownloadResult`: `{ content: str, source_url: str, skill_id: str }`
- URL construction:
  - GitHub: `https://raw.githubusercontent.com/{provider}/{skill_name}/main/skills/{skill_name}/SKILL.md` (try `main`, fallback `master`)
  - skills.sh: `https://skills.sh/v1/skills/{skill_id}/SKILL.md` (assumed public API)
- Uses `httpx.AsyncClient` with:
  - Timeout: 15s connect, 30s read
  - Max response size: 1MB (reject larger)
  - **Redirect policy:** Disable automatic redirect following. Handle main→master branch fallback with explicit sequential requests. This eliminates SSRF via redirect chains to internal hosts (169.254.169.254, 10.x.x.x, etc.)
  - **Host allowlist:** Only fetch from `raw.githubusercontent.com` and `skills.sh` — reject any URL resolving to other hosts
  - No cookies, no auth headers
- Validates downloaded content with `validate_skill_content()` from U2
- Extracts `skill_id` from the skill name (lowercase, replace spaces with hyphens)

**Patterns to follow:** The project uses `httpx` for async HTTP (seen in `capability_registry.py`).

**Test scenarios:**
- Happy path: mock GitHub raw URL returns valid SKILL.md → content extracted
- Happy path: mock skills.sh URL returns valid SKILL.md → content extracted
- GitHub 404 on `main` branch, success on `master` fallback
- HTTP timeout → raises descriptive error
- Response > 1MB → rejected with size error
- Response is not valid SKILL.md (no frontmatter) → raises validation error
- Non-200 status code → raises descriptive error
- Redirect loop (>3 hops) → rejected

**Verification:** `uv run pytest tests/backend/unit/test_skill_downloader.py -v` passes with mocked HTTP.

---

### U5. Install endpoint — `POST /api/v1/ai/skills/install`

**Goal:** Backend endpoint that orchestrates the full install flow: parse → download (or AI fallback) → save.

**Requirements:** R1, R2, R3, R5, R6, R11, R13

**Dependencies:** U1, U2, U3, U4, U7

**Files:**
- Modify: `server/apps/backend/app/routers/ai_skills.py`
- Test: `server/tests/backend/unit/test_skill_install_endpoint.py`

**Approach:**
- New endpoint `POST /ai/skills/install` with `Depends(require_owner)`
- Request body: `{ "command": str }` — the raw user input
- Flow:
  1. Parse with `SkillCommandParser.parse(command)`
  2. If `match_type` in `('cli', 'url')`: download with `SkillDownloader.download(result)`
  3. If `match_type == 'unmatched'`: call agent service internal endpoint to dispatch skill-installer (see U7)
  4. Parse frontmatter from downloaded content → extract name/description
  5. Derive `skill_id` — for regex-matched paths use `parse_result.skill_name`; for AI fallback, extract from frontmatter `name` field then normalize with `SKILL_ID_PATTERN`. **Never use raw LLM output as skill_id without normalization.**
  6. Validate `skill_id` with `SKILL_ID_PATTERN`, check not in `BUILTIN_CAPABILITIES` or `RESERVED_NAMES` or `INTERNAL_ONLY_SKILLS`
  7. **Filesystem confinement guard:** After constructing `skill_dir = skills_custom_dir(family_id) / skill_id`, assert `skill_dir.resolve().is_relative_to(skills_custom_dir(family_id).resolve())` before any write
  8. Write `SkillRegistry` row first (within DB transaction) with `skill_type='custom'`, `creation_type='cmd'`, `source_url=<original_url>`. On unique constraint violation → return 409 "该技能已存在" (no filesystem write occurs)
  9. Only after DB commit succeeds: write to filesystem via `workspace.create_custom_skill(family_id, skill_id, content)`. If filesystem write fails → delete the DB row (compensating transaction)
  10. Apply the **same security validation pipeline** (steps 5-7) to AI fallback content identically to downloaded content — AI output is untrusted
- Response: `SkillDefinitionResponse` (same as existing create endpoint)

**Patterns to follow:** Existing `create_custom_skill_endpoint` in `ai_skills.py` for the save logic pattern.

**Test scenarios:**
- Covers AE1. Valid CLI command → full flow succeeds, DB record has `creation_type='cmd'`
- Covers AE2. Path traversal input → 400 error before any download
- Covers AE5. Duplicate skill_id for same family → 409 "该技能已存在"
- Valid GitHub URL → downloads and installs
- Unmatched input → triggers AI fallback path (mocked agent call)
- Download failure (network error) → 502 with descriptive message
- Downloaded content has no valid frontmatter → uses skill_id as fallback name
- Input exceeds 2048 chars → truncated, still processed

**Verification:** `uv run pytest tests/backend/unit/test_skill_install_endpoint.py -v` passes.

---

### U6. Install builtin skills — skill-creator and skill-installer SKILL.md

**Goal:** Create the two internal-only builtin skill definitions that DeerFlow will load.

**Requirements:** R4, R8

**Dependencies:** None

**Files:**
- Create: `server/apps/agent/skills/builtin/skill-creator/SKILL.md`
- Create: `server/apps/agent/skills/builtin/skill-installer/SKILL.md`

**Approach:**

**skill-creator/SKILL.md:**
- Frontmatter: `name: skill-creator`, `description: Generates professional SKILL.md from natural language descriptions`, `allowed-tools: []`, `thinking: true`
- Body: System prompt instructing the LLM to receive a user description and output a complete SKILL.md with standard structure (frontmatter with name/description/trigger_phrases, `## When to Use`, `## Instructions`, boundary constraints)
- Reference: adapt from `https://raw.githubusercontent.com/anthropics/skills/refs/heads/main/skills/skill-creator/SKILL.md`

**skill-installer/SKILL.md:**
- Frontmatter: `name: skill-installer`, `description: Resolves and downloads skills from external sources`, `allowed-tools: [web_search]`, `thinking: true`
- Body: System prompt instructing the LLM to: (1) analyze the user's install command/text, (2) use web_search to locate the skill source, (3) extract the SKILL.md content, (4) return the full SKILL.md text as output

**Patterns to follow:** Existing builtin skills in `server/apps/agent/skills/builtin/report/SKILL.md` for frontmatter structure.

**Test scenarios:**
- Test expectation: none — these are static prompt files. Verification is that DeerFlow loads them without error (covered by integration in U5/U8).

**Verification:** Files exist at expected paths; `CapabilityRegistry()._read_frontmatter(Path("server/apps/agent/skills/builtin/skill-creator/SKILL.md"))` returns a non-empty dict.

---

### U7. Agent-side internal dispatch endpoint for backend → agent skill calls

**Goal:** Expose an internal HTTP endpoint on the agent service that the backend can call to dispatch skill-creator or skill-installer synchronously.

**Requirements:** R3, R7

**Dependencies:** U6

**Files:**
- Modify: `server/apps/agent/app/routers/gateway.py` (add endpoint to existing internal router)
- Test: `server/tests/agent/unit/test_internal_skill_dispatch.py`

**Approach:**
- Add new endpoint `POST /api/v1/internal/skill-dispatch` to the existing `gateway.py` router (reuse existing `X-Agent-Token` auth pattern from `server/apps/agent/app/routers/cache.py` lines 21/37)
- Request body: `{ "skill_name": str, "family_id": int, "input_text": str }`
- Flow:
  1. Validate `X-Agent-Token` matches `settings.AGENT_INTERNAL_TOKEN` (existing pattern in `cache.py`)
  2. Validate `skill_name` is in `["skill-creator", "skill-installer"]` (whitelist — only internal skills)
  3. Fetch family AI config via `BackendClient(family_id).get_family_ai_config()`
  4. Construct `DeerFlowAdapter(family_id=family_id, ai_config=ai_config)`
  5. Build a valid `RedactedContext` instance (must populate all required fields from `server/apps/agent/schemas/context.py` — use `family_id` and `input_text` as the message content)
  6. Call `adapter.dispatch(skill_name, context, thread_id=str(uuid4()))`
  7. Return `{ "content": str }` — the raw text output from DeerFlow
- Timeout: 60s (LLM generation can be slow)
- Error handling: if dispatch fails → return 502; if timeout → return 504 with structured error body distinguishing timeout from other failures
- **Trust boundary note:** `family_id` in the request body is trusted because this endpoint is only callable with the internal token, and the backend (U5/U8) always passes `current_user.family_id` (JWT-derived). Add a code comment documenting this trust assumption.

**Patterns to follow:** Existing `X-Agent-Token` auth in `server/apps/agent/app/routers/cache.py`; existing `DeerFlowAdapter` construction in `server/apps/agent/services/orchestrator.py`.

**Test scenarios:**
- Valid request with skill-creator → returns generated SKILL.md text
- Valid request with skill-installer → returns downloaded SKILL.md text
- Missing X-Agent-Token → 403
- Invalid skill_name (not in whitelist) → 400
- DeerFlow dispatch timeout → 502 with timeout message
- DeerFlow dispatch error → 502 with error detail

**Verification:** `uv run pytest tests/agent/unit/test_internal_skill_dispatch.py -v` passes.

---

### U8. AI-create endpoint — `POST /api/v1/ai/skills/ai-create`

**Goal:** Backend endpoint that calls skill-creator via the agent service and returns generated SKILL.md for preview.

**Requirements:** R7, R8, R9

**Dependencies:** U2, U6, U7

**Files:**
- Modify: `server/apps/backend/app/routers/ai_skills.py`
- Test: `server/tests/backend/unit/test_skill_ai_create_endpoint.py`

**Approach:**
- New endpoint `POST /ai/skills/ai-create` with `Depends(require_owner)`
- Request body: `{ "description": str }` — user's natural language description
- Flow:
  1. Validate description is non-empty, max 4096 chars
  2. Call agent internal endpoint: `POST {AGENT_BASE_URL}/api/v1/internal/skill-dispatch` with `skill_name="skill-creator"`, `input_text=description`, `family_id=current_user.family_id`. Use `httpx.AsyncClient` with headers `{'X-Agent-Token': settings.AGENT_INTERNAL_TOKEN}`.
  3. Validate returned content length (max 64KB — reject oversized LLM output)
  4. Parse the returned content with `parse_skill_frontmatter()` to validate it's well-formed
  5. Return `{ "content": str, "parsed_name": str | None, "parsed_description": str | None }` for frontend preview
- This endpoint does NOT save anything — it's preview-only
- **Save flow for AI-created skills:** The frontend cannot use the existing `POST /ai/skills/custom` endpoint directly because that endpoint rebuilds SKILL.md from form fields (discarding the AI-generated structure). Instead, add a new endpoint `POST /ai/skills/custom/raw` that accepts `{ "skill_id": str, "content": str, "icon": str, "color": str }` and writes the raw SKILL.md content directly (bypassing template assembly). This preserves the skill-creator's structured output (trigger_phrases, `## When to Use`, `## Instructions`). Set `creation_type='ai_created'`.
- Timeout: 60s for the agent call
- Error handling: agent timeout → 504 with structured body; agent error → 502; malformed LLM output (no frontmatter) → return content anyway with `parsed_name=None` (let user edit before saving)

**Patterns to follow:** Backend → agent HTTP call is a new pattern for this project. Use `httpx.AsyncClient` with `{'X-Agent-Token': settings.AGENT_INTERNAL_TOKEN}` header and POST to `{settings.AGENT_BASE_URL}/api/v1/internal/skill-dispatch`.

**Test scenarios:**
- Covers AE4. Valid description → returns well-formed SKILL.md with frontmatter
- Empty description → 422 validation error
- Description > 4096 chars → 422 validation error
- Agent service timeout → 504 with descriptive message
- Agent returns malformed content (no frontmatter) → still returns content with null parsed fields
- Agent returns valid content → parsed_name and parsed_description populated from frontmatter

**Verification:** `uv run pytest tests/backend/unit/test_skill_ai_create_endpoint.py -v` passes.

---

### U9. Sentinel exclusion — `INTERNAL_ONLY_SKILLS` filter

**Goal:** Prevent skill-creator and skill-installer from being exposed to the numina agent via sentinel `["*"]` resolution.

**Requirements:** R12

**Dependencies:** U6

**Files:**
- Modify: `server/apps/agent/services/agent_dispatch.py`
- Test: `server/tests/agent/unit/test_agent_dispatch.py` (extend existing)

**Approach:**
- Add constant: `INTERNAL_ONLY_SKILLS = {"skill-creator", "skill-installer"}`
- In `_resolve_skills()`, apply the filter in **both** branches:
  - When `"*" in agent_skills`: `return [s for s in family_enabled_skills if s.get("skill_id") not in INTERNAL_ONLY_SKILLS]`
  - When non-empty specific list: also filter out INTERNAL_ONLY_SKILLS from the intersection result (prevents a custom agent from explicitly listing `skills=["skill-creator"]` to gain access)
- This ensures internal-only skills cannot be dispatched by any agent, regardless of how their skill list is configured

**Patterns to follow:** The existing `_resolve_skills()` function structure — add the filter as a list comprehension.

**Test scenarios:**
- Covers AE6. Sentinel `["*"]` with family_enabled_skills containing skill-creator → result excludes it
- Sentinel `["*"]` with family_enabled_skills containing skill-installer → result excludes it
- Sentinel `["*"]` with normal skills (report, alerts) → result includes them unchanged
- Non-sentinel agent (specific skill list) → INTERNAL_ONLY_SKILLS filter does NOT apply
- `["chat"]` path → unchanged behavior (returns [])

**Verification:** `uv run pytest tests/agent/unit/test_agent_dispatch.py -v` passes.

---

### U10. Frontend — tabbed creation interface

**Goal:** Convert the single-form popup in SkillsManagePage into a three-tab interface.

**Requirements:** R1, R7, R9, R10

**Dependencies:** U5, U8

**Files:**
- Modify: `frontend/apps/main/src/pages/SkillsManagePage.vue`
- Modify: `frontend/apps/main/src/api/ai.ts`
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts`

**Approach:**

**API additions (`api/ai.ts`):**
- `installSkill(command: string)` → `POST /ai/skills/install`
- `aiCreateSkill(description: string)` → `POST /ai/skills/ai-create`

**Tab structure (inside existing `<van-popup>`):**
- `<van-tabs v-model:active="activeTab">` with three tabs
- Tab 1 "命令安装": single textarea input + "安装" button. On submit → `installSkill()`. Show loading state during install. On success → close popup, refresh list.
- Tab 2 "AI 生成": markdown textarea for description + "🤖 技能智能分析和生成" button. On submit → `aiCreateSkill()`. Show preview of generated SKILL.md in a read-only code block. User clicks "确认保存" → calls existing `createCustomSkill()` with generated content. Two-step flow.
- Tab 3 "手动编辑": existing form (skill_id, name, icon, color, prompt_content) — no changes to logic.

**i18n additions:**
- `skills.tabs.install`: '命令安装' / 'Install'
- `skills.tabs.aiCreate`: 'AI 生成' / 'AI Generate'
- `skills.tabs.manual`: '手动编辑' / 'Manual'
- `skills.install.placeholder`: '粘贴安装命令或 URL...' / 'Paste install command or URL...'
- `skills.install.button`: '安装' / 'Install'
- `skills.install.success`: '✅ 技能安装成功' / '✅ Skill installed'
- `skills.install.exists`: '⚠️ 该技能已存在' / '⚠️ Skill already exists'
- `skills.aiCreate.placeholder`: '描述你想要的技能功能...' / 'Describe the skill you want...'
- `skills.aiCreate.button`: '🤖 技能智能分析和生成' / '🤖 AI Generate Skill'
- `skills.aiCreate.preview`: '生成预览' / 'Generated Preview'
- `skills.aiCreate.confirm`: '确认保存' / 'Confirm & Save'

**Patterns to follow:** Existing `<van-tabs>` usage in the project; existing popup form pattern in `SkillsManagePage.vue`.

**Test scenarios:**
- Tab 1: paste valid command → loading state → success toast → popup closes → list refreshes
- Tab 1: paste invalid command → error toast with message from backend
- Tab 1: duplicate skill → shows "该技能已存在" warning
- Tab 2: enter description → click generate → loading state → preview appears
- Tab 2: preview shown → click confirm → saves via raw content endpoint → success toast
- Tab 2: empty description → generate button disabled
- Tab 3: existing manual flow unchanged — all current behavior preserved

**Verification:** `pnpm typecheck` passes; manual testing of all three tabs in browser.

---

## Requirements Trace

| Requirement | Implementation Unit(s) |
|-------------|----------------------|
| R1 (install endpoint + variants) | U3, U4, U5 |
| R2 (security — no shell exec) | U3, U5 |
| R3 (AI fallback) | U5, U7 |
| R4 (skill-installer builtin) | U6 |
| R5 (tenant isolation) | U5, U8 (via existing workspace helpers) |
| R6 (DB record with creation_type) | U1, U5, U8 (U8 adds raw save endpoint with `creation_type='ai_created'`; existing endpoint uses server_default `'manual'` for R10) |
| R7 (AI-create endpoint) | U7, U8 |
| R8 (skill-creator builtin) | U6 |
| R9 (two-step preview+save) | U8, U10 |
| R10 (manual unchanged) | U10 (tab 3 preserves existing) |
| R11 (concurrency — unique constraint) | U5 |
| R12 (sentinel exclusion) | U9 |
| R13 (frontmatter parsing) | U2 |

---

## Verification Strategy

1. **Unit tests** — Each unit has dedicated test file covering happy paths, edge cases, and security scenarios
2. **Security tests** — U3 specifically covers command injection, path traversal, and input sanitization
3. **Integration** — U5 and U8 test the full flow with mocked agent service calls
4. **Type checking** — `pnpm typecheck` for frontend, `uv run mypy` for backend
5. **Lint** — `uv run ruff check` for backend, `pnpm lint` for frontend

---

## Implementation-Time Unknowns

- Exact skills.sh download URL format — may need adjustment after testing against the real API
- skill-creator prompt quality — may need iteration on the SKILL.md system prompt to produce consistently good output
- DeerFlow `web_search` tool availability for ai-assistant — needs verification in deerflow_config; if not configured, U6 skill-installer won't have web access
- `RedactedContext` required fields — implementer must read `server/apps/agent/schemas/context.py` to determine which fields are non-nullable when constructing the minimal context for U7

---

## Review Findings (2026-05-31)

Applied fixes from multi-persona review (coherence, feasibility, security, adversarial, scope-guardian):

### Applied (safe_auto + gated_auto)

1. **U5 missing U7 dependency** — Added U7 to U5's dependency list (AI fallback path requires U7)
2. **mcp_internal.py reference wrong** — Corrected to `cache.py` (the actual file with X-Agent-Token auth)
3. **SkillLoader reference wrong** — Corrected to `CapabilityRegistry()._read_frontmatter()`
4. **U8 backend_client.py reference wrong** — Removed; specified the new pattern directly
5. **SSRF via redirect chain** — Disabled automatic redirects; added host allowlist (raw.githubusercontent.com, skills.sh)
6. **URL-encoded/Unicode path traversal** — Added URL-decode + NFKC normalization step before validation
7. **Orphaned filesystem writes** — Reversed write order: DB first, filesystem second, with compensating delete on failure
8. **AI fallback output untrusted** — Added explicit note that AI output goes through same security pipeline as downloaded content
9. **Path traversal confinement** — Added `resolve().is_relative_to()` assertion before filesystem write
10. **INTERNAL_ONLY_SKILLS bypass via explicit list** — Filter now applies to both wildcard and explicit skill list branches
11. **U7 new router file unnecessary** — Changed to add endpoint to existing `gateway.py`
12. **DeerFlowAdapter construction omitted** — Added steps for fetching ai_config and constructing adapter
13. **U8 save path discards AI structure** — Added new `POST /ai/skills/custom/raw` endpoint for raw content save
14. **U3 false dependency on U2** — Removed (U3 doesn't use frontmatter parsing)
15. **U10 "tab switching preserves draft" scope creep** — Removed from test scenarios
16. **System-Wide Impact missing i18n** — Added row for i18n file changes
17. **U7 family_id trust boundary** — Added documentation note about trust assumption

### Deferred / Open Questions

- **[P2][Security]** YAML alias bomb protection: consider adding 4KB frontmatter size cap in `parse_skill_frontmatter()` before `yaml.safe_load()`
- **[P2][Security]** Rate limiting on AI endpoints: consider applying existing rate_limit middleware to `/ai/skills/install` and `/ai/skills/ai-create` (max 10 per hour per family)
- **[P2][Feasibility]** `SkillDefinitionResponse` inherits from `BaseModel` not `SnowflakeBase` — pre-existing gap that new endpoints will propagate. Consider fixing as part of this work or separately.
- **[P1][Scope]** U2 (skill_parser.py) creates a 4th copy of frontmatter parsing logic in the codebase. Consider extracting to `server/packages/core` for shared use, or inlining the trivial 3-line logic directly in U5/U8. Decision deferred to implementation.
- **[P1][Adversarial]** DeerFlow dispatch timeout (60s) is unverified for skill-creator workload. If consistently exceeds 60s, consider async job pattern (return job_id, poll for completion). Monitor during implementation.

