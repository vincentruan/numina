---
title: FastAPI Pydantic v2 Validation Error Localization with Composable Frontend Error State
date: 2026-04-16
category: best-practices
module: authentication
problem_type: best_practice
component: form_validation
severity: high
applies_when:
  - Implementing form validation with Pydantic v2 in FastAPI
  - Requiring localized validation error messages across multiple languages
  - Building composable error state management in Vue 3
  - Handling 422 validation responses with structured error details
tags:
  - pydantic-v2
  - fastapi
  - validation-errors
  - error-localization
  - i18n
  - vue3
  - composables
  - form-handling
---

# FastAPI Pydantic v2 Validation Error Localization with Composable Frontend Error State

## Context

When building full-stack applications with FastAPI and Vue 3, validation errors from the backend need to be properly localized and routed to individual form fields on the frontend. A common gap occurs when:

- Backend `_VALIDATION_CODE_MAP` only covers a subset of Pydantic v2 error types
- The `else` branch in `validation_error_handler` falls back to raw Pydantic messages instead of locale strings
- Frontend has no mechanism to extract field-level errors from 422 responses and bind them to form inputs

This creates a poor user experience: validation messages appear in English (or as raw error codes), even when the application supports multiple languages, and errors aren't tied to specific fields.

## Guidance

Implement a three-layer validation error pipeline: backend code map → locale messages → frontend composable.

### 1. Backend: Expand the validation code map

In `backend/app/error_handlers.py`, maintain a comprehensive `_VALIDATION_CODE_MAP` covering all Pydantic v2 error types your application encounters.

**Critical discovery:** Pydantic v2 uses `int_parsing` (not `int_parsing_error`) for string-to-int coercion failures. Verify actual type names by running:

```python
from pydantic import BaseModel
class M(BaseModel):
    age: int
try:
    M(age='not-a-number')
except Exception as e:
    for err in e.errors():
        print(err['type'])  # prints: int_parsing
```

Complete map covering common types:

```python
_VALIDATION_CODE_MAP = {
    "missing": "REQUIRED",
    "string_too_short": "TOO_SHORT",
    "string_too_long": "TOO_LONG",
    "value_error": "INVALID_VALUE",
    "string_pattern_mismatch": "INVALID_FORMAT",
    "int_type": "INVALID_TYPE",
    "float_type": "INVALID_TYPE",
    "string_type": "INVALID_TYPE",
    "bool_type": "INVALID_TYPE",
    "int_parsing": "INVALID_TYPE",       # NOT int_parsing_error
    "float_parsing": "INVALID_TYPE",     # NOT float_parsing_error
    "greater_than": "INVALID_VALUE",
    "greater_than_equal": "INVALID_VALUE",
    "less_than": "INVALID_VALUE",
    "less_than_equal": "INVALID_VALUE",
    "enum": "INVALID_VALUE",
    "url_type": "INVALID_FORMAT",
    "datetime_type": "INVALID_FORMAT",
}
```

### 2. Backend: Use locale lookup in the else branch

Update `validation_error_handler` to attempt locale lookup before falling back to raw Pydantic messages:

```python
# Before
msg = error.get("msg", code)

# After
locale_key = f"VALIDATION_{code}"
locale_msg = _get_message(locale_key, lang)
msg = locale_msg if locale_msg != locale_key else error.get("msg", code)
```

`_get_message` returns the key itself when not found — so `locale_msg != locale_key` detects a missing key and falls back gracefully to the raw Pydantic message.

### 3. Locale files: Add missing validation message keys

In both `zh-CN.json` and `en-US.json`, add entries using the `VALIDATION_<CODE>` prefix:

```json
{
  "VALIDATION_REQUIRED": "此字段为必填项",
  "VALIDATION_INVALID_VALUE": "输入值无效",
  "VALIDATION_INVALID_FORMAT": "格式不正确",
  "VALIDATION_INVALID_TYPE": "类型不正确",
  "VALIDATION_TOO_SHORT": "长度至少 {min_length} 位",
  "VALIDATION_TOO_LONG": "长度最多 {max_length} 位"
}
```

