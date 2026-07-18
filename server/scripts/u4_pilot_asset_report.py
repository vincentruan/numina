"""U4 P0 pilot: verify typed_stream_dispatch can run a non-chat skill end-to-end.

Plan (2026-07-17-002) U4 P0 prerequisite (adversarial Finding校正):
  KTD-7 "报告 skill 同样能跑" was an INFERENCE — typed_stream_dispatch has
  never run a non-chat skill (worker.py hardcodes capability="chat"). Before
  committing U4, this pilot turns the inference into evidence:

  1. Feasibility (1 run): a non-chat skill runs end-to-end via
     typed_stream_dispatch, yielding messages/values/custom/end frames with
     tool_result flowing through worker.py:270-279's tool_call handling.
  2. F1 baseline (≥20 runs): single-pass success rate ≥80%.
     success = write_file called AND read_file called AND final JSON parses.
     <80% → fall back to two-skill NDJSON orchestration (do NOT commit U4).

USAGE (run from server/, requires real family AI config + data):

  uv run python -m scripts.u4_pilot_asset_report --family-id <FAMILY_ID> \\
      --runs 20 --skill asset-report

  # Minimal 1-run feasibility probe:
  uv run python -m scripts.u4_pilot_asset_report --family-id <FAMILY_ID> \\
      --runs 1 --skill asset-report

This script does NOT start a dev server — it calls the adapter directly,
mirroring worker.py's setup (BackendClient.get_family_ai_config +
get_enabled_mcp_servers → create_family_adapter → typed_stream_dispatch).

Exit code 0 = feasibility passed (for --runs 1) or ≥80% success (for --runs≥20).
Exit code 1 = feasibility failed / success rate below threshold → do NOT commit U4.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from typing import Any

# Ensure server/ is on the path when run as a module.
sys.path.insert(0, ".")

from apps.agent.app.config import settings  # noqa: E402
from apps.agent.core.backend_client import BackendClient  # noqa: E402
from apps.agent.schemas.context import FamilyContext  # noqa: E402
from apps.agent.services.deerflow_adapter.active_skill_context import (
    set_active_skill,  # noqa: E402
)
from apps.agent.services.deerflow_adapter.adapter import (
    create_family_adapter,  # noqa: E402
)
from apps.agent.services.pii_redactor import pii_redactor  # noqa: E402
from apps.agent.services.runtime.sandbox_provider import (
    set_family_sandbox_context,  # noqa: E402
)

_SYNTHETIC_TRIGGER = "/asset-report 生成家庭资产报告"


async def _build_mcp_servers(client: BackendClient, family_id: str, user_id: str | None) -> list[dict[str, Any]]:
    """Mirror worker.py's MCP server setup (lines ~133-153)."""
    mcp_servers = await client.get_enabled_mcp_servers()
    for srv in mcp_servers:
        if srv.get("name") == "Numina Backend MCP":
            expected_prefix = settings.BACKEND_BASE_URL.rstrip("/")
            actual_url = (srv.get("url") or "").rstrip("/")
            if not actual_url.startswith(expected_prefix):
                srv["url"] = expected_prefix + "/api/v1/internal/mcp/" + family_id + "/sse"
            mcp_headers: dict[str, str] = {
                "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                "X-Family-Id": family_id,
            }
            if user_id:
                mcp_headers["X-Caller-User-Id"] = user_id
            srv["headers"] = mcp_headers
    return mcp_servers


async def _run_once(
    *,
    family_id: str,
    user_id: str | None,
    ai_config: dict[str, Any],
    mcp_servers: list[dict[str, Any]],
    skill_name: str,
    thread_id: str,
) -> dict[str, Any]:
    """Run one typed_stream_dispatch and collect evidence."""
    set_family_sandbox_context(family_id)
    _token = set_active_skill(skill_name)

    provider = next(
        (p for p in ai_config.get("providers", []) if p.get("is_active")),
        ai_config.get("providers", [{}])[0] if ai_config.get("providers") else {},
    )

    context = FamilyContext(family_id=family_id, free_text=_SYNTHETIC_TRIGGER)
    redacted = pii_redactor.redact(context)

    adapter = create_family_adapter(
        family_id,
        provider,
        timeout_seconds=240,
        subagent_enabled=False,
        plan_mode=True,  # asset-report benefits from planning (3 steps)
        mcp_servers=mcp_servers,
    )

    saw_write_file = False
    saw_read_file = False
    ai_text_parts: list[str] = []
    custom_events: list[dict] = []
    ended = False
    error: str | None = None

    try:
        async def _drive():
            nonlocal saw_write_file, saw_read_file, ended, error
            async for sse_type, data in adapter.typed_stream_dispatch(
                skill_name=skill_name,
                context=redacted,
                thread_id=thread_id,
                enable_thinking=False,  # Qwen3: avoid empty content
            ):
                if sse_type == "end":
                    ended = True
                    break
                if sse_type == "error":
                    error = str(data)
                    break
                if sse_type == "messages" and isinstance(data, dict) and data.get("type") == "ai":
                    content = data.get("content")
                    if content:
                        ai_text_parts.append(content)
                    for tc in _extract_tool_calls(data):
                        name = tc.get("name", "")
                        if "write_file" in name:
                            saw_write_file = True
                        if "read_file" in name:
                            saw_read_file = True
                if sse_type == "custom" and isinstance(data, dict):
                    custom_events.append(data)

        await _drive()
    finally:
        try:
            from apps.agent.services.deerflow_adapter.active_skill_context import (
                reset_active_skill,
            )
            reset_active_skill(_token)
        except Exception:
            pass

    full_text = "".join(ai_text_parts)
    parsed_json = _try_parse_json(full_text)

    return {
        "thread_id": thread_id,
        "ended": ended,
        "error": error,
        "saw_write_file": saw_write_file,
        "saw_read_file": saw_read_file,
        "saw_skill_load": _saw_skill_load(custom_events, ai_text_parts, skill_name),
        "json_parsed": parsed_json is not None,
        "ai_text_len": len(full_text),
        "custom_event_count": len(custom_events),
    }


