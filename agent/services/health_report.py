"""家庭资产体检报告生成服务。

流程：
1. 从 backend 拉取聚合数据（overview / allocation / trend / low-usage / daily-cost / liabilities）
2. 脱敏处理
3. 构建结构化 prompt，调用 LLM 生成叙事
4. 返回固定结构的报告 JSON
"""

import json
import logging
import re
from datetime import datetime

from core.backend_client import BackendClient
from core.desensitize import desensitize_liabilities
from core.llm import LLMClient
from schemas.context import RedactedContext

logger = logging.getLogger(__name__)

REPORT_PROMPT_TEMPLATE = """你是一位专业的家庭财务顾问。以下是一个家庭的资产状况数据（已脱敏），请根据数据生成一份结构化的家庭资产体检报告。

## 数据摘要
{data_summary}

## 输出要求
请严格按照以下 JSON 格式输出，不要添加任何额外内容：

{{
  "net_worth_health": {{
    "score": <1-5整数>,
    "narrative": "<50-100字的净资产健康状况分析>"
  }},
  "allocation_analysis": {{
    "score": <1-5整数>,
    "narrative": "<50-100字的资产配置分析>"
  }},
  "liability_pressure": {{
    "score": <1-5整数>,
    "narrative": "<50-100字的负债压力分析，无负债时score给5>"
  }},
  "asset_efficiency": {{
    "score": <1-5整数>,
    "narrative": "<50-100字的资产效率分析>"
  }},
  "overall_score": <0-100整数>,
  "summary": "<100-150字的综合总结和核心建议>"
}}

评分标准：1=很差，2=较差，3=一般，4=良好，5=优秀
overall_score = 各维度加权平均（净资产30% + 配置25% + 负债25% + 效率20%）* 20"""


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
        raw = await llm.complete(prompt, max_tokens=800)
        # Strip markdown code fences if present, then fall back to brace extraction
        fence_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
        if fence_match:
            json_str = fence_match.group(1)
        else:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            json_str = raw[start:end]
        report_data = json.loads(json_str)
    except Exception as e:
        logger.error(f"[health_report] LLM 解析失败 family={family_id}: {e}")
        raise ValueError(f"LLM 响应解析失败: {e}") from e

    report_data["generated_at"] = datetime.utcnow().isoformat()
    report_data["data_completeness_score"] = data_completeness

    # Note: Raw PII data intentionally NOT attached to response per security invariant.
    # Frontend should fetch aggregate data separately via backend APIs if needed.

    return report_data
