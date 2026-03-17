"""Keep list database model."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class KeepListEntry(SQLModel, table=True):
    """A file path that should never be deleted during cleanup."""

    __tablename__ = "keep_list"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    path: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
