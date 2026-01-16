from sqlalchemy import Column, Integer, String, DateTime, Boolean, BigInteger, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    tg_id = Column(BigInteger, unique=True, index=True, nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100), nullable=True)
    username = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    
    # VIP статус
    is_vip = Column(Boolean, default=False)
    vip_until = Column(DateTime, nullable=True)
    
    # Статусы
    STATUS_NEW = 'new'
    STATUS_IN_WORK = 'in_work'
    STATUS_CLIENT = 'client'
    STATUS_VIP = 'vip'
    STATUS_ARCHIVED = 'archived'
    STATUS_CHOICES = [STATUS_NEW, STATUS_IN_WORK, STATUS_CLIENT, STATUS_VIP, STATUS_ARCHIVED]
    status = Column(String(20), default=STATUS_NEW)
    
    # Источники
    SOURCE_BOT = 'bot'
    SOURCE_VIP = 'vip_channel'
    SOURCE_RECOMMENDATION = 'recommendation'
    SOURCE_COURSE = 'course'
    SOURCE_OTHER = 'other'
    SOURCE_CHOICES = [SOURCE_BOT, SOURCE_VIP, SOURCE_RECOMMENDATION, SOURCE_COURSE, SOURCE_OTHER]
    source = Column(String(50), default=SOURCE_BOT)
    
    # Интересующие продукты (FK)
    interested_event_id = Column(Integer, ForeignKey('events.id'), nullable=True)
    interested_consultation_id = Column(Integer, ForeignKey('consultations.id'), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Отношения
    events = relationship("UserEvent", back_populates="user")
    consultations = relationship("UserConsultation", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    
    def __repr__(self):
        return f"<User(id={self.id}, tg_id={self.tg_id}, name={self.first_name})>"