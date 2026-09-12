"""PII 脱敏服务：统一入口，结构化数据 + 自由文本双路径。"""

import re

from apps.agent.core.desensitize import (
    desensitize_assets,
    desensitize_liabilities,
    desensitize_members,
)
from apps.agent.schemas.context import FamilyContext, RedactedContext

# 自由文本 PII 正则模式
# All digit patterns use negative lookbehind/lookahead for digits (?<!\d) / (?!\d)
# to avoid matching substrings of longer numeric sequences like snowflake IDs (18-digit).
_PATTERNS = [
    # 18 chars (17 digits + digit/X), not part of a longer digit sequence
    (re.compile(r'(?<!\d)\d{17}[\dXx](?!\d)'), "身份证号"),
    # 11 digits starting with 1[3-9], standalone
    (re.compile(r'(?<!\d)1[3-9]\d{9}(?!\d)'), "手机号"),
    # Chinese address (no digit boundary needed)
    (re.compile(r'[省市区路号][一-鿿\d]{2,}[省市区路号]'), "地址"),
]
_REDACTED = "[已脱敏]"


def _luhn_check(number: str) -> bool:
    """Luhn algorithm — validates credit card numbers.

    Returns True when the number is a plausible card number.
    Snowflake IDs (18-digit) almost never pass Luhn, so this
    distinguishes bank cards from internal entity IDs.
    """
    digits = [int(d) for d in number]
    odd = digits[-1::-2]
    even = digits[-2::-2]
    total = sum(odd)
    for d in even:
        d2 = d * 2
        total += d2 - 9 if d2 > 9 else d2
    return total % 10 == 0


def _redact_bank_cards(text: str) -> tuple[str, list[str]]:
    """Redact bank card numbers (16-19 digits passing Luhn check).

    Snowflake IDs (18-digit) are preserved — they don't pass Luhn.
    Boundary assertions prevent matching substrings of longer numbers.
    """
    log: list[str] = []
    pattern = re.compile(r'(?<!\d)\d{16,19}(?!\d)')

    def _replace_if_card(match: re.Match) -> str:
        num = match.group()
        if _luhn_check(num):
            log.append("free_text:银行卡号")
            return _REDACTED
        return num  # snowflake ID or other numeric — keep

    text = pattern.sub(_replace_if_card, text)
    return text, log


def _redact_free_text(text: str) -> tuple[str, list[str]]:
    """对自由文本应用正则脱敏，返回（脱敏后文本, 脱敏日志）。"""
    log: list[str] = []
    for pattern, label in _PATTERNS:
        if pattern.search(text):
            text = pattern.sub(_REDACTED, text)
            log.append(f"free_text:{label}")
    # Bank card redaction uses Luhn check to avoid redacting snowflake IDs
    text, card_log = _redact_bank_cards(text)
    log.extend(card_log)
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
