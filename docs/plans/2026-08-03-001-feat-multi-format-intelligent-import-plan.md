---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
execution: code
date: 2026-08-03
topic: multi-format-intelligent-import
---

# Multi-Format Intelligent Import - Plan

## Goal Capsule

**Objective:** Enable families to import financial data from any document format (PDF bank statements, e-commerce screenshots, Excel spreadsheets) through a single unified import flow at `/finance/import`, with AI-powered recognition that classifies items into assets or liabilities, progress display during parsing, an interactive preview page for review and correction before commit, and a persistent draft staging table that retains import history for future analysis and rollback.

**Product authority:** This plan owns the import feature end-to-end — file ingestion, AI extraction, preview/edit UX, and multi-model commit. Route reorganization (`/settings/import-report` → `/finance/import`) is bundled. Surrounding areas (reconciliation, duplicate detection, periodic auto-import) are not active scope.

**Open blockers:** None.

## Product Contract

### Summary

Expand the current PDF-only import-report feature into a multi-format intelligent import system. Users upload or paste any file (PDF, screenshot, Excel), the system detects the format and routes it through the appropriate extraction pipeline, the `import-parse` AI agent classifies each item as Asset or Liability with extracted field values. A progress display shows parsing phases (format detected → extracting → AI parsing → complete). Parsed results persist in a `draft_imports` staging table, enabling batch undo, import history review, and future analysis. An interactive preview page lets users edit all fields with confidence indicators before batch committing via MCP tools. The feature moves from `/settings/import-report` to `/finance/import`.

**v1 scope decision:** Wish import is deferred to a later phase. Purchase screenshots represent already-acquired items (assets) or outstanding balances (liabilities), not wishes. This eliminates the need for a Wish MCP tool and simplifies the AI classification prompt.

### Problem Frame

The current import feature only accepts PDF bank statements and lives under `/settings/import-report` — a route that implies configuration rather than data ingestion. In practice, families track assets through diverse sources: e-commerce purchase screenshots (JD, Taobao, Amazon), Excel spreadsheets from brokers or banks, and PDF statements. Each requires manual data entry. The preview page only allows editing name and current_value, leaving all other fields (type, category, currency) immutable despite AI uncertainty. The confirm endpoint only creates Assets, not Liabilities or Wishes. As the number of import sources grows, the friction of manual entry outweighs the benefit of the feature.

### Requirements

**File Ingestion**

- **R1.** The import page accepts files of type: `application/pdf`, `image/png`, `image/jpeg`, `application/vnd.openxmlformats-officedocument.spreadsheetml.xlsx`, `application/vnd.ms-excel`, `text/csv`. Maximum file size: 25MB for PDF and images, 10MB for Excel/CSV.
- **R2.** The import page supports clipboard paste (Ctrl+V / Cmd+V) for image files. Pasting extracts the image blob and sends it directly to the parse endpoint without requiring a file picker dialog.
- **R3.** The backend exposes a single `/import/parse` endpoint that accepts any supported file type. Format detection is server-side — the frontend sends the file, the backend determines the extraction strategy.
- **R4.** File format handling uses conditional dispatch: images pass through directly as `image_paths`; PDFs use existing pdfplumber + pymupdf rendering to produce `image_paths`; Excel/CSV serializes rows to structured text as `text`. The `import-parse` agent receives the same contract regardless of input format.

**AI Recognition & Classification**

- **R5.** The `import-parse` agent classifies each extracted item with a `target_model` field: `asset` or `liability`. Classification is based on content signals (e.g., credit card balance → liability; product purchase → asset; loan statement → liability). Completed purchase screenshots are classified as assets (goods owned) or liabilities (outstanding balances), never wishes.
- **R6.** For each item, the agent extracts fields appropriate to the target model. Asset items get `name`, `asset_type`, `current_value`, `currency`, `category_hint`, `institution`. Liability items get `name`, `original_amount`, `remaining_amount`, `monthly_payment`, `interest_rate`, `currency`.
- **R7.** The agent returns a per-item `confidence` score (0.0–1.0) for the overall extraction. Items with confidence < 0.6 are flagged for user review (red indicator).
- **R7a.** If the AI extraction produces zero items, the system shows "No recognizable financial data found in this file" with guidance on supported formats. If the AI call fails or times out, a retry button is shown.

**Preview & Editing**

