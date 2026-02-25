from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from core.db import Base


class CRMUserActivity(Base):
    __tablename__ = "crm_user_activity"

    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    ai_chats = Column(Integer, nullable=False, server_default="0")
    last_activity_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user = relationship("User", lazy="joined")


class IntegrationState(Base):
    __tablename__ = "integration_state"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), nullable=False, unique=True, index=True)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    payload_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class GetCourseWebhookEvent(Base):
    __tablename__ = "getcourse_webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    received_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    event_id = Column(String(128), nullable=True, index=True)
    payload_hash = Column(String(64), nullable=False, index=True)
    dedupe_key = Column(String(160), nullable=False, unique=True, index=True)
    event_type = Column(String(100), nullable=False, server_default="unknown", index=True)
    user_email = Column(String(255), nullable=True, index=True)
    user_id = Column(String(100), nullable=True, index=True)
    deal_id = Column(String(100), nullable=True, index=True)
    deal_number = Column(String(100), nullable=True, index=True)
    amount = Column(Numeric(12, 2), nullable=True)
    currency = Column(String(16), nullable=True)
    status = Column(String(64), nullable=True, index=True)
    raw_payload = Column(Text, nullable=False)


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "product", name="ux_user_subscriptions_user_product"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product = Column(String(64), nullable=False, server_default="private_channel", index=True)
    status = Column(String(16), nullable=False, server_default="pending", index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user = relationship("User", lazy="joined")
    invites = relationship(
        "ChannelInvite",
        back_populates="subscription",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ChannelInvite(Base):
    __tablename__ = "channel_invites"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(
        Integer,
        ForeignKey("user_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token = Column(String(64), nullable=False, unique=True, index=True)
    invite_url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    used_at = Column(DateTime(timezone=True), nullable=True)

    subscription = relationship("UserSubscription", back_populates="invites")


class YooKassaPayment(Base):
    __tablename__ = "yookassa_payments"
    __table_args__ = (
        UniqueConstraint("payment_id", name="ux_yookassa_payments_payment_id"),
        UniqueConstraint("idempotence_key", name="ux_yookassa_payments_idempotence_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tg_id = Column(BigInteger, nullable=False, index=True)
    product = Column(String(64), nullable=False, server_default="game10", index=True)
    amount_rub = Column(Integer, nullable=False)
    payment_id = Column(String(128), nullable=True, index=True)
    idempotence_key = Column(String(128), nullable=False, index=True)
    status = Column(String(32), nullable=False, server_default="pending", index=True)
    confirmation_url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)


class YooKassaWebhookEvent(Base):
    __tablename__ = "yookassa_webhook_events"
    __table_args__ = (
        UniqueConstraint("event_type", "payment_id", name="ux_yookassa_webhook_event_payment"),
    )

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    payment_id = Column(String(128), nullable=False, index=True)
    raw_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
