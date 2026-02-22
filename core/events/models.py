from sqlalchemy import (
    Column,
    BigInteger,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Numeric,
    String,
    Time,
    func,
)
from sqlalchemy.orm import relationship

from core.db import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(BigInteger, primary_key=True, index=True)

    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)

    starts_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)

    location = Column(Text, nullable=True)
    schedule_type = Column(String(20), nullable=False, server_default="one_time", index=True)
    start_date = Column(DateTime(timezone=True), nullable=True)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    recurring_rule = Column(Text, nullable=True)
    hosts = Column(Text, nullable=True)
    price_individual_rub = Column(Integer, nullable=True)
    price_group_rub = Column(Integer, nullable=True)
    duration_hint = Column(Text, nullable=True)
    booking_hint = Column(Text, nullable=True)

    link_getcourse = Column(Text, nullable=True)
    external_source = Column(Text, nullable=True, index=True)
    external_id = Column(Text, nullable=True, index=True)
    external_updated_at = Column(DateTime(timezone=True), nullable=True)

    # Р’ Р‘Р” numeric (С„Р°РєС‚РёС‡РµСЃРєРё numeric(12,2) вЂ” РµСЃР»Рё С‚Р°Рє СЃРѕР·РґР°РІР°Р»)
    price = Column(Numeric(12, 2), nullable=True)

    capacity = Column(Integer, nullable=True)

    is_active = Column(Boolean, nullable=False, server_default="true")

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user_links = relationship(
        "UserEvent",
        back_populates="event",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Event(id={self.id}, title={self.title})>"


class UserEvent(Base):
    __tablename__ = "user_events"

    id = Column(BigInteger, primary_key=True, index=True)

    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id = Column(
        BigInteger,
        ForeignKey("events.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Р’ Р‘Р”: text + DEFAULT 'registered'
    status = Column(Text, nullable=False, server_default="registered")

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user = relationship("User", back_populates="events")
    event = relationship("Event", back_populates="user_links")

