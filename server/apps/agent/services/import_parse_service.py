"""金融文档持仓解析服务 — 调用 LLM 从文本中提取持仓快照。"""

import contextlib
import json
import logging

logger = logging.getLogger(__name__)

IMPORT_PARSE_PROMPT = """你是一个金融文档解析助手。
从以下文本中提取持仓/资产信息，输出严格 JSON，不输出任何解释文字。

输出格式：
{{
  "source": "机构名称或空字符串",
  "report_date": "YYYY-MM-DD 或 null",
  "items": [
    {{
      "name": "资产名称",
      "asset_type": "financial",
      "category_hint": "股票|基金|债券|存款|理财产品|数字货币|其他",
      "current_value": 数字,
      "currency": "CNY",
      "quantity": 数字或null
    }}
  ]
}}

规则：
- 只提取持仓/资产信息，忽略交易流水、消费记录
- 识别不到任何资产时返回 {{"source": "", "report_date": null, "items": []}}
- current_value 必须是数字，不能是字符串

文档内容：
{text}
"""


async def parse_holdings_from_text(text: str, llm) -> dict:
    """调用 LLM 从文本中提取持仓快照，返回结构化 dict。"""
    prompt = IMPORT_PARSE_PROMPT.format(text=text)

    if not hasattr(llm, "chat"):
        logger.warning("[import_parse] llm has no .chat() method")
        return {"source": "", "report_date": None, "items": []}

    raw = await llm.chat(prompt)

    # 尝试解析 JSON，失败时返回空结果
    with contextlib.suppress(json.JSONDecodeError, ValueError, TypeError):
        # 去除可能的 markdown 代码块包裹
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned
        return json.loads(cleaned)

    logger.warning(f"[import_parse] LLM returned non-JSON: {raw[:200]}")
    return {"source": "", "report_date": None, "items": []}
