#!/usr/bin/env python3
"""
scripts/patch-langgraph-runtime.py

Applies a compatibility shim to langgraph/runtime.py in the active venv.

Required because langgraph 1.0.9 references ExecutionInfo and ServerInfo in
tool_node.py, but these symbols are not exported by langgraph-runtime-inmem
0.26.0. The symbols are only used as type annotations, so stub classes suffice.

Run after: uv add --editable ./vendor/deerflow-harness
"""

import importlib.util
import sys

STUB = '''

# Compatibility stubs for langgraph 1.0.9 + langgraph-runtime-inmem 0.26.0
# ExecutionInfo and ServerInfo are referenced in tool_node.py but not yet
# exported by langgraph-runtime-inmem at this version combination.
class ExecutionInfo:
    """Stub for type annotation compatibility."""
    pass


class ServerInfo:
    """Stub for type annotation compatibility."""
    pass
'''

spec = importlib.util.find_spec("langgraph.runtime")
if spec is None:
    print("ERROR: langgraph.runtime not found — is langgraph installed?")
    sys.exit(1)

runtime_path = spec.origin
assert runtime_path, "Could not locate langgraph/runtime.py"

with open(runtime_path) as f:
    content = f.read()

if "class ExecutionInfo" in content:
    print(f"Already patched: {runtime_path}")
    sys.exit(0)

with open(runtime_path, "a") as f:
    f.write(STUB)

print(f"Patched: {runtime_path}")
print("ExecutionInfo and ServerInfo stubs added.")
