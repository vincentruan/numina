"""PII 脱敏服务：统一入口，结构化数据 + 自由文本双路径。"""

import re

from apps.agent.core.desensitize import (
    desensitize_assets,
    desensitize_liabilities,
    desensitize_members,
)
from apps.agent.schemas.context import FamilyContext, RedactedContext

# 自由文本 PII 正则模式
_PATTERNS = [
    (re.compile(r'\d{17}[\dXx]'), "身份证号"),
    (re.compile(r'1[3-9]\d{9}'), "手机号"),
    (re.compile(r'\d{16,19}'), "银行卡号"),
    (re.compile(r'[\u7701\u5e02\u533a\u8def\u53f7][\u4e00-\u9fff\d]{2,}[\u7701\u5e02\u533a\u8def\u53f7]'), "地址"),
]
_REDACTED = "[已脱敏]"


def _redact_free_text(text: str) -> tuple[str, list[str]]:
    """对自由文本应用正则脱敏，返回（脱敏后文本, 脱敏日志）。"""
    log: list[str] = []
    for pattern, label in _PATTERNS:
        if pattern.search(text):
            text = pattern.sub(_REDACTED, text)
            log.append(f"free_text:{label}")
    return text, log


class PIIRedactor:
    """统一 PII 脱敏入口。"""

    def redact_text(self, text: str) -> tuple[str, list[str]]:
        """对任意文本应用正则脱敏，返回（脱敏后文本, 脱敏日志）。供审计日志等外部调用使用。"""
        return _redact_free_text(text)

    def redact(self, ctx: FamilyContext) -> RedactedContext:
        """脱敏 FamilyContext，返回 RedactedContext。"""
        log: list[str] = []

        # 结构化数据脱敏
        redacted_assets = desensitize_assets(ctx.assets)
        if ctx.assets:
            log.append("assets:name")

        redacted_liabilities = desensitize_liabilities(ctx.liabilities)
        if ctx.liabilities:
            log.append("liabilities:name,institution,exact_amounts")

        redacted_members = desensitize_members(ctx.members)
        if ctx.members:
            log.append("members:name")

        # 自由文本脱敏
        redacted_free_text: str | None = None
        if ctx.free_text is not None:
            redacted_free_text, text_log = _redact_free_text(ctx.free_text)
            log.extend(text_log)

        return RedactedContext(
            family_id=ctx.family_id,
            assets=redacted_assets,
            liabilities=redacted_liabilities,
            members=redacted_members,
            dashboard_overview=ctx.dashboard_overview,
            dashboard_allocation=ctx.dashboard_allocation,
            dashboard_trend=ctx.dashboard_trend,
            low_usage_assets=ctx.low_usage_assets,
            free_text=redacted_free_text,
            redaction_log=log,
        )


pii_redactor = PIIRedactor()