- **R8.** The preview page groups items by `target_model` (Asset / Liability) with appropriate icons and section headers.
- **R9.** Each item in the preview is fully editable. Users can modify: `name`, `target_model` (reclassify between asset/liability), `asset_type` (for assets), `category` (via picker from system categories), `current_value` / `original_amount`, `currency`, `institution`. When switching `target_model`, `name` and `currency` are preserved; model-specific fields are reset. Confidence scores remain static from initial AI classification (not recalculated after editing).
- **R10.** Each item displays a confidence indicator: green with checkmark icon (confidence ≥ 0.8), yellow with warning icon (0.6 to <0.8), red with exclamation icon (< 0.6 or warning present). Color is supplemented by icon and text label for accessibility (WCAG 1.4.1). Red items are grouped at the top of each model section for easy review.
- **R11.** Users can delete individual items from the preview before confirming. Deleted items are not committed.
- **R12.** The preview summary bar shows counts per model type: "3 assets, 2 liabilities".

**Commit & Data Writing**

- **R13.** The confirm endpoint creates or updates records across both models (Asset, Liability) in a single batch. Each item is routed to the appropriate model based on its `target_model` field. Before committing, a duplicate check compares incoming items against existing records by (family_id, name, value, currency). If matches exist, a warning is shown in the preview: "N 项与已有记录重复". The duplicate check is performed after file upload and before parse to save bandwidth — a file hash match against recent `draft_imports` shows a `van-dialog` with "此文件已于 [日期] 导入过 [N] 项，是否继续？" (cancel: 取消导入 / proceed: 继续导入).
- **R14.** The confirm flow uses MCP batch write tools (`import_assets_batch`, `import_liabilities_batch`) as the default write path, providing per-item success/failure status in the response.
- **R15.** The preview page displays per-item commit results: success (green check), failure (red with error message). Partial failures are reported clearly.

**Route & Navigation**

- **R16.** The import page moves from `/settings/import-report` to `/finance/import`. The old route uses a Vue Router client-side redirect to `/finance/import` (not an HTTP 301).
- **R17.** The FinanceHubPage displays an "import" action button in the page header (not a tab). Tapping it navigates to `/finance/import`.

**Parse Progress Display**

- **R18.** The parse endpoint shows a generic progress phase to the frontend before parsing begins. The UI displays: "正在解析文件，请稍候…" (Parsing file, please wait…). For large files (>5MB or multi-page PDFs), additional text: "大文件可能需要1-2分钟" (Large files may take 1-2 minutes). Page-level progress (e.g., "page 3/12") is deferred to v1.1 with SSE streaming.
- **R19.** The frontend displays a progress UI during parsing: phase label with spinner, transitioning to the preview page when complete. The parse is asynchronous — the backend returns all items at once after processing.
- **R20.** For multi-page PDFs, the progress indicator shows the total page count upfront: "正在解析 12 页 PDF…" (Parsing 12-page PDF…) before the parse begins. Per-page progress is deferred to v1.1.

**Draft Staging & Import History**

- **R21.** Every parse operation creates a `draft_imports` record with status `pending`. The record stores: `family_id`, `user_id`, `source_filename`, `source_format`, `file_hash` (SHA-256 for duplicate detection), `parsed_items` (JSON of all extracted items with AI classifications), `status` (pending/committed/rolled_back), `created_at`. Raw uploaded files are deleted after successful commit to bound storage.
- **R22.** When the user confirms an import, the `draft_imports` record status changes to `committed` and the committed record IDs (Asset/Liability IDs) are stored on the record. Rollback sets `is_archived=True` on imported Assets and Liabilities (reusing the existing soft-delete mechanism). Before rollback executes, the system checks for cross-references (e.g., `linked_asset_id` on liabilities, `instance_id` on activities). If references exist, rollback is blocked with: "Cannot rollback: N items are referenced by other records." Rollback requires explicit user confirmation showing item count and names.
- **R23.** A "Recent Imports" section on the import page shows the last 20 draft_imports records with: source filename, date, item count, status (pending/committed/rolled_back). Users can tap a committed record to view what was imported and trigger a rollback. Retention policy: committed records retained for 1 year; rolled_back/pending records auto-purged after 90 days.
- **R24.** Rollback is available for committed imports within 30 days of import. After 30 days, the rollback option is no longer available (prevents cascading issues with long-settled data). Rolling back sets `is_archived=True` on all records created by that import batch and updates the `draft_imports` status to `rolled_back`. The rollback event (who, when, what) is recorded on the draft_imports record for audit.

### Key Decisions

