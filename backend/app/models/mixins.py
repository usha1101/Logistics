from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column


class SoftDeleteMixin:
    """
    Mixin providing standard soft-deletion capabilities across operational entities.
    Preserves audit trails, historical compliance, and referential integrity.
    """

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    def soft_delete(self) -> None:
        """Marks the entity as soft-deleted with the current UTC timestamp."""
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)

    def restore(self) -> None:
        """Restores a soft-deleted entity back to active status."""
        self.is_deleted = False
        self.deleted_at = None
