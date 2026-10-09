from sqlalchemy import ForeignKey, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.config.database import Base


class UserAccess(Base):
    __tablename__ = "user_access"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    permissions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
