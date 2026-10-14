from typing import List, Optional
from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        index=True,
        autoincrement=False,
    )
    username: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    first_name: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    monitored_links: Mapped[List["MonitoredLink"]] = relationship(
        "MonitoredLink",
        back_populates="user",
        cascade="all, delete-orphan",
    )