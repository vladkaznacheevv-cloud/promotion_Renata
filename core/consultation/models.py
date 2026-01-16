from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base

class Consultation(Base):
    __tablename__ = 'consultations'
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Типы консультаций
    TYPE_INDIVIDUAL = 'individual'
    TYPE_GROUP = 'group'
    TYPE_MENTORING = 'mentoring'
    TYPE_CHOICES = [TYPE_INDIVIDUAL, TYPE_GROUP, TYPE_MENTORING]
    type = Column(String(50), nullable=False)
    
    title = Column(String(200), nullable=False)
    description = Column(Text)
    
    # Детали
    duration_minutes = Column(Integer, default=60)  # Длительность в минутах
    price = Column(String(50))  # "3500 ₽/час" или "Бесплатно"
    
    # Расписание
    available_slots = Column(Text)  # JSON массив доступных слотов
    
    # Статус
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Consultation(id={self.id}, title={self.title}, type={self.type})>"


class UserConsultation(Base):
    """Связь пользователь-консультация"""
    __tablename__ = 'user_consultations'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    consultation_id = Column(Integer, ForeignKey('consultations.id'), nullable=False)
    
    # Детали записи
    scheduled_at = Column(DateTime, nullable=False)
    zoom_link = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    
    # Статус
    STATUS_SCHEDULED = 'scheduled'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_NO_SHOW = 'no_show'
    STATUS_CHOICES = [STATUS_SCHEDULED, STATUS_COMPLETED, STATUS_CANCELLED, STATUS_NO_SHOW]
    status = Column(String(20), default=STATUS_SCHEDULED)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)