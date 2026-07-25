"""seed placeholder product catalog

Revision ID: 21c989a3600e
Revises: 3e071ffdf90f
Create Date: 2026-07-25 13:22:30.521948

"""
import uuid
from typing import Sequence, Union

from alembic import op
from sqlalchemy import Boolean, Integer, Numeric, String, table, column, text
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '21c989a3600e'
down_revision: Union[str, None] = '3e071ffdf90f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


products = table(
    "products",
    column("id", UUID),
    column("name", String),
    column("category", String),
    column("description", String),
    column("unit", String),
    column("price", Numeric),
    column("max_qty_per_order", Numeric),
    column("is_active", Boolean),
)

outlet_stock = table(
    "outlet_stock",
    column("id", UUID),
    column("outlet_id", UUID),
    column("product_id", UUID),
    column("quantity", Numeric),
    column("version", Integer),
)

# Placeholder catalog matching the four categories named in the
# LocalButcher brand knowledge base (Poultry / Meat / Seafood / Farm Eggs)
# — not the founder's real product data. Replace/extend when that arrives;
# nothing in the LLM layer needs to change to pick up real rows (see
# README "Recommendations" section).
PRODUCTS = [
    {"name": "Chicken Curry Cut", "category": "Poultry", "unit": "kg", "price": 240, "max_qty_per_order": 5,
     "description": "Bone-in chicken, curry cut, skinless.", "stock": 60},
    {"name": "Chicken Boneless Cubes", "category": "Poultry", "unit": "kg", "price": 320, "max_qty_per_order": 5,
     "description": "Boneless chicken breast and thigh, cubed for curries.", "stock": 50},
    {"name": "Whole Chicken", "category": "Poultry", "unit": "piece", "price": 280, "max_qty_per_order": 3,
     "description": "Whole dressed chicken, skin-on, approx 1.1 kg.", "stock": 25},
    {"name": "Country Chicken Curry Cut", "category": "Poultry", "unit": "kg", "price": 420, "max_qty_per_order": 3,
     "description": "Naati/country chicken, curry cut — firmer texture, richer flavour.", "stock": 20},

    {"name": "Mutton Curry Cut", "category": "Meat", "unit": "kg", "price": 780, "max_qty_per_order": 5,
     "description": "Bone-in goat mutton, curry cut.", "stock": 35},
    {"name": "Mutton Boneless Cubes", "category": "Meat", "unit": "kg", "price": 900, "max_qty_per_order": 5,
     "description": "Boneless goat mutton, cubed.", "stock": 25},
    {"name": "Lamb Chops", "category": "Meat", "unit": "kg", "price": 950, "max_qty_per_order": 3,
     "description": "Rack of lamb, cut into chops.", "stock": 15},
    {"name": "Mutton Keema", "category": "Meat", "unit": "kg", "price": 820, "max_qty_per_order": 5,
     "description": "Freshly minced goat mutton.", "stock": 20},

    {"name": "Rohu Fish Curry Cut", "category": "Seafood", "unit": "kg", "price": 260, "max_qty_per_order": 5,
     "description": "Rohu fish, cleaned and curry cut.", "stock": 30},
    {"name": "Pomfret Whole", "category": "Seafood", "unit": "kg", "price": 650, "max_qty_per_order": 3,
     "description": "Whole pomfret, cleaned and gutted.", "stock": 15},
    {"name": "Prawns Medium Deveined", "category": "Seafood", "unit": "kg", "price": 520, "max_qty_per_order": 3,
     "description": "Medium-sized prawns, peeled and deveined.", "stock": 20},
    {"name": "Crab Cleaned", "category": "Seafood", "unit": "kg", "price": 480, "max_qty_per_order": 3,
     "description": "Whole crab, cleaned and ready to cook.", "stock": 10},

    {"name": "Farm Eggs Pack of 6", "category": "Farm Eggs", "unit": "pack", "price": 60, "max_qty_per_order": 10,
     "description": "Farm-fresh eggs, pack of 6.", "stock": 80},
    {"name": "Farm Eggs Pack of 12", "category": "Farm Eggs", "unit": "pack", "price": 110, "max_qty_per_order": 10,
     "description": "Farm-fresh eggs, pack of 12.", "stock": 60},
    {"name": "Farm Eggs Tray of 30", "category": "Farm Eggs", "unit": "tray", "price": 260, "max_qty_per_order": 5,
     "description": "Farm-fresh eggs, tray of 30.", "stock": 20},
]


def upgrade() -> None:
    bind = op.get_bind()

    # The one pre-existing smoke-test product predates this taxonomy —
    # fold it into "Poultry" so category filtering is consistent.
    bind.execute(text("UPDATE products SET category = 'Poultry' WHERE name = 'Boneless Chicken Breast'"))

    outlet_ids = [row[0] for row in bind.execute(text("SELECT id FROM outlets")).fetchall()]

    rows = [{**p, "id": uuid.uuid4(), "is_active": True} for p in PRODUCTS]
    op.bulk_insert(products, [{k: v for k, v in r.items() if k != "stock"} for r in rows])

    if outlet_ids:
        stock_rows = [
            {"id": uuid.uuid4(), "outlet_id": outlet_id, "product_id": r["id"], "quantity": r["stock"], "version": 0}
            for r in rows
            for outlet_id in outlet_ids
        ]
        op.bulk_insert(outlet_stock, stock_rows)


def downgrade() -> None:
    bind = op.get_bind()
    names_sql = ",".join(f"'{p['name']}'" for p in PRODUCTS)
    bind.execute(text(f"DELETE FROM outlet_stock WHERE product_id IN (SELECT id FROM products WHERE name IN ({names_sql}))"))
    bind.execute(text(f"DELETE FROM products WHERE name IN ({names_sql})"))
    bind.execute(text("UPDATE products SET category = 'Chicken' WHERE name = 'Boneless Chicken Breast'"))