- **Single unified entry point.** One import page at `/finance/import` handles all formats and all target models. No per-detail-page import entries. Governs R16, R17. (session-settled: user-approved — chose unified entry over per-detail or per-section entry: simpler mental model, one page to maintain)
- **Server-side format detection.** The backend determines file type and routes to the appropriate extraction strategy. The frontend sends files without format-specific handling. Governs R3, R4.
- **Conditional dispatch for extraction.** File format handling uses simple conditional dispatch (image → vision pipeline, PDF → render then vision, Excel/CSV → serialize rows). A formal strategy pattern is deferred until a 4th format is actually needed. Governs R4.
- **Synchronous parse with generic progress for v1.** The parse endpoint returns a complete JSON response after processing all pages/items. A generic progress message is shown during parsing ("正在解析文件…" with optional "大文件可能需要1-2分钟" for large files). Per-page progress is deferred to v1.1 with SSE streaming. Governs R18, R19, R20.
- **Persistent draft staging with is_archived rollback.** Every parse creates a `draft_imports` record that persists across sessions. Rollback sets `is_archived=True` (reusing existing mechanism on Asset, adding to Liability). Raw files deleted after commit to bound storage. Governs R21, R22, R23, R24.
- **Asset + Liability only for v1.** Wish import deferred — purchase screenshots represent already-acquired items, not wishes. Simplifies AI classification and eliminates the need for a Wish MCP tool. Governs R5, R6, R8, R13.

### Actors

- **Adult family member** — the primary user who uploads files, reviews the preview, edits fields, and confirms the import. Must have `require_adult` role.
- **import-parse agent** — the AI agent that receives extracted text/images, classifies items by target model, extracts field values, and assigns confidence scores.
- **MCP batch write tools** — `import_assets_batch` and `import_liabilities_batch` execute the confirmed writes and return per-item status.

### Key Flows

**Flow 1: Upload → Parse → Preview → Confirm**

1. User navigates to `/finance/import` (or follows client-side redirect from `/settings/import-report`).
2. User uploads a file via the file picker, or pastes from clipboard (Ctrl+V).
3. Frontend sends file to `POST /import/parse`. UI shows phase progress: "Detecting format" → "Extracting content" → "AI parsing".
4. Backend creates a `draft_imports` record (status=pending), computes file hash, detects format, runs extraction pipeline.
5. Backend calls `import-parse` agent with extracted content.
6. Agent classifies each item (asset/liability), extracts fields, assigns confidence.
7. Backend runs duplicate check against existing records. Returns `ImportPreview` with items grouped by `target_model`, duplicate warnings, and confidence indicators.
8. Preview page renders items grouped by model type, with red items at top of each group.
9. User edits fields, reclassifies items, deletes unwanted rows.
10. User taps "Confirm". Frontend sends `POST /import/confirm` with edited items.
11. Backend routes each item to the appropriate model, calls MCP batch write tools, updates `draft_imports` status to `committed`, deletes raw file.
12. Preview displays per-item commit results.

**Flow 2: Route Migration**

1. User navigates to `/settings/import-report` (bookmark, deep link, or old habit).
2. Vue Router client-side redirect to `/finance/import`.
3. Import page renders normally at the new location.

**Flow 3: Import History & Rollback**

1. User navigates to `/finance/import`. The "Recent Imports" section shows the last 20 import records.
2. User taps a committed import record. A detail view shows all items that were created/updated by that import.
3. System checks for cross-references (linked assets, activities). If references exist, shows warning and blocks rollback.
4. If no blockers, user taps "Rollback". Confirmation dialog shows: "撤销导入 招商银行信用卡.xlsx 的 5 项记录？已创建的记录将被归档。"
5. User confirms. Backend sets `is_archived=True` on imported records, updates `draft_imports` status to `rolled_back`, records the rollback event.
6. Confirmation toast: "已撤销 5 项导入".

### Scope Boundaries

**In scope:**
- Route migration with Vue Router client-side redirect
- Multi-format file upload (PDF, images, Excel, CSV)
- Clipboard paste for images
- Server-side format detection with conditional dispatch
- AI classification into Asset/Liability (Wish deferred)
- Interactive preview with full field editing and confidence indicators
- Multi-model batch commit via MCP tools
- Parse progress display with phase labels
- Persistent `draft_imports` staging table with import history
- Soft-delete rollback with dependency checks and 30-day window
- Duplicate import detection via file hash
- Retention policy (raw files deleted after commit, records auto-purged)

**Out of scope (deferred):**
- SSE streaming parse (may revisit as v1.1 if multi-page PDF latency is a real pain point)
- Wish import (purchase screenshots are assets/liabilities, not wishes)
- Ambient folder watch / share sheet integration
- Multi-source fusion / cross-file reconciliation
- Column mapping memory / template learning
- Per-asset-detail-page import entry
- E-commerce platform-specific extraction prompts (JD/Taobao/Amazon) — generic vision extraction for v1
- HEIC image format (most sharing paths auto-convert to JPEG)

### Acceptance Examples

**AE1. Screenshot import.** User pastes a JD.com order screenshot showing "Sony WH-1000XM5 ¥2,299". The preview shows one item: target_model=asset, name="Sony WH-1000XM5", current_value=2299, currency=CNY, category_hint=electronics, confidence=0.85 (green). User confirms. One Asset record is created.

