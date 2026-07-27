"""Currency symbols and labels for server-side formatting.

Mirrors the frontend ``CURRENCY_SYMBOLS`` in ``utils/format.ts``.
"""

CURRENCY_SYMBOLS: dict[str, str] = {
    "CNY": "¥",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "HKD": "HK$",
}

CURRENCY_LABELS: dict[str, str] = {
    "CNY": "人民币",
    "USD": "美元",
    "EUR": "欧元",
    "GBP": "英镑",
    "JPY": "日元",
    "HKD": "港币",
}
