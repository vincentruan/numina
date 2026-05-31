#!/usr/bin/env python3
"""
scripts/patch-deerflow-thread-data.py

Fixes a bug in deerflow ThreadDataMiddleware.before_agent where
runtime.context.get("run_id") is called without None guard.

The bug: Line 83 defines `context = runtime.context or {}` but line 110
still uses `runtime.context.get("run_id")` directly, causing AttributeError
when runtime.context is None.

Fix: Replace `runtime.context.get("run_id")` with `context.get("run_id")`
to use the already-defined fallback variable.

Run after: uv sync --frozen --no-dev --extra agent
"""

import importlib.util
import sys

PATCH_MARKER = "# NUMINA_PATCH: thread_data_middleware_context_fix"

spec = importlib.util.find_spec("deerflow.agents.middlewares.thread_data_middleware")
if spec is None:
    print("ERROR: deerflow.agents.middlewares.thread_data_middleware not found")
    sys.exit(1)

middleware_path = spec.origin
assert middleware_path, "Could not locate thread_data_middleware.py"

with open(middleware_path) as f:
    content = f.read()

if PATCH_MARKER in content:
    print(f"Already patched: {middleware_path}")
    sys.exit(0)

# Apply the fix: replace runtime.context.get("run_id") with context.get("run_id")
# on line 110 (within before_agent method)
original_line = '"run_id": runtime.context.get("run_id"),'
fixed_line = '"run_id": context.get("run_id"),'

if original_line not in content:
    print(f"WARNING: Expected pattern not found in {middleware_path}")
    print("The deerflow version may have changed. Manual inspection required.")
    sys.exit(1)

# Insert patch marker as a comment before the fixed line
content = content.replace(
    original_line,
    f'{PATCH_MARKER}\n                "run_id": context.get("run_id"),',
)

with open(middleware_path, "w") as f:
    f.write(content)

print(f"Patched: {middleware_path}")
print("Fixed ThreadDataMiddleware.before_agent: runtime.context.get -> context.get")