**AE2. Excel import with mixed types.** User uploads an Excel file with 4 rows: 3 assets (bank deposits), 1 liability (credit card balance). The preview groups them: "3 assets" section, "1 liability" section. User edits the liability's remaining_amount and confirms. 3 Assets + 1 Liability created.

**AE3. Reclassification in preview.** AI classifies a JD screenshot item as "asset" but user recognizes it as a credit card balance (liability). User changes target_model from asset to liability in the preview. The field set updates to show liability-specific fields. User fills in remaining_amount and confirms. One Liability created.

**AE4. Low-confidence review.** An image-based PDF produces 3 items. Two have confidence 0.9 (green), one has confidence 0.4 (red). The red item's name is partially garbled. User edits the name, verifies the value, and confirms all three.

**AE5. Route redirect.** User has a bookmark to `/settings/import-report`. Clicking it navigates to `/finance/import`. The import page renders correctly.

**AE6. Parse progress display.** User uploads a 12-page scanned PDF. The UI shows "正在解析 12 页 PDF，请稍候…" (Parsing 12-page PDF, please wait…) with a spinner. After ~2 minutes, the parse completes and the preview page shows all extracted items.

**AE7. Import history & rollback.** User confirms an import of 5 items from "招商银行信用卡.xlsx". The import record appears in "Recent Imports" with status "committed". Two days later, user discovers one item was wrong. User taps the import record, sees all 5 items, taps "Rollback". System checks for cross-references — none found. Confirmation dialog shows "Rollback 5 items?". User confirms. All 5 records are soft-deleted. The import record shows status "rolled_back".

**AE8. Duplicate import detection.** User accidentally uploads the same "招商银行信用卡.xlsx" file again. The system detects the file hash matches a record from 2 days ago and shows: "This file was already imported on 2026-08-01 with 5 items. Import again anyway?" User can choose to cancel or proceed.

### Outstanding Questions

- **Resolved (see KTD1):** The `ImportPreview` response schema extends the existing `ImportPreviewItem` with `target_model` and `confidence` fields. No new schema needed.
- **Deferred to Planning:** How should the agent's prompt be structured to reliably classify items as asset vs liability? The import-parse agent's SKILL.md needs updating with multi-model classification instructions and few-shot examples.
- **Resolved (see KTD3):** The `draft_imports` table uses `Text` for `parsed_items` JSON with Python-side serialization, consistent with `Asset.properties`. Index on `(family_id, created_at)`.
- **Deferred to Implementation:** Should the import feature support update-in-place for existing assets (re-importing an updated bank statement to update current_value without creating duplicates)? The existing `matched_asset_id` + `action: update` mechanism handles this for PDF imports; multi-format matching logic refinement is an implementation-time decision.

### How This Work Fits Together

<!-- ce-section: work-relationships -->

This plan owns the import feature end-to-end: file ingestion, AI extraction, parse progress display, preview/edit UX, multi-model commit, draft staging with history, and soft-delete rollback.

Related work that is not active scope:
- **Wish import** — deferred from this plan. Purchase screenshots represent already-acquired items (assets) or outstanding balances (liabilities), not wishes. Can be revisited if user demand emerges.
- **SSE streaming parse** — deferred from this plan. Phase-label progress display covers the 80% case. If multi-page PDF latency becomes a real pain point, true incremental streaming can be added without changing the data model.
- **Reconciliation and duplicate detection** — depends on this plan (needs multi-model import as a data source; `draft_imports` records provide an audit trail for reconciliation). Can proceed independently but benefits from import's event emission.
- **E-commerce platform-specific extraction** — shares the extraction pipeline. Can proceed independently as format-specific prompt enhancements.
- **Multi-source fusion / cross-file reconciliation** — depends on `draft_imports` records for cross-referencing. Can proceed independently after this plan ships.
- **Column mapping memory / template learning** — can store learned templates alongside `draft_imports` records. Can proceed independently.

---

## Planning Contract

**Product Contract preservation:** unchanged. Product Contract meaning, R-IDs, A/F/AE-IDs preserved.

### Key Technical Decisions

**KTD1. Extend ImportPreview schema rather than creating a new one.** The existing `ImportPreview` response schema (in `server/apps/backend/app/routers/import_report.py`) gains `target_model` and `confidence` fields per item. `ImportPreviewItem` becomes: `{temp_id, name, target_model, asset_type, category_hint, current_value, currency, quantity, notes, matched_asset_id, matched_asset_name, action, warning, confidence}`. This avoids schema duplication. Governs R5, R7, R8, R9.

