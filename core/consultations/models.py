from sqlalchemy import (
    Column,
    BigInteger,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Numeric,
    func,
)
from sqlalchemy.orm import relationship

from core.db import Base


class Consultation(Base):
    __tablename__ = "consultations"

    id = Column(BigInteger, primary_key=True, index=True)

    # В БД: text
    type = Column(Text, nullable=False)

    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)

    duration_minutes = Column(Integer, nullable=True)

    # В БД: numeric (без scale в introspection, но фактически numeric(12,2))
    price = Column(Numeric(12, 2), nullable=True)

    # В БД: integer
    available_slots = Column(Integer, nullable=True)

    is_active = Column(Boolean, nullable=False, server_default="true")

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user_links = relationship(
        "UserConsultation",
        back_populates="consultation",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Consultation(id={self.id}, title={self.title}, type={self.type})>"


class UserConsultation(Base):
    __tablename__ = "user_consultations"

    id = Column(BigInteger, primary_key=True, index=True)

    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    consultation_id = Column(
        BigInteger,
        ForeignKey("consultations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    scheduled_at = Column(DateTime(timezone=True), nullable=True)

    zoom_link = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # В БД: text + DEFAULT 'scheduled'
    status = Column(Text, nullable=False, server_default="scheduled")

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user = relationship("User", back_populates="consultations")
    consultation = relationship("Consultation", back_populates="user_links")
