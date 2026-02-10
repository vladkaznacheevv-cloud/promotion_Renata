from sqlalchemy import Column, BigInteger, DateTime, Text, Boolean, func

from core.db import Base


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(BigInteger, primary_key=True, index=True)
    email = Column(Text, nullable=False, unique=True, index=True)
    password_hash = Column(Text, nullable=False)
    role = Column(Text, nullable=False, server_default="admin")
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self):
        return f"<AdminUser(id={self.id}, email={self.email}, role={self.role})>"