**KTD2. Conditional dispatch over strategy pattern for file extraction.** Three formats (image, PDF, Excel/CSV) map to two effective code paths: vision (image + PDF) and tabular (Excel/CSV). A strategy pattern adds class hierarchy overhead for 2 branches. Use `if/elif` dispatch in a single function. Governs R4.

**KTD3. draft_imports table uses Text column for parsed_items JSON.** The parsed items array varies in size (1–50+ items, each with 10+ fields). A JSON column type is DB-specific (SQLite JSON1 vs PostgreSQL jsonb). Using `Text` with Python-side `json.dumps`/`json.loads` keeps the model portable across DB backends, consistent with how `Asset.properties` already stores JSON in this codebase. Governs R21.

**KTD4. Rollback reuses `is_archived` on Asset, adds `is_archived` to Liability.** Asset already has `is_archived` (45 query sites filter `is_archived=False`). Adding a separate `deleted_at` column would require updating all 45 filter sites. Instead: rollback sets `is_archived=True` on imported Assets (existing filter handles it) and adds `is_archived` to Liability model. No new column on Asset. Governs R22, R24.

**KTD5. File size limits split by type.** Scanned PDFs from Chinese banks routinely exceed 10MB. Images from phones can be 5-15MB. Excel/CSV files are typically <1MB. Split limits: 25MB for PDF/images, 10MB for Excel/CSV. Governs R1.

### Assumptions

- The `import-parse` agent's existing vision pipeline (pymupdf render → view_image MCP tool) works for standalone image uploads without modification. The agent accepts `image_paths` in its request body already.
- The existing `import_assets_batch` and `import_liabilities_batch` MCP tools handle the confirm flow. No new MCP tools are needed since Wish import is deferred.
- The `require_adult` dependency already gates all import endpoints — no new auth changes needed.
- The `draft_imports` table will be small (tens of records per family) — no special indexing strategy needed beyond `(family_id, created_at)`.

### Sequencing

```
U1 (draft_imports table) → U2 (backend: parse + confirm + history + rollback + extraction)
                          → U3 (route migration) [independent]
U2 → U4 (frontend: import page rewrite)
U4 → U5 (import history + rollback UI)
```

U3 (route migration) is independent and can ship in parallel or first.

---

## Implementation Units

### U1. draft_imports Database Table and Alembic Migration

**Goal:** Create the `draft_imports` table for persistent import staging, history, and rollback tracking.

**Requirements:** R21, R22, R23, R24

**Dependencies:** None

**Files:**
- Create: `server/apps/backend/app/models/draft_import.py`
- Create: `server/apps/backend/alembic/versions/<hash>_add_draft_imports_table.py`
- Modify: `server/apps/backend/app/models/__init__.py` (register model)

**Approach:**
1. Create SQLAlchemy model `DraftImport(Base)` with fields: `id` (BigInteger PK, snowflake), `family_id`, `user_id`, `source_filename` (String 500), `source_format` (String 20), `file_hash` (String 64, nullable), `parsed_items` (Text, JSON-serialized), `committed_record_ids` (Text, JSON-serialized array), `status` (String 20, default "pending"), `rolled_back_at` (DateTime, nullable), `created_at` (DateTime). Add `is_archived` (Boolean, default False) to Liability model for rollback support — Asset already has this field. No new column on Asset.
2. Create Alembic migration with `has_table` guard for fresh-DB idempotency. Index on `(family_id, created_at)`.
3. Register model in `__init__.py`.

**Patterns to follow:** Existing model pattern in `server/apps/backend/app/models/asset.py` — snowflake PK via `next_id`, `family_id` foreign key, `Base` inheritance from `server/packages/db`. Alembic guard pattern from `bootstrap` migrations.

**Test scenarios:**
- Model instantiation with all fields produces valid ORM object
- Alembic `upgrade head` succeeds on fresh SQLite database
- Alembic `upgrade head` is idempotent (second run succeeds without error)
- `parsed_items` JSON serialization round-trips correctly (Python dict → Text → Python dict)

**Verification:** `uv run pytest tests/backend/models/test_draft_import.py -v` passes. `uv run alembic upgrade head` succeeds on a fresh database.

### U2. Backend: /import/parse, /confirm, /history, /rollback + Multi-Format Extraction

**Goal:** Replace `/parse-pdf` with unified `/parse` (including multi-format extraction), extend `/confirm` for multi-model + draft staging, add `/history` and `/rollback` endpoints.

**Requirements:** R1, R3, R4, R13, R14, R15, R21, R22, R23

**Dependencies:** U1

