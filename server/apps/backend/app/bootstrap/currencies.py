"""Bootstrap favorite currencies."""

from sqlalchemy.orm import Session

from apps.backend.app.core.logging_config import get_logger

logger = get_logger(__name__)

FAVORITE_CURRENCIES = [
    {"code": "CNY", "name_zh": "人民币", "name_en": "Chinese Yuan",      "symbol": "¥",   "flag_emoji": "🇨🇳", "sort_order": 1},
    {"code": "USD", "name_zh": "美元",   "name_en": "US Dollar",         "symbol": "$",   "flag_emoji": "🇺🇸", "sort_order": 2},
    {"code": "EUR", "name_zh": "欧元",   "name_en": "Euro",              "symbol": "€",   "flag_emoji": "🇪🇺", "sort_order": 3},
    {"code": "JPY", "name_zh": "日元",   "name_en": "Japanese Yen",      "symbol": "¥",   "flag_emoji": "🇯🇵", "sort_order": 4},
    {"code": "GBP", "name_zh": "英镑",   "name_en": "British Pound",     "symbol": "£",   "flag_emoji": "🇬🇧", "sort_order": 5},
    {"code": "AUD", "name_zh": "澳元",   "name_en": "Australian Dollar", "symbol": "A$",  "flag_emoji": "🇦🇺", "sort_order": 6},
    {"code": "CAD", "name_zh": "加元",   "name_en": "Canadian Dollar",   "symbol": "C$",  "flag_emoji": "🇨🇦", "sort_order": 7},
    {"code": "CHF", "name_zh": "瑞士法郎","name_en": "Swiss Franc",      "symbol": "Fr",  "flag_emoji": "🇨🇭", "sort_order": 8},
    {"code": "HKD", "name_zh": "港币",   "name_en": "Hong Kong Dollar",  "symbol": "HK$", "flag_emoji": "🇭🇰", "sort_order": 9},
    {"code": "SGD", "name_zh": "新加坡元","name_en": "Singapore Dollar", "symbol": "S$",  "flag_emoji": "🇸🇬", "sort_order": 10},
    {"code": "RUB", "name_zh": "卢布",   "name_en": "Russian Ruble",     "symbol": "₽",   "flag_emoji": "🇷🇺", "sort_order": 11},
    {"code": "INR", "name_zh": "卢比",   "name_en": "Indian Rupee",      "symbol": "₹",   "flag_emoji": "🇮🇳", "sort_order": 12},
    {"code": "BRL", "name_zh": "巴西雷亚尔","name_en": "Brazilian Real", "symbol": "R$",  "flag_emoji": "🇧🇷", "sort_order": 13},
]


def bootstrap_currencies(db: Session) -> None:
    """Ensure favorite currencies exist. Idempotent."""
    from apps.backend.app.models.currency import Currency

    existing = db.query(Currency).filter(Currency.is_favorite == True).first()  # noqa: E712
    if existing:
        return

    for cur_data in FAVORITE_CURRENCIES:
        cur = Currency(is_favorite=True, **cur_data)
        db.add(cur)
    db.commit()
    logger.info(f"已初始化 {len(FAVORITE_CURRENCIES)} 个常用货币")
