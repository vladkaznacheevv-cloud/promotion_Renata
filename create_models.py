# create_models.py
code = '''from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, DECIMAL, Enum, ForeignKey,
    Integer, String, Text
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

Base = declarative_base()

class ProductType(enum.Enum):
    online_course = "online_course"
    seminar = "seminar"
    individual_meeting = "individual_meeting"
    training_for_psychologists = "training_for_psychologists"

class StaffRole(enum.Enum):
    manager = "manager"
    admin = "admin"

class DealStatus(enum.Enum):
    new = "new"
    consultation_scheduled = "consultation_scheduled"
    paid = "paid"
    completed = "completed"
    cancelled = "cancelled"

class MessageRole(enum.Enum):
    user = "user"
    assistant = "assistant"

class User(Base):
    __tablename__ = "user"
    user_id = Column(BigInteger, primary_key=True)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255))
    username = Column(String(255))
    phone = Column(String(32))
    email = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    utm_source = Column(String(100))
    is_bot_blocked = Column(Boolean, default=False)
    deals = relationship("Deal", back_populates="user")
    messages = relationship("MessageLog", back_populates="user")

class Product(Base):
    __tablename__ = "product"
    product_id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    type = Column(Enum(ProductType), nullable=False)
    price = Column(DECIMAL(10, 2), nullable=False)
    gcourse_product_id = Column(String(100))
    is_active = Column(Boolean, default=True)
    deals = relationship("Deal", back_populates="product")

class Staff(Base):
    __tablename__ = "staff"
    staff_id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    role = Column(Enum(StaffRole), nullable=False, default=StaffRole.manager)
    is_active = Column(Boolean, default=True)
    managed_deals = relationship("Deal", back_populates="assigned_manager")

class Deal(Base):
    __tablename__ = "deal"
    deal_id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("user.user_id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("product.product_id", ondelete="RESTRICT"), nullable=False)
    status = Column(Enum(DealStatus), nullable=False, default=DealStatus.new)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    payment_id = Column(String(100))
    assigned_manager_id = Column(Integer, ForeignKey("staff.staff_id", ondelete="SET NULL"))
    user = relationship("User", back_populates="deals")
    product = relationship("Product", back_populates="deals")
    assigned_manager = relationship("Staff", back_populates="managed_deals")

class MessageLog(Base):
    __tablename__ = "message_log"
    message_id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("user.user_id", ondelete="CASCADE"), nullable=False)
    role = Column(Enum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    context_summary = Column(Text)
    user = relationship("User", back_populates="messages")
'''

with open('models.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("✅ models.py создан без BOM")