**Files:**
- Modify: `server/apps/backend/app/routers/import_report.py` (endpoints, extraction logic, inline schemas at lines 187-223)
- Create: `server/apps/backend/tests/test_import_endpoints.py`
- Create: `server/apps/backend/tests/test_extraction.py`

**Approach:**
1. Add `target_model` (str, default "asset"), `confidence` (float, nullable) to `ImportPreviewItem` schema. Add `file_hash` to internal processing.
2. Rename `POST /parse-pdf` to `POST /parse`. Accept any file type from R1. Compute SHA-256 hash of uploaded file. Create `DraftImport` record (status=pending). Detect format and extract:
   - **Image** (png, jpeg): save to sandbox, set `image_paths=[path]`, `text=""`. Agent's view_image reads directly.
   - **PDF**: reuse existing `_extract_pdf_text` + `_is_image_based_pdf` + `_render_pdf_pages_to_sandbox` pipeline unchanged.
   - **Excel/CSV**: read with openpyxl (xlsx) or csv module. Serialize rows to structured text. Set as `text`, `image_paths=[]`.
3. Call import-parse agent with extracted content. Run asset/liability matching. Return enriched `ImportPreview`. If extraction produces zero items, return preview with empty items list and a `message` field: "未在文件中识别到财务数据" (R7a).
4. Extend `POST /confirm` to: (a) look up `draft_import` by request context, (b) run duplicate check per R13, (c) route creates through MCP batch tools per R14 (`import_assets_batch` for assets, `import_liabilities_batch` for liabilities), (d) route updates through direct DB write via existing `matched_asset_id` logic, (e) update `draft_import` status to "committed" with record IDs, (f) delete raw file from sandbox, (g) return per-item results per R15. After commit, scroll target: show summary "N 成功，M 失败" at top of results, auto-scroll to first failure if any.
5. Add `GET /history` — return last 20 `draft_imports` records for the family, ordered by `created_at desc`, with status and item counts.
6. Add `POST /rollback/{draft_id}` — (a) load draft_import, (b) verify status="committed" and created_at within 30 days, (c) check for cross-references on committed record IDs (query `linked_asset_id` on liabilities, `instance_id` on activities), (d) if references found, return 409 with details, (e) set `is_archived=True` on imported records, (f) update draft_import status to "rolled_back", (g) record rollback event.

**Patterns to follow:** Existing endpoint pattern in `import_report.py` — `require_adult` dependency, `get_db` session, `UploadFile` handling. MCP batch write pattern from `confirm-via-agent` endpoint. Extraction helpers (`_extract_pdf_text`, `_render_pdf_pages_to_sandbox`) already in the same file.

**Test scenarios:**
- `POST /parse` with PDF file creates draft_import record with status=pending and returns ImportPreview with target_model and confidence per item
- `POST /parse` with PNG image creates draft_import and returns items classified by vision
- `POST /parse` with XLSX file creates draft_import and returns items from tabular extraction
- `POST /parse` with unrecognizable file returns empty items with guidance message (R7a)
- `POST /confirm` with mixed asset/liability items creates records in both models via MCP batch tools and updates draft_import to committed
- `POST /confirm` with duplicate items returns warning but allows proceed
- `GET /history` returns last 20 records with correct status and counts
- `POST /rollback/{id}` with committed draft sets is_archived=True on records and updates status
- `POST /rollback/{id}` when records are referenced returns 409
- `POST /rollback/{id}` after 30 days returns 409

**Verification:** `uv run pytest tests/backend/test_import_endpoints.py tests/backend/test_extraction.py -v` passes. `uv run ruff check apps/backend/app/routers/import_report.py` clean.
   - **PDF**: reuse existing `_extract_pdf_text` + `_is_image_based_pdf` + `_render_pdf_pages_to_sandbox` pipeline unchanged.
   - **Excel/CSV**: read with openpyxl (xlsx) or csv module (csv). Serialize rows to structured text: each row as `{"col_a": val1, "col_b": val2, ...}`. Return as `text` with `image_paths=[]`. The agent classifies columns by content heuristics.
2. Set file size limits per R1: 25MB for PDF/images, 10MB for Excel/CSV. Validate in the `/parse` endpoint before processing.
3. Save uploaded files to family-scoped sandbox directory for raw file retention (deleted after commit per R21).

**Patterns to follow:** Existing `_extract_pdf_text` and `_render_pdf_pages_to_sandbox` functions. Sandbox path pattern: `{DATA_ROOT}/workspaces/users/{family_id}/threads/{thread_id}/user-data/uploads/`.

**Test scenarios:**
- Image upload (PNG) produces `image_paths` with one entry and empty text
- Excel upload produces structured text with row-per-line format
- CSV upload produces structured text
### U3. Route Migration: /settings/import-report → /finance/import

