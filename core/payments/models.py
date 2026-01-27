from sqlalchemy import (
    Column,
    BigInteger,
    Integer,
    DateTime,
    ForeignKey,
    Text,
    JSON,
    func,
)
from sqlalchemy.orm import relationship

from core.db import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(BigInteger, primary_key=True, index=True)

    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # у тебя amount integer — считаем что это "копейки" или просто целое
    amount = Column(Integer, nullable=True)

    status = Column(Text, nullable=False, server_default="pending", index=True)

    provider = Column(Text, nullable=True)
    external_id = Column(Text, nullable=True)

    metadata_ = Column("metadata", JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user = relationship("User", back_populates="payments")

    def __repr__(self):
        return f"<Payment(id={self.id}, user_id={self.user_id}, amount={self.amount}, status={self.status})>"
