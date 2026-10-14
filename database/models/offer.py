from typing import Optional, TYPE_CHECKING
from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from database.models.link import MonitoredLink


class SeenOffer(Base, TimestampMixin):
    __tablename__ = "seen_offers"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    link_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("monitored_links.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    olx_offer_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    price: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    published_at: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    phone: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    monitored_link: Mapped["MonitoredLink"] = relationship(
        "MonitoredLink",
        back_populates="seen_offers",
    )

    __table_args__ = (
        Index("ix_link_olx_offer", "link_id", "olx_offer_id", unique=True),
    )