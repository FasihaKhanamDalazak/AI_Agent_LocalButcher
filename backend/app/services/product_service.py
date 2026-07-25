import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product


async def list_products(db: AsyncSession, category: str | None = None) -> list[Product]:
    stmt = select(Product).where(Product.is_active == True)  # noqa: E712
    if category:
        # Case-insensitive: the LLM guesses category strings from the
        # user's wording (e.g. "chicken"), which won't exact-match the
        # stored title-case values ("Poultry") — ILIKE avoids a silent
        # empty result on a plausible guess.
        stmt = stmt.where(Product.category.ilike(category))
    result = await db.execute(stmt.order_by(Product.name))
    return list(result.scalars().all())


async def get_product(db: AsyncSession, product_id: uuid.UUID) -> Product | None:
    return await db.get(Product, product_id)