**Goal:** Move the import page route and add navigation entry point.

**Requirements:** R16, R17

**Dependencies:** None (independent)

**Files:**
- Modify: `frontend/apps/main/src/router/index.ts`
- Modify: `frontend/apps/main/src/pages/FinanceHubPage.vue`
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`

**Approach:**
1. In router, change the import route from `settings/import-report` to `finance/import`. Add a redirect: `{ path: 'settings/import-report', redirect: '/finance/import' }`.
2. In FinanceHubPage.vue, add an import action button in the page header area (above the van-tabs). Use a `van-button` with `icon="upload"` and `type="primary"` `size="small"`, with `@click="$router.push('/finance/import')"`. Add i18n key `finance.importButton`.
3. Update i18n: add `finance.importButton: "导入"` in zh-CN. Update `settings.importReport` reference to `finance.import` in the page header.

**Patterns to follow:** Existing route structure in `router/index.ts`. Existing button pattern from other hub pages.

**Test scenarios:**
- Navigating to `/settings/import-report` redirects to `/finance/import`
- Import button on FinanceHubPage navigates to `/finance/import`
- Import page renders correctly at new route

**Verification:** `cd frontend/apps/main && pnpm typecheck` passes. Manual test: visit `/settings/import-report` and verify redirect.

### U4. Frontend: Import Page Rewrite (Upload, Preview, Commit)

**Goal:** Rewrite ImportReportPage.vue to support multi-format upload, clipboard paste, progress display, multi-model preview with full editing, confidence indicators, duplicate warnings, and commit with per-item results.

**Requirements:** R1, R2, R5, R6, R7, R7a, R8, R9, R10, R11, R12, R13, R14, R15, R18, R19, R20

**Dependencies:** U2

**Files:**
- Modify: `frontend/apps/main/src/pages/ImportReportPage.vue`
- Modify: `frontend/apps/main/src/api/importReport.ts`
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- Create: `frontend/apps/main/tests/pages/ImportReportPage.spec.ts` (or extend existing)

**Approach:**

*Upload step:*
1. Update `van-uploader` accept attribute to `application/pdf,image/png,image/jpeg,.xlsx,.xls,.csv`. Set max-size to 25MB.
2. Add clipboard paste handler: listen for `paste` event on the page, extract `event.clipboardData.files`, filter for image types, trigger the same upload flow.
3. Update `importReport.ts` API: change `parsePdf` to `parseFile`, endpoint `/import/parse-pdf` → `/import/parse`.

*Parse progress step:*
4. Replace `van-loading` spinner with progress display: "正在解析文件，请稍候…" with spinner. For files >5MB or multi-page PDFs, add "大文件可能需要1-2分钟".

*Preview step:*
5. Group items by `target_model` into two sections: "资产 (N)" and "负债 (N)" with icons and section headers.
6. Per item, render editable fields by target_model:
   - Asset: name, target_model (van-picker: asset/liability), asset_type (van-picker: financial/physical), category (van-picker from system categories), current_value (van-field inputmode="decimal"), currency, institution
   - Liability: name, target_model, category (van-picker: mortgage/car_loan/other), original_amount (inputmode="decimal"), remaining_amount (inputmode="decimal"), monthly_payment (inputmode="decimal"), interest_rate (inputmode="decimal"), currency, institution
   - On target_model switch: preserve `name` and `currency`, reset model-specific fields.
7. Confidence indicator per item: green chip with ✓ (≥0.8), yellow chip with ⚠ (0.6 to <0.8), red chip with ✕ (<0.6). Red items sorted to top of each section.
8. Delete button per item (van-icon name="delete"). Removed items excluded from confirm.
9. Show duplicate warning banner if parse response includes duplicate warnings.
10. Summary bar: "共 N 项：X 资产，Y 负债".
11. If parse returns zero items (R7a), show "未在文件中识别到财务数据" with supported format guidance.

*Commit:*
12. Confirm button: POST `/import/confirm`. After response, show summary "N 成功，M 失败" at top, auto-scroll to first failure. Per-item results: ✓ for success, ✕ with error message for failure.

**Patterns to follow:** Existing `ImportReportPage.vue` three-step wizard pattern. Existing `van-uploader` + `handleFileRead` pattern. Vant 4 `van-picker` for dropdowns. Existing `van-tag` for status display.

**Test scenarios:**
- van-uploader accepts PDF, PNG, JPEG, XLSX, XLS, CSV files
- Pasting an image from clipboard triggers upload flow
- Paste event with non-image content is ignored
- Progress display shows "正在解析文件…" during parse
- File exceeding 25MB shows fileTooLarge toast
- Preview shows items grouped by target_model with section headers
- Confidence indicators render correct colors and icons based on score thresholds
- Red items appear at top of each section
- User can change target_model from asset to liability; name/currency preserved, model-specific fields reset
- User can delete items and they are excluded from confirm request
- Duplicate warning banner shows when parse response includes duplicates
- Confirm with mixed items creates assets and liabilities
- Per-item commit results show success/failure with summary at top
- Zero-items response shows "未在文件中识别到财务数据" message

**Verification:** `cd frontend/apps/main && pnpm typecheck` passes. `pnpm test:run` passes. Manual test: import a JD screenshot, edit fields, confirm, verify records created.

### U5. Import History and Rollback UI

**Goal:** Add the "Recent Imports" section, import detail view, and rollback interaction.

**Requirements:** R22, R23, R24

**Dependencies:** U4

**Files:**
- Modify: `frontend/apps/main/src/pages/ImportReportPage.vue`
- Modify: `frontend/apps/main/src/api/importReport.ts`
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`