def _extract_tool_calls(data: dict) -> list[dict]:
    tcs = data.get("tool_calls") or []
    out = []
    for tc in tcs:
        if isinstance(tc, dict):
            out.append(tc)
    return out


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _try_parse_json(text: str) -> dict | None:
    """Try json_repair-style parse of fenced or bare JSON in the AI text."""
    import json_repair

    candidates: list[str] = []
    for m in _JSON_FENCE_RE.finditer(text):
        candidates.append(m.group(1))
    candidates.append(text)

    for cand in candidates:
        try:
            parsed = json_repair.repair_json(cand, return_objects=True)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return None


def _saw_skill_load(custom_events: list[dict], ai_text_parts: list[str], skill_name: str) -> bool:
    """F1 Finding 14: read_file on asset-report/SKILL.md appears in the stream."""
    blob = json.dumps(custom_events) + "".join(ai_text_parts)
    return f"{skill_name}/SKILL.md" in blob or ("SKILL.md" in blob and skill_name in blob)


def _is_success(result: dict[str, Any]) -> bool:
    return (
        result["ended"]
        and result["saw_write_file"]
        and result["saw_read_file"]
        and result["json_parsed"]
        and result["error"] is None
    )


async def _main_async(args: argparse.Namespace) -> int:
    client = BackendClient(family_id=args.family_id)
    ai_config = await client.get_family_ai_config()
    if not ai_config.get("providers"):
        print("FAIL: family has no AI providers configured", file=sys.stderr)
        return 1
    user_id = args.user_id
    mcp_servers = await _build_mcp_servers(client, args.family_id, user_id)

    print(f"U4 pilot: skill={args.skill} family={args.family_id} runs={args.runs}")
    print(f"  provider={ai_config['providers'][0].get('provider')}")

    results = []
    for i in range(args.runs):
        thread_id = f"pilot-{args.skill}-{int(time.time())}-{i}"
        try:
            r = await _run_once(
                family_id=args.family_id,
                user_id=user_id,
                ai_config=ai_config,
                mcp_servers=mcp_servers,
                skill_name=args.skill,
                thread_id=thread_id,
            )
        except Exception as exc:
            r = {
                "thread_id": thread_id,
                "ended": False,
                "error": f"{type(exc).__name__}: {exc}",
                "saw_write_file": False,
                "saw_read_file": False,
                "saw_skill_load": False,
                "json_parsed": False,
                "ai_text_len": 0,
                "custom_event_count": 0,
            }
        results.append(r)
        ok = _is_success(r)
        print(
            f"  run {i + 1}/{args.runs}: {'OK' if ok else 'FAIL'} "
            f"wf={r['saw_write_file']} rf={r['saw_read_file']} "
            f"json={r['json_parsed']} skill_load={r['saw_skill_load']} "
            f"err={r['error']}"
        )

    success = sum(1 for r in results if _is_success(r))
    rate = success / len(results) if results else 0.0
    print(f"\nResult: {success}/{len(results)} success ({rate:.0%})")

    if args.runs == 1:
        # Feasibility mode: just need it to end + show tool activity.
        feasible = results[0]["ended"] and (results[0]["saw_write_file"] or results[0]["saw_read_file"])
        print("Feasibility: " + ("PASS" if feasible else "FAIL"))
        return 0 if feasible else 1

    threshold = 0.80
    print(f"Threshold: ≥{threshold:.0%} single-pass success to commit U4")
    if rate >= threshold:
        print("PASS: commit U4 with single-agent-run 3-step pipeline")
        return 0
    print("FAIL: rate < 80% → fall back to two-skill NDJSON orchestration, do NOT commit U4")
    return 1


def main() -> int:
    p = argparse.ArgumentParser(description="U4 P0 pilot for asset-report pipeline")
    p.add_argument("--family-id", required=True, help="Family ID to run against")
    p.add_argument("--user-id", default=None, help="Optional user ID for MCP headers")
    p.add_argument("--runs", type=int, default=20, help="Number of runs (1 = feasibility probe)")
    p.add_argument("--skill", default="asset-report", help="Skill name to drive")
    args = p.parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    sys.exit(main())
