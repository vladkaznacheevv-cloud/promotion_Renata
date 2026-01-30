from sqlalchemy import Column, Integer, String, Text, Boolean, Numeric
from core.db.base import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)

    title = Column(String(255), nullable=False)

    type = Column(String(50), nullable=False)
    # consultation | group | vip | getcourse | tg_channel

    short_description = Column(Text, nullable=False)

    price = Column(Numeric(10, 2), nullable=True)
    currency = Column(String(10), default="RUB")

    is_active = Column(Boolean, default=True)

    external_id = Column(String(255), nullable=True)
