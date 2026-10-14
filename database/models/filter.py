from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from database.models.base import Base, TimestampMixin


class BlacklistRecord(Base, TimestampMixin):
    __tablename__ = "blacklist_records"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_value: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "target_value", name="uq_user_blacklist"),
    )


class StopwordRecord(Base, TimestampMixin):
    __tablename__ = "stopword_records"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    word: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "word", name="uq_user_stopword"),
    )