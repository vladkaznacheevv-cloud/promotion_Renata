from sqlalchemy import BigInteger, Column, DateTime, Numeric, String, Text, func

from core.db import Base


class CatalogItem(Base):
    __tablename__ = "catalog_items"

    id = Column(BigInteger, primary_key=True, index=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(12, 2), nullable=True)
    currency = Column(String(8), nullable=False, server_default="RUB")
    link_getcourse = Column(Text, nullable=True)
    item_type = Column(String(20), nullable=False, server_default="product")
    status = Column(String(20), nullable=False, server_default="active")
    external_source = Column(String(50), nullable=False, server_default="getcourse")
    external_id = Column(String(255), nullable=False, index=True)
    external_updated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<CatalogItem(id={self.id}, type={self.item_type}, title={self.title})>"
