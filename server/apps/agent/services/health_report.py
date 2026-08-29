"""家庭资产体检报告生成服务。

流程：
1. 从 backend 拉取聚合数据（overview / allocation / trend / low-usage / daily-cost / liabilities）
2. 脱敏处理
3. 构建结构化 prompt，调用 LLM 生成叙事
4. 返回固定结构的报告 JSON
"""

import logging
from datetime import datetime
from typing import Any, cast

from apps.agent.core.backend_client import BackendClient
from apps.agent.core.desensitize import desensitize_liabilities
from apps.agent.core.llm import LLMClient
from apps.agent.schemas.context import RedactedContext

logger = logging.getLogger(__name__)


async def _async_noop() -> None:
    """No-op async function for health-report's publish_retry_event (no SSE)."""

REPORT_PROMPT_TEMPLATE = """你是一位专业的家庭财务顾问。以下是一个家庭的资产状况数据（已脱敏），请根据数据生成一份结构化的家庭资产体检报告。

## 数据摘要
{data_summary}

## 输出要求
请严格按照以下 JSON 格式输出，不要添加任何额外内容：

{{
  "net_worth_health": {{
    "score": <1-5整数>,
    "narrative": "<150-350字净资产健康状况分析，使用markdown格式：用**加粗**突出关键结论，用换行分段>",
    "suggestions": ["<建议1，15-40字>", "<建议2，15-40字>"]
  }},
  "allocation_analysis": {{
    "score": <1-5整数>,
    "narrative": "<150-350字资产配置分析，使用markdown格式：用**加粗**突出关键结论，用换行分段>",
    "suggestions": ["<建议1，15-40字>", "<建议2，15-40字>", "<建议3，15-40字>"]
  }},
  "liability_pressure": {{
    "score": <1-5整数>,
    "narrative": "<150-350字负债压力分析，使用markdown格式：用**加粗**突出关键结论，用换行分段，无负债时score给5>",
    "suggestions": ["<建议1，15-40字>"]
  }},
  "asset_efficiency": {{
    "score": <1-5整数>,
    "narrative": "<150-350字资产效率分析，使用markdown格式：用**加粗**突出关键结论，用换行分段>",
    "suggestions": ["<建议1，15-40字>", "<建议2，15-40字>"]
  }},
  "overall_score": <20-100整数>,
  "summary": "<100-250字综合总结，使用markdown格式：用**加粗**突出核心问题，用有序列表列出核心建议>"
}}

评分标准：1=很差，2=较差，3=一般，4=良好，5=优秀
overall_score 计算方式（必须严格按此公式）：
  overall_score = round((net_worth_health.score * 0.30 + allocation_analysis.score * 0.25 + liability_pressure.score * 0.25 + asset_efficiency.score * 0.20) * 20)
  示例：各维度均为4分 → (4*0.30 + 4*0.25 + 4*0.25 + 4*0.20) * 20 = 4 * 20 = 80
  示例：各维度均为5分 → 5 * 20 = 100
  overall_score 范围：20（全1分）到 100（全5分），不得输出 0

narrative 格式要求：
- 用 **加粗** 突出关键结论
- 用 \\n\\n 分段（结论段 + 展开段）
- 禁止使用标题（#）和表格
- 使用观察性语言：「观察到」「数据显示」，严禁提供投资建议"""


def _build_data_summary(overview: dict, allocation: dict, trend: dict, low_usage: list, liabilities: list) -> str:
    lines = []

    # Net worth
    net_worth = overview.get("net_worth", 0)
    total_assets = overview.get("total_assets", 0)
    total_liabilities = overview.get("total_liabilities", 0)
    mom_change = overview.get("mom_change_pct", 0)
    lines.append(f"净资产：{net_worth:,.0f}（资产{total_assets:,.0f} - 负债{total_liabilities:,.0f}），月环比{mom_change:+.1f}%")

    # Allocation
    alloc_items = allocation.get("items", [])
    if alloc_items:
        alloc_str = "、".join(
            f"{item.get('category_name', item.get('name', '未知'))}占{item.get('percentage', 0):.1f}%"
            for item in alloc_items[:5]
        )
        lines.append(f"资产配置：{alloc_str}")

    # Trend (last 3 points)
    points = trend.get("points", [])
    if len(points) >= 2:
        first = points[0].get("net_worth", 0)
        last = points[-1].get("net_worth", 0)
        change_pct = ((last - first) / first * 100) if first else 0
        lines.append(f"净资产趋势：近期{change_pct:+.1f}%（共{len(points)}个数据点）")

    # Low usage
    if low_usage:
        lines.append(f"低效资产：{len(low_usage)}项（使用频率低或闲置）")

    # Liabilities
    desensitized_liabilities = desensitize_liabilities(liabilities)
    if desensitized_liabilities:
        total_remaining = sum(li.get("remaining_amount_range_mid", 0) for li in desensitized_liabilities)
        lines.append(f"活跃负债：{len(desensitized_liabilities)}笔，估算总余额约{total_remaining:,.0f}")
    else:
        lines.append("活跃负债：无")

    return "\n".join(lines)


