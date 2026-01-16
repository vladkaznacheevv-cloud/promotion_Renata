from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base

class Event(Base):
    __tablename__ = 'events'
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Типы мероприятий
    TYPE_CONCERT = 'concert'
    TYPE_WORKSHOP = 'workshop'
    TYPE_PARTY = 'party'
    TYPE_MEETUP = 'meetup'
    TYPE_WEBINAR = 'webinar'
    TYPE_CHOICES = [TYPE_CONCERT, TYPE_WORKSHOP, TYPE_PARTY, TYPE_MEETUP, TYPE_WEBINAR]
    type = Column(String(50), nullable=False)
    
    title = Column(String(200), nullable=False)
    description = Column(Text)
    
    # Детали
    date = Column(DateTime, nullable=False)
    location = Column(String(200))
    address = Column(String(500), nullable=True)
    price = Column(String(50))  # "1000 ₽" или "Бесплатно"
    seats_total = Column(Integer, default=0)
    seats_sold = Column(Integer, default=0)
    
    # Статус
    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [STATUS_DRAFT, STATUS_PUBLISHED, STATUS_COMPLETED, STATUS_CANCELLED]
    status = Column(String(20), default=STATUS_DRAFT)
    
    # Медиа
    image_url = Column(String(500), nullable=True)
    
    # Внешние ссылки
    external_url = Column(String(500), nullable=True)
    external_id = Column(String(100), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Отношения
    participants = relationship("UserEvent", back_populates="event")
    
    def __repr__(self):
        return f"<Event(id={self.id}, title={self.title}, type={self.type})>"
    
    @property
    def seats_available(self):
        return self.seats_total - self.seats_sold


class UserEvent(Base):
    """Связь пользователь-мероприятие"""
    __tablename__ = 'user_events'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    event_id = Column(Integer, ForeignKey('events.id'), nullable=False)
    
    # Статус участия
    STATUS_REGISTERED = 'registered'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_ATTENDED = 'attended'
    STATUS_CHOICES = [STATUS_REGISTERED, STATUS_CONFIRMED, STATUS_CANCELLED, STATUS_ATTENDED]
    status = Column(String(20), default=STATUS_REGISTERED)
    
    source = Column(String(50), default='bot')  # bot, crm, payment
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Отношения
    user = relationship("User", back_populates="events")
    event = relationship("Event", back_populates="participants")