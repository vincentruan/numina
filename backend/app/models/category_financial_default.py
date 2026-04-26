from sqlalchemy import BigInteger, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.snowflake import next_id


class CategoryFinancialDefault(Base):
    __tablename__ = "category_financial_defaults"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    category_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("categories.id"), nullable=False, unique=True
    )
    default_annual_depreciation: Mapped[float] = mapped_column(Float, default=0.1)
    default_annual_return: Mapped[float] = mapped_column(Float, default=0.0)
    default_lifespan_years: Mapped[int | None] = mapped_column(Integer, nullable=True, default=10)

    category = relationship("Category")