`TOO_SHORT` and `TOO_LONG` use `ctx` interpolation — handle them explicitly before the generic locale lookup:

```python
if code == "TOO_SHORT" and "min_length" in ctx:
    template = _get_message("VALIDATION_TOO_SHORT", lang)
    msg = template.format(min_length=ctx["min_length"])
elif code == "TOO_LONG" and "max_length" in ctx:
    template = _get_message("VALIDATION_TOO_LONG", lang)
    msg = template.format(max_length=ctx["max_length"])
else:
    locale_key = f"VALIDATION_{code}"
    locale_msg = _get_message(locale_key, lang)
    msg = locale_msg if locale_msg != locale_key else error.get("msg", code)
```

### 4. Frontend: Create a `useValidationErrors` composable

`frontend/src/composables/useValidationErrors.ts`:

```typescript
import { ref, type InjectionKey, type Ref } from 'vue'

export interface ValidationError {
  code: string
  msg: string
}

export interface UseValidationErrors {
  validationErrors: Ref<Record<string, ValidationError>>
  setErrors: (axiosError: unknown) => void
  clearErrors: () => void
  getError: (field: string) => ValidationError | undefined
}

export const validationErrorsKey: InjectionKey<UseValidationErrors> = Symbol('validationErrors')

export function useValidationErrors(): UseValidationErrors {
  const validationErrors = ref<Record<string, ValidationError>>({})

  function setErrors(axiosError: unknown): void {
    const err = axiosError as {
      response?: { status?: number; data?: { details?: Array<{ field: string; code: string; msg: string }> } }
    }
    if (err?.response?.status !== 422) return
    const details = err.response?.data?.details
    if (!Array.isArray(details)) return
    const map: Record<string, ValidationError> = {}
    for (const item of details) {
      if (item.field) map[item.field] = { code: item.code, msg: item.msg }
    }
    validationErrors.value = map
  }

  function clearErrors(): void {
    validationErrors.value = {}
  }

  function getError(field: string): ValidationError | undefined {
    return validationErrors.value[field]
  }

  return { validationErrors, setErrors, clearErrors, getError }
}
```

### 5. Wire into form pages (reference pattern)

The interceptor stays stateless — it throws the error, and the page handles it:

```typescript
// In the form page script setup
const validationErrorsComposable = useValidationErrors()
const { setErrors, clearErrors, getError } = validationErrorsComposable
provide(validationErrorsKey, validationErrorsComposable)

async function onSubmit() {
  clearErrors()  // clear before each attempt
  try {
    await authStore.register(form.value)
  } catch (error) {
    setErrors(error)  // populates field-level errors from 422
    // handle other error types (captcha, 503, etc.) separately
  }
}
```

Template binding using Vant's `:error-message` prop:

```vue
<van-field
  v-model="form.username"
  label="用户名"
  :error-message="getError('username')?.msg"
/>
<van-field
  v-model="form.password"
  label="密码"
  :error-message="getError('password')?.msg"
/>
```

## Why This Matters

- **User experience**: Validation messages appear in the user's language, not raw Pydantic error strings
- **Fail-safe**: Unknown Pydantic types fall back to `INVALID_VALUE` + raw message — never silently swallowed
- **Interceptor stays stateless**: Pages control composable lifecycle; the axios interceptor doesn't need to know about form state
- **Opt-in per page**: Pages that don't call `provide` continue to receive toast-based error display unchanged

## When to Apply

- Any FastAPI endpoint that validates request bodies with Pydantic models
- Any Vue 3 form page that should show field-level errors (not just global toasts)
- When adding a new form page: import `useValidationErrors`, provide it, bind `:error-message` on each field

## Related Docs

- `docs/solutions/best-practices/security-protection.md` — auth error handling (uses hardcoded Chinese strings; candidate for migration to AppError + error codes)
- `docs/solutions/best-practices/altcha-captcha-best-practices-2026-04-03.md` — captcha error handling in registration flow
