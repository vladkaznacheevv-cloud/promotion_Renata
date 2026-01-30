from sqlalchemy import select
from core.products.models import Product


class ProductService:
    def __init__(self, session):
        self.session = session

    async def get_active(self):
        stmt = select(Product).where(Product.is_active == True)
        result = await self.session.execute(stmt)
        return result.scalars().all()