**Approach:**
1. Below the upload area (visible in `upload` step), add a "近期导入" section. Call `GET /import/history` on page mount. Show a loading spinner while the request is in flight. If the result is empty, show an empty state: "暂无导入记录" with hint "上传文件或粘贴截图开始导入". Render last 20 records as a list: source_filename, date (formatted), item count, status badge (pending/committed/rolled_back). Use inline expansion for the detail view (avoids navigation complexity on mobile).
2. Tapping a committed record navigates to a detail view (can be inline expansion or a dialog). Show all items from `parsed_items` with their committed status.
3. Add "撤销导入" button on detail view. On tap: show `van-dialog` confirmation: "撤销导入 [filename] 的 N 项记录？已创建的记录将被标记删除。"
4. On confirm: POST `/import/rollback/{draft_id}`. If success, show toast "已撤销 N 项导入" and refresh the history list. If 409 (references exist), show error dialog with reference details. If past 30 days, show "超过 30 天撤销期限".

**Patterns to follow:** Existing `van-cell-group` list pattern. Existing `van-dialog` for confirmations. Existing toast pattern.

**Test scenarios:**
- History list shows last 20 records with correct metadata
- Tapping a committed record shows detail view with items
- Rollback confirmation dialog shows correct item count
- Successful rollback sets is_archived=True on records and shows toast
- Rollback with referenced records shows 409 error dialog
- Rollback after 30 days shows expiry message

**Verification:** `cd frontend/apps/main && pnpm typecheck` passes. Manual test: import, rollback, verify records soft-deleted.

---

## Verification Contract

**Backend:**
```bash
cd server
uv run pytest tests/backend/test_import_endpoints.py tests/backend/test_extraction.py tests/backend/models/test_draft_import.py -v
uv run ruff check apps/backend/app/routers/import_report.py apps/backend/app/models/draft_import.py
uv run mypy apps/backend/app/routers/import_report.py
cd apps/backend && uv run alembic upgrade head
```

**Frontend:**
```bash
cd frontend/apps/main
pnpm typecheck
pnpm test:run
pnpm lint
```

**Integration:**
- Upload a PDF bank statement → verify items appear with target_model=asset and confidence scores
- Upload a JD screenshot → verify vision pipeline produces asset items
- Upload an Excel file → verify tabular extraction produces classified items
- Import mixed items → verify assets and liabilities created correctly
- Import same file twice → verify duplicate warning shown
- Rollback a committed import → verify records soft-deleted and status updated

---

## Definition of Done

**Global:**
- [ ] All 24 requirements (R1–R24 + R7a) have corresponding test coverage
- [ ] All 8 acceptance examples (AE1–AE8) pass manual verification
- [ ] Backend tests pass: `pytest` green, `ruff check` clean, `mypy` clean
- [ ] Frontend tests pass: `typecheck` clean, `vitest` green, `lint` clean
- [ ] Alembic migration succeeds on fresh SQLite database
- [ ] No `TODO`, `FIXME`, or placeholder comments in committed code
- [ ] All i18n strings defined in `zh-CN.ts` (no hardcoded Chinese in .vue files)
- [ ] Route redirect from `/settings/import-report` to `/finance/import` works
- [ ] File upload accepts all formats in R1 with correct size limits
- [ ] Rollback sets is_archived=True with dependency pre-check and 30-day window

**Per-unit:**
- [ ] U1: Model registered, migration passes, JSON round-trip verified
- [ ] U2: All 4 endpoints functional with multi-format extraction, auth, error handling, per-item results
- [ ] U3: Redirect works, FinanceHub button navigates correctly
- [ ] U4: Full import page — upload, progress, preview with editing, commit with results, all interaction states covered
- [ ] U5: History list with empty/loading states, detail view, rollback with confirmation and error handling
