#!/usr/bin/env python3
"""
fingerprint.py — Exception fingerprint computation.

Normalizes a Python exception/traceback into a stable fingerprint (SHA256)
so that the same bug producing the same stack trace gets the same fingerprint,
regardless of variable values, timestamps, or request IDs.

Normalization strategy:
1. Extract ExceptionType from the last line
2. Extract the top frame's file (basename only) + line number
3. Extract the exception message's first line (strip variable parts)
4. Combine: "ExceptionType:basename.py:lineno:normalized_message"
5. SHA256 hash → fingerprint

Usage:
    # From a raw traceback string:
    python fingerprint.py --traceback '<traceback text>'

    # From explicit components:
    python fingerprint.py --input 'ValueError:models.py:42:invalid literal'

    # From a log line containing a traceback block (JSON stdin):
    echo '{"traceback": "..."}' | python fingerprint.py --stdin

Output: JSON with 'fingerprint', 'exception_type', 'normalized_key'.
"""

import argparse
import hashlib
import json
import os
import re
import sys


def normalize_traceback(traceback_text: str) -> dict:
    """Extract normalized components from a traceback string.

    Returns dict with:
      - exception_type: str
      - top_file: str (basename)
      - top_line: int
      - message: str (first line of exception message, stripped)
      - normalized_key: str (fingerprint input)
      - fingerprint: str (SHA256 hex)
    """
    lines = traceback_text.strip().split("\n")
    if not lines:
        return {
            "exception_type": "Unknown",
            "top_file": "unknown",
            "top_line": 0,
            "message": "",
            "normalized_key": "Unknown:unknown:0:",
            "fingerprint": _hash("Unknown:unknown:0:"),
        }

    # Find exception type — last non-empty line usually contains "ExceptionType: message"
    exception_line = ""
    for line in reversed(lines):
        line = line.strip()
        if line and not line.startswith("File ") and not line.startswith("Traceback"):
            exception_line = line
            break

    # Parse "ExceptionType: message"
    exc_match = re.match(r'^([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|Warning|Fault|Interrupt|Exit)?)\s*:\s*(.*)', exception_line)
    if exc_match:
        exception_type = exc_match.group(1).split(".")[-1]  # last component
        message = exc_match.group(2).strip()
    else:
        # Try without colon — e.g., "KeyboardInterrupt"
        exc_match2 = re.match(r'^([A-Za-z_][A-Za-z0-9_.]*)', exception_line)
        exception_type = exc_match2.group(1).split(".")[-1] if exc_match2 else "Unknown"
        message = exception_line

    # Normalize message: strip numbers, IDs, UUIDs, timestamps, paths
    normalized_msg = re.sub(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', '<UUID>', message)
    normalized_msg = re.sub(r'\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', '<TIMESTAMP>', normalized_msg)
    normalized_msg = re.sub(r'\b\d+\b', '<N>', normalized_msg)
    normalized_msg = re.sub(r'/[^\s]+', '<PATH>', normalized_msg)
    # Keep only first 100 chars
    normalized_msg = normalized_msg[:100]

    # Find top frame — first "File ..." line after "Traceback"
    top_file = "unknown"
    top_line = 0
    for line in lines:
        file_match = re.match(r'\s*File "([^"]+)", line (\d+)', line)
        if file_match:
            filepath = file_match.group(1)
            # Skip standard library / framework frames — prefer app code
            top_file = os.path.basename(filepath)
            top_line = int(file_match.group(2))

    # Prefer deepest app-specific frame (closest to the error)
    for line in reversed(lines):
        file_match = re.match(r'\s*File "([^"]+)", line (\d+)', line)
        if file_match:
            filepath = file_match.group(1)
            if any(p in filepath for p in ["apps/", "packages/", "/app/"]):
                top_file = os.path.basename(filepath)
                top_line = int(file_match.group(2))
                break

    normalized_key = f"{exception_type}:{top_file}:{top_line}:{normalized_msg}"
    fingerprint = _hash(normalized_key)

    return {
        "exception_type": exception_type,
        "top_file": top_file,
        "top_line": top_line,
        "message": message[:200],
        "normalized_key": normalized_key,
        "fingerprint": fingerprint,
    }


def _hash(key: str) -> str:
    """SHA256 hash of the normalized key."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def main():
    parser = argparse.ArgumentParser(description="Exception fingerprint computation")
    parser.add_argument("--traceback", type=str, help="Raw traceback text")
    parser.add_argument("--input", type=str, help="Explicit normalized key (ExceptionType:file:line:msg)")
    parser.add_argument("--stdin", action="store_true", help="Read JSON from stdin with 'traceback' field")
    args = parser.parse_args()

    if args.input:
        fingerprint = _hash(args.input)
        result = {
            "normalized_key": args.input,
            "fingerprint": fingerprint,
        }
    elif args.stdin:
        data = json.load(sys.stdin)
        traceback_text = data.get("traceback", "")
        result = normalize_traceback(traceback_text)
    elif args.traceback:
        result = normalize_traceback(args.traceback)
    else:
        print("ERROR: provide --traceback, --input, or --stdin", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
