"""智能资产录入助手 — 基于资产名称和类别，AI 建议字段默认值。"""

import json
import logging

from core.llm import LLMClient

logger = logging.getLogger(__name__)

SUGGEST_PROMPT_TEMPLATE = """你是一位资产管理专家。用户正在录入一项资产，请根据资产名称和类别，推断合理的字段默认值。

资产名称：{name}
资产类别：{category}（{asset_type}）

请严格按照以下 JSON 格式输出，不要添加任何额外内容：

{{
  "expected_lifespan_years": <整数或null，预期使用年限，无法判断时为null>,
  "annual_maintenance_cost_hint": "<字符串，年维护费用估算说明，如'约500-1000元/年'，无需维护时为'无'>"，
  "usage_frequency": "<daily|weekly|monthly|rarely|idle，最可能的使用频率>",
  "suggested_tags": ["<标签1>", "<标签2>"],
  "notes_hint": "<可选备注提示，如保修信息、注意事项等，无则为空字符串>"
}}

注意：
- expected_lifespan_years 仅对实物资产有意义，金融资产返回 null
- usage_frequency 仅对实物资产有意义，金融资产返回 "daily"
- suggested_tags 最多 3 个，简短中文标签
- 所有字段必须存在，不可省略"""


async def suggest_asset_fields(name: str, category: str, asset_type: str, llm: LLMClient) -> dict:
    """根据资产名称和类别，返回 AI 建议的字段值。"""
    prompt = SUGGEST_PROMPT_TEMPLATE.format(
        name=name,
        category=category,
        asset_type="实物资产" if asset_type == "physical" else "金融资产",
    )

    try:
        raw = await llm.complete(prompt, max_tokens=300)
        start = raw.find("{")
        end = raw.rfind("}") + 1
        result = json.loads(raw[start:end])
    except Exception as e:
        logger.warning(f"[asset_suggest] LLM 解析失败: {e}, raw={raw!r}")
        # Return safe defaults on failure
        result = {
            "expected_lifespan_years": None,
            "annual_maintenance_cost_hint": "",
            "usage_frequency": "daily",
            "suggested_tags": [],
            "notes_hint": "",
        }

    return result
