from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, BigInteger, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base

class Payment(Base):
    __tablename__ = 'payments'
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Связи
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Сумма в копейках
    amount = Column(Integer, default=0)
    currency = Column(String(3), default='RUB')
    
    # Тип продукта
    PRODUCT_EVENT = 'event'
    PRODUCT_CONSULTATION = 'consultation'
    PRODUCT_VIP = 'vip'
    PRODUCT_COURSE = 'course'
    PRODUCT_CHOICES = [PRODUCT_EVENT, PRODUCT_CONSULTATION, PRODUCT_VIP, PRODUCT_COURSE]
    product_type = Column(String(50), nullable=False)
    
    # ID продукта
    product_id = Column(Integer, nullable=True)
    
    # YooKassa
    payment_id = Column(String(100), nullable=True)  # ID в YooKassa
    payment_url = Column(String(500), nullable=True)
    
    # Статусы
    STATUS_PENDING = 'pending'
    STATUS_WAITING = 'waiting_for_capture'
    STATUS_PAID = 'paid'
    STATUS_CANCELLED = 'cancelled'
    STATUS_REFUNDED = 'refunded'
    STATUS_CHOICES = [STATUS_PENDING, STATUS_WAITING, STATUS_PAID, STATUS_CANCELLED, STATUS_REFUNDED]
    status = Column(String(30), default=STATUS_PENDING)
    
    # Описание
    description = Column(String(500), nullable=True)
    metadata = Column(Text, nullable=True)  # JSON
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Отношения
    user = relationship("User", back_populates="payments")
    
    def __repr__(self):
        return f"<Payment(id={self.id}, user_id={self.user_id}, amount={self.amount}, status={self.status})>"
    
    @property
    def amount_rub(self):
        return self.amount / 100 if self.amount else 0