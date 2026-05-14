from sqlalchemy import BigInteger, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base


class Currency(Base):
    __tablename__ = "currencies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    name_zh: Mapped[str] = mapped_column(String(50), nullable=False)
    name_en: Mapped[str] = mapped_column(String(50), nullable=False)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    flag_emoji: Mapped[str] = mapped_column(String(10), nullable=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=999)
