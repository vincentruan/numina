"""Soft-delete mixin for archivable models."""

from sqlalchemy import Boolean
from sqlalchemy.orm import Mapped, mapped_column


class ArchivableMixin:
    """Mixin providing ``is_archived`` column for soft-delete support."""

    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
