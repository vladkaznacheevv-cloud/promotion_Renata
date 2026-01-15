from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, Boolean, BigInteger, Text
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    tg_id = Column(BigInteger, unique=True, index=True)
    first_name = Column(String(100))
    last_name = Column(String(100), nullable=True)
    username = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Deal(Base):
    __tablename__ = 'deals'
    id = Column(Integer, primary_key=True, index=True)
    user_tg_id = Column(BigInteger) 
    status = Column(String(20), default='new')
    amount = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)