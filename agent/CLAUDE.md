# agent/CLAUDE.md

Module-specific guidance for the Python FastAPI AI agent microservice.
See root [`CLAUDE.md`](../CLAUDE.md) for behavioral guidelines and cross-cutting conventions.

## Quality Commands

```bash
uv run ruff check .              # lint
uv run ruff check . --fix        # lint + auto-fix
uv run ruff format .             # format (only files you touch)
uv run mypy . --exclude vendor   # type check
uv run pytest tests/ -v          # run all tests
```

## Tooling

- **ruff:** lint + format. Config in `pyproject.toml` under `[tool.ruff]`. Rules: E, F, I, UP.
- **mypy:** type checker. `ignore_missing_imports = true` is intentional — LangChain and DeerFlow stubs are incomplete. Use `# type: ignore[<code>]` with an inline comment explaining why when suppressing.
- **pytest + pytest-asyncio:** async test runner. `asyncio_mode = "auto"` is set in `pyproject.toml`.

## Key Invariants (Risk Control)

These must hold in every code path — never bypass them:

1. **PII redaction:** Always call `pii_redactor` before passing user data to any tool call or writing to logs.
2. **Policy guard:** All agent requests must pass through `policy_guard`. Never skip or short-circuit it.
3. **Audit logging:** Every agent decision must emit an audit event via `audit_logger`. This includes both success and error paths.

## Patterns

### DeerFlow Toggle

Controlled by `USE_DEERFLOW` env var (default: `false`). Set in `config.py` as `settings.USE_DEERFLOW`.

| `USE_DEERFLOW` | Execution path |
|---|---|
| `false` | `fallback_engine` — direct LLM calls via Anthropic/OpenAI SDK |
| `true` | `deerflow_adapter` — routes through DeerFlow harness |

Both paths must produce equivalent `AgentResponse` output. When changing orchestration logic, test both paths.

### Pydantic v2

```python
# ✅ ConfigDict
from pydantic import BaseModel, ConfigDict
class MyModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

# ✅ model_validate
obj = MyModel.model_validate(data)

# ✅ field_validator
from pydantic import field_validator
class MyModel(BaseModel):
    @field_validator("field")
    @classmethod
    def check(cls, v: str) -> str:
        return v.strip()
```

## Links

- Root [`CLAUDE.md`](../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
- Module [`README.md`](./README.md) — quick start, architecture, API endpoints
