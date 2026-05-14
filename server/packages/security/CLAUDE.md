# security/CLAUDE.md

Module-specific guidance for the auth utilities package.
See root [`CLAUDE.md`](../../../CLAUDE.md) for behavioral guidelines and cross-cutting conventions.

## Quality Commands

Run all commands from `server/`:

```bash
uv run ruff check packages/security/        # lint
uv run ruff check packages/security/ --fix  # lint + auto-fix
uv run ruff format packages/security/       # format (only files you touch)
uv run mypy packages/security/ --explicit-package-bases  # type check
uv run pytest packages/security/ -v         # run tests
```

## Tooling

- **uv:** package manager. Use `uv add`/`uv remove`. Never `pip install`.
- **ruff:** lint + format. Config in `pyproject.toml` under `[tool.ruff]`.
- **mypy:** type checker. Requires `--explicit-package-bases` to avoid namespace collision with other `packages/` directories.

## Key Invariants

1. **Import direction** — `packages/security` must never import from `apps/`. Dependency flow is one-way: `apps/` → `packages/`. Violating this creates circular imports.
2. **JTI revocation interface** — `revoke_jti`, `revoke_all_user_tokens`, and `cleanup_expired_revoked_tokens` are the only approved functions for JWT revocation. Never query the `RevokedToken` model directly from app code, and never call the private `_is_jti_revoked` or `_is_token_revoked_for_user` functions — these are internal implementation details.
3. **Auth contexts are separate** — `frontend_auth` and `service_auth` are distinct auth subsystems. Do not mix their middleware, dependencies, or token validation logic.

## Don't Do

- **Don't import from `apps/`** — import direction rule: `packages/` must not import sibling `apps/`. Use other `packages/` for shared logic.
- **Don't query `RevokedToken` directly** — use the public revocation functions in `revoke_jti.py`.
- **Don't call `_is_jti_revoked` or `_is_token_revoked_for_user`** — these are private helpers; the public interface is sufficient.
- **Don't mix `frontend_auth` and `service_auth`** — they serve different callers with different token formats and trust models.
- **Don't run commands from the package directory** — quality commands must be invoked from `server/`, not from `packages/security/`.

## Links

- Root [`CLAUDE.md`](../../../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
- Module [`README.md`](./README.md) — purpose statement, exports table
