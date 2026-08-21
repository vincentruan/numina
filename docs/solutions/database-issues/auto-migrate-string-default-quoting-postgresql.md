---
title: "SQLAlchemy auto-migrate emits unquoted string defaults for VARCHAR columns in PostgreSQL"
date: "2026-08-19"
category: database-issues
module: server/apps/backend
problem_type: database_issue
component: database
severity: high
symptoms:
  - "Adding a VARCHAR column with server_default='equal_payment' fails with PostgreSQL FeatureNotSupported error"
  - "DDL emits DEFAULT equal_payment (unquoted) instead of DEFAULT 'equal_payment'"
  - "PostgreSQL interprets the unquoted string as a column reference, not a literal value"
root_cause: missing_validation
resolution_type: code_fix
tags:
  - sqlalchemy
  - postgresql
  - auto-migrate
  - server-default
  - varchar
  - ddl
  - quoting
---

# SQLAlchemy Auto-Migrate Emits Unquoted String Defaults for VARCHAR Columns

## Problem

Numina's auto-migrate system (`db_migrate.py`) compares SQLAlchemy models against the live database schema and adds missing columns. When a model defines `Column(String, server_default='equal_payment')`, the auto-migrate generated DDL with `DEFAULT equal_payment` (unquoted). PostgreSQL interprets `equal_payment` as a column reference, not a string literal, and raises `FeatureNotSupported: cannot use column reference in DEFAULT expression`.

## Symptoms

- Adding a new `repayment_method` column (VARCHAR) with `server_default='equal_payment'` crashes on startup with a PostgreSQL error.
- The error only occurs in PostgreSQL — SQLite accepts the unquoted form (it's more permissive with DEFAULT expressions).
- Integer and boolean defaults (e.g., `server_default='0'`, `server_default='true'`) work correctly because they're valid SQL expressions.

## What Didn't Work

- Changing the `server_default` value to include quotes (`server_default="'equal_payment'"`) — the auto-migrate double-quoted it, producing `DEFAULT ''equal_payment''`.
- Using `text("'equal_payment'")` — the auto-migrate detected it as a `TextClause` and handled it differently, but this is an ORM-level workaround that doesn't fix the root cause.

## Solution

The root cause was in `get_expected_columns_from_model()`: all string `server_default` args were classified as `default_type='sql_expr'` (SQL expression). For string-typed columns (VARCHAR, TEXT, CHAR), these are literal values that must be passed as `default_type='scalar'` so the migration library properly quotes them.

```python
# In get_expected_columns_from_model():
if isinstance(arg, str):
    # For string-typed columns, a plain string server_default is a
    # literal value that must be quoted in DDL.
    col_type_upper = str(column.type).upper()
    _is_string_col = any(
        t in col_type_upper
        for t in ("VARCHAR", "TEXT", "CHAR", "STRING")
    )
    if _is_string_col:
        default_val = arg
        default_type = "scalar"    # → DEFAULT 'equal_payment'
    else:
        default_val = arg
        default_type = "sql_expr"  # → DEFAULT true / DEFAULT 0
```

## Why This Works

The `default_type='scalar'` path in the migration library wraps the value in quotes during DDL generation, producing `DEFAULT 'equal_payment'` (a valid string literal). The `default_type='sql_expr'` path emits the value verbatim, which is correct for expressions like `true`, `0`, or `now()` — but wrong for string literals.

The fix distinguishes string-typed columns (where the default is a literal value) from non-string columns (where the default is a SQL expression).

## Prevention

- **Rule:** In any auto-migration or schema diff tool, always classify `server_default` values by column type. String columns get scalar (quoted) defaults; non-string columns get SQL expression defaults.
- **Test:** Add a test case that creates a VARCHAR column with a string `server_default` and verifies the DDL includes quotes.
- **Cross-DB**: This bug only manifests in PostgreSQL (strict about DEFAULT expressions). SQLite silently accepts the unquoted form. Test against PostgreSQL to catch it.

## Related Issues

- Found by: `production-ops-patrol` skill (anomaly detection fingerprint, identified the FeatureNotSupported error pattern in production logs)
- Related: `docs/solutions/integration-issues/production-deployment-config-mismatches.md` (production deployment issues)
