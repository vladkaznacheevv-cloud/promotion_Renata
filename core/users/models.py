from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Boolean,
    BigInteger,
    ForeignKey,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from core.db import Base


class User(Base):
    __tablename__ = "users"

    # В БД id = bigserial -> BigInteger
    id = Column(BigInteger, primary_key=True, index=True)

    # tg_id в БД BIGINT + UNIQUE + INDEX + NOT NULL
    tg_id = Column(BigInteger, unique=True, index=True, nullable=False)

    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    username = Column(String(100), nullable=True)

    phone = Column(Text, nullable=True)
    email = Column(String(100), nullable=True)

    # CRM funnel stage
    CRM_STAGE_NEW = "NEW"
    CRM_STAGE_ENGAGED = "ENGAGED"
    CRM_STAGE_READY_TO_PAY = "READY_TO_PAY"
    CRM_STAGE_MANAGER_FOLLOWUP = "MANAGER_FOLLOWUP"
    CRM_STAGE_PAID = "PAID"
    CRM_STAGE_INACTIVE = "INACTIVE"
    CRM_STAGE_CHOICES = [
        CRM_STAGE_NEW,
        CRM_STAGE_ENGAGED,
        CRM_STAGE_READY_TO_PAY,
        CRM_STAGE_MANAGER_FOLLOWUP,
        CRM_STAGE_PAID,
        CRM_STAGE_INACTIVE,
    ]
    crm_stage = Column(String(32), nullable=False, server_default=CRM_STAGE_NEW, index=True)
    last_activity_at = Column(DateTime(timezone=True), nullable=True)

    # VIP
    is_vip = Column(Boolean, nullable=False, server_default="false")
    vip_until = Column(DateTime(timezone=True), nullable=True)

    # Статусы
    STATUS_NEW = "new"
    STATUS_IN_WORK = "in_work"
    STATUS_CLIENT = "client"
    STATUS_VIP = "vip"
    STATUS_ARCHIVED = "archived"
    STATUS_CHOICES = [STATUS_NEW, STATUS_IN_WORK, STATUS_CLIENT, STATUS_VIP, STATUS_ARCHIVED]

    status = Column(String(20), nullable=False, server_default=STATUS_NEW)

    # Источники
    SOURCE_BOT = "bot"
    SOURCE_VIP = "vip_channel"
    SOURCE_RECOMMENDATION = "recommendation"
    SOURCE_COURSE = "course"
    SOURCE_OTHER = "other"
    SOURCE_CHOICES = [SOURCE_BOT, SOURCE_VIP, SOURCE_RECOMMENDATION, SOURCE_COURSE, SOURCE_OTHER]

    source = Column(String(50), nullable=False, server_default=SOURCE_BOT)

    # Интерес (в БД bigint; FK можно держать)
    interested_event_id = Column(BigInteger, ForeignKey("events.id"), nullable=True)
    interested_consultation_id = Column(BigInteger, ForeignKey("consultations.id"), nullable=True)

    # timestamps: в БД timestamptz + DEFAULT now() + триггер обновляет updated_at
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    events = relationship("UserEvent", back_populates="user", cascade="all, delete-orphan")

    consultations = relationship(
        "UserConsultation",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, tg_id={self.tg_id}, name={self.first_name})>"