def _compute_data_completeness(overview: dict, allocation: dict, trend: dict) -> float:
    score = 0.0
    if overview.get("total_assets", 0) > 0:
        score += 40
    if allocation.get("items"):
        score += 20
    points = trend.get("points", [])
    if len(points) >= 3:
        score += 20
    elif len(points) >= 1:
        score += 10
    if overview.get("asset_count", 0) >= 3:
        score += 20
    return min(score, 100.0)


async def generate_health_report(
    family_id: str,
    llm: LLMClient,
    ctx: "RedactedContext | None" = None,
) -> dict:
    """生成家庭资产体检报告，返回报告 JSON dict。

    优先使用已脱敏的 ctx（由 Orchestrator 传入），避免重复拉取数据和绕过 PII 脱敏。
    仅当 ctx 为 None 时（直接调用 legacy 路径）才自行拉取数据。
    """
    if ctx is not None:
        overview = ctx.dashboard_overview
        allocation = ctx.dashboard_allocation
        trend = ctx.dashboard_trend
        low_usage = ctx.low_usage_assets
        liabilities = ctx.liabilities
    else:
        client = BackendClient(family_id=family_id)
        try:
            overview = await client.get_dashboard_overview()
            allocation = await client.get_dashboard_allocation()
            trend = await client.get_dashboard_trend(period="year")
            low_usage = await client.get_dashboard_low_usage()
            liabilities = await client.get_liabilities()
        except Exception as e:
            logger.error(f"[health_report] 拉取数据失败 family={family_id}: {e}")
            raise

    data_summary = _build_data_summary(overview, allocation, trend, low_usage, liabilities)
    data_completeness = _compute_data_completeness(overview, allocation, trend)

    prompt = REPORT_PROMPT_TEMPLATE.format(data_summary=data_summary)

    try:
        # Use complete_json() for response_format enforcement (OpenAI: json_object)
        raw = await llm.complete_json(prompt, max_tokens=3000)
        # parse_report_json handles fenced + bare JSON with json_repair tolerance
        from apps.agent.services.runtime.asset_report_middleware import (
            parse_report_json,
        )

        report_data = parse_report_json(raw)
        if report_data is None:
            raise ValueError("LLM 响应无法解析为 JSON")
    except Exception as e:
        logger.error(f"[health_report] LLM 解析失败 family={family_id}: {e}")
        raise ValueError(f"LLM 响应解析失败: {e}") from e

    # Validate→repair cycle (shared infrastructure)
    from apps.agent.services.runtime.llm_json_repair import (
        _HEALTH_REPORT_REPAIR_PROMPT,
        _repair_health_report_via_llm,
        extract_json_via_llm,
        run_json_repair_loop,
        validate_health_report_json,
    )

    # Build a provider dict from the LLMClient for the repair functions.
    # Must include actual credentials — _llm_repair_json creates a new client.
    _provider = {
        "ai_provider": llm.provider,
        "api_key": llm._api_key,
        "ai_model_id": llm.model_id,
        "ai_base_url": llm._base_url,
    }

    async def _health_repair_fn(text: str, errors: list[str]):
        return await _repair_health_report_via_llm(text, errors, _provider)

    report_data, repair_count = await run_json_repair_loop(
        report_data,
        raw,
        validator=validate_health_report_json,
        repair_fn=_health_repair_fn,
        publish_retry_event=lambda _attempt: _async_noop(),
        app_name="health_report",
        max_retries=2,
        budget_seconds=120,
    )

    # Final fallback: standalone LLM extraction
    if report_data is not None and validate_health_report_json(report_data):
        fallback = await extract_json_via_llm(
            raw, _HEALTH_REPORT_REPAIR_PROMPT, _provider,
        )
        if fallback is not None and not validate_health_report_json(fallback):
            report_data = fallback

    if report_data is None or validate_health_report_json(report_data):
        errors = validate_health_report_json(report_data) if report_data else ["无法解析报告 JSON"]
        logger.error(
            "[health_report] validation failed after %d retries + fallback "
            "family=%s errors=%s",
            repair_count,
            family_id,
            errors[:3],
        )
        raise ValueError(f"体检报告校验失败: {'; '.join(errors[:3])}")

    # Clamp overall_score to valid range regardless of LLM compliance with the prompt formula.
    if "overall_score" in report_data:
        try:
            report_data["overall_score"] = max(20, min(100, int(float(str(report_data["overall_score"])))))
        except (TypeError, ValueError):
            logger.warning(f"[health_report] overall_score 无法转换为整数，使用默认值 60: {report_data['overall_score']!r}")
            report_data["overall_score"] = 60

    report_data["generated_at"] = datetime.utcnow().isoformat()
    report_data["data_completeness_score"] = data_completeness

    # Note: Raw PII data intentionally NOT attached to response per security invariant.
    # Frontend should fetch aggregate data separately via backend APIs if needed.

    return cast("dict[str, Any]", report_data)
