# Vision Model Test Optimization Design

**Date:** 2026-04-28
**Status:** Draft - Pending User Review

## Summary

Split vision model testing into two independent tests with separate buttons, results storage, and clear success criteria:
1. **文本能力测试** - validates basic text understanding capability
2. **图像理解测试** - validates OCR accuracy using embedded test image (≥80% threshold)

## Requirements

### Functional Requirements

1. Two separate test buttons for vision model:
   - 文本能力测试 button
   - 图像理解测试 button
   - Each test runs independently and stores its own results

2. Text-only test:
   - Send simple text prompt to vision model
   - Validate model responds correctly (HTTP 200/400)
   - Store success/failure status, message, latency, timestamp

3. Image OCR test:
   - Use embedded test image containing text "这是一个测试文本~"
   - Send image with prompt "请识别图片中的文字"
   - Calculate OCR accuracy using Levenshtein distance ratio
   - Success threshold: ≥80% similarity
   - Store success/failure status, accuracy percentage, extracted text snippet, latency, timestamp

### Non-Functional Requirements

- 120-second timeout per test
- Support both Anthropic and OpenAI API formats
- Base64 embedded image (no external dependencies)
- Chinese UI messages with emoji prefixes

## Architecture

### Backend Changes

**1. New API Endpoints** (`backend/app/routers/ai_config.py`):

```
POST /api/v1/ai/config/test/vision/text   → test_vision_text_only()
POST /api/v1/ai/config/test/vision/image  → test_vision_image_only()
```

Both endpoints:
- Require owner permissions
- Validate AI config exists (enabled, provider, API key, vision_model)
- Return `AIConfigTestResult` schema

**2. New Database Fields** (`backend/app/models/family.py`):

```python
# Vision model text test results
ai_vision_text_test_success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
ai_vision_text_test_message: Mapped[str | None] = mapped_column(Text, nullable=True)
ai_vision_text_test_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
ai_vision_text_test_timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

Existing `ai_vision_test_*` fields remain for OCR image test results.

**3. Embedded Test Image** (`backend/app/services/vision_test_image.py`):

```python
# Base64 encoded test image containing "这是一个测试文本~"
# Generated from frontend/src/assets/test_AI_vision.png
_TEST_IMAGE_BASE64 = (
    # ~150KB base64 string embedded directly (no external file dependency)
    # Ensures test works in Docker containers where frontend/backend are separate
    "iVBORw0KGgoAAAANSUhEUgAA..."  # Full base64 string
)

def get_test_image_data_url() -> str:
    """Return base64 data URL for test image."""
    return f"data:image/png;base64,{_TEST_IMAGE_BASE64}"
```

Note: Base64 string generated once from source image and embedded as literal in code.

**4. OCR Accuracy Calculator** (`backend/app/services/ocr_accuracy.py`):

```python
def levenshtein_ratio(s1: str, s2: str) -> float:
    """Calculate similarity ratio using Levenshtein distance."""
    # Implementation using dynamic programming
    # Returns 0.0-1.0 (0% to 100% match)

def calculate_ocr_accuracy(expected: str, actual: str) -> int:
    """Calculate OCR accuracy percentage."""
    return int(levenshtein_ratio(expected, actual) * 100)
```

**5. Test Helper Functions** (`backend/app/routers/ai_config.py`):

```python
async def _test_vision_text(family: Family, api_key: str, vision_model: str) -> dict:
    """Test vision model text capability."""
    # Send: {"model": vision_model, "max_tokens": 10, "messages": [{"role": "user", "content": "测试"}]}
    # Return: {"success": bool, "message": str, "latency_ms": int}

async def _test_vision_image_ocr(family: Family, api_key: str, vision_model: str) -> dict:
    """Test vision model OCR capability."""
    # Send image with prompt "请识别图片中的文字"
    # Expected: "这是一个测试文本~"
    # Calculate accuracy, threshold: 80%
    # Return: {"success": bool, "message": str, "latency_ms": int, "accuracy": int, "ocr_text": str}
```

### Frontend Changes

**1. New Test Buttons** (AI Config Page):

- Add to existing test button group
- Button labels with emoji:
  - `🧪 文本能力测试`
  - `🖼️ 图像理解测试`

**2. Result Display**:

Each test shows independently:
- Status badge (✅ 成功 / ❌ 失败)
- Message text
- Latency (毫秒)
- Timestamp
- OCR test additionally shows: 准确率 XX%, 识别结果 snippet

**3. Schema Updates** (`backend/app/schemas/ai_config.py`):

```python
class AIConfigResponse(BaseModel):
    # Existing fields...
    # Vision text test
    ai_vision_text_test_success: bool | None = None
    ai_vision_text_test_message: str | None = None
    ai_vision_text_test_latency_ms: int | None = None
    ai_vision_text_test_timestamp: datetime | None = None
    # Vision OCR test (existing fields renamed conceptually)
    ai_vision_test_success: bool | None = None  # OCR test
    ai_vision_test_message: str | None = None
    ai_vision_test_latency_ms: int | None = None
    ai_vision_test_timestamp: datetime | None = None

class AIConfigTestResult(BaseModel):
    # Existing fields...
    vision_text_success: bool | None = None
    vision_text_message: str | None = None
    vision_text_latency_ms: int | None = None
    vision_ocr_accuracy: int | None = None  # OCR accuracy percentage
    vision_ocr_text: str | None = None  # Extracted text snippet
```

## Data Flow

### Text Test Flow

1. User clicks 🧪 文本能力测试 button
2. Frontend calls `POST /api/v1/ai/config/test/vision/text`
3. Backend validates config, sends text prompt to vision model
4. Model responds → backend validates HTTP status
5. Backend stores result to database
6. Backend returns result → frontend displays success/failure

### Image OCR Test Flow

1. User clicks 🖼️ 图像理解测试 button
2. Frontend calls `POST /api/v1/ai/config/test/vision/image`
3. Backend loads embedded base64 image
4. Backend sends image + prompt "请识别图片中的文字" to vision model
5. Model responds with extracted text
6. Backend calculates Levenshtein ratio against expected "这是一个测试文本~"
7. Backend checks accuracy ≥ 80%
8. Backend stores result (success, accuracy, extracted text, latency)
9. Backend returns result → frontend displays accuracy and snippet

## Error Handling

- Timeout: 120 seconds → return `{"success": False, "message": "图像模型连接超时（120秒）"}`
- HTTP errors: return `{"success": False, "message": "图像模型测试失败: HTTP {status}"}`
- Missing config: return early with Chinese error message
- Provider unsupported: return `{"success": False, "message": "不支持的 Provider: {provider}"}`

All errors stored to database with `success=False` and error message.

## Testing Strategy

- Unit test for `levenshtein_ratio()` function
- Integration test for text endpoint (mock API response)
- Integration test for OCR endpoint (mock API response with known text)
- Verify database persistence after each test

## Migration

No Alembic migration needed - existing `ai_vision_test_*` fields will store OCR results, new `ai_vision_text_test_*` fields will be added via migration:

```bash
uv run alembic revision --autogenerate -m "Add vision text test fields"
uv run alembic upgrade head
```

## Implementation Priority

1. Backend: OCR accuracy calculator + embedded image loader
2. Backend: New test endpoints + helper functions
3. Backend: Database migration
4. Backend: Schema updates
5. Frontend: UI buttons + result display
6. Testing: Unit + integration tests