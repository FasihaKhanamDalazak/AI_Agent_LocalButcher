"""seed 8 hyderabad outlets with varied stock and demo addresses

Revision ID: 3aa804451344
Revises: 21c989a3600e
Create Date: 2026-07-25 14:36:33.287856

"""
import uuid
from datetime import time
from typing import Sequence, Union

from alembic import op
from sqlalchemy import Boolean, Float, Integer, Numeric, String, Time, table, column, text
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '3aa804451344'
down_revision: Union[str, None] = '21c989a3600e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


outlets_t = table(
    "outlets",
    column("id", UUID),
    column("name", String),
    column("area", String),
    column("city", String),
    column("address_text", String),
    column("lat", Float),
    column("lng", Float),
    column("phone", String),
    column("opening_time", Time),
    column("closing_time", Time),
    column("delivery_radius_km", Float),
    column("is_active", Boolean),
)

outlet_stock_t = table(
    "outlet_stock",
    column("id", UUID),
    column("outlet_id", UUID),
    column("product_id", UUID),
    column("quantity", Numeric),
    column("version", Integer),
)

addresses_t = table(
    "addresses",
    column("id", UUID),
    column("user_id", UUID),
    column("label", String),
    column("address_text", String),
    column("lat", Float),
    column("lng", Float),
    column("is_default", Boolean),
)

# Distance-checked against the existing Madhapur outlet (17.4483, 78.3915,
# 8km radius) with the real haversine_km function before picking these —
# 9 outlets total gives solid coverage of GHMC (Greater Hyderabad) without
# reaching into genuinely different towns/cities, which is deliberate: an
# address in Warangal or Vikarabad should stay out of range so the
# "we don't operate there yet" path has something real to demonstrate.
NEW_OUTLETS = [
    {"name": "Local Butcher - Kukatpally", "area": "Kukatpally",
     "address_text": "KPHB Colony Main Road, Kukatpally, Hyderabad, Telangana",
     "lat": 17.4849, "lng": 78.4138, "phone": "+91-9849011002", "delivery_radius_km": 8.0},
    {"name": "Local Butcher - Secunderabad", "area": "Secunderabad",
     "address_text": "SP Road, Secunderabad, Hyderabad, Telangana",
     "lat": 17.4399, "lng": 78.4983, "phone": "+91-9849011003", "delivery_radius_km": 9.0},
    {"name": "Local Butcher - Banjara Hills", "area": "Banjara Hills",
     "address_text": "Road No. 12, Banjara Hills, Hyderabad, Telangana",
     "lat": 17.4156, "lng": 78.4347, "phone": "+91-9849011004", "delivery_radius_km": 7.0},
    {"name": "Local Butcher - Dilsukhnagar", "area": "Dilsukhnagar",
     "address_text": "Chaitanyapuri Main Road, Dilsukhnagar, Hyderabad, Telangana",
     "lat": 17.3687, "lng": 78.5247, "phone": "+91-9849011005", "delivery_radius_km": 9.0},
    {"name": "Local Butcher - Uppal", "area": "Uppal",
     "address_text": "Uppal Main Road, Uppal, Hyderabad, Telangana",
     "lat": 17.4058, "lng": 78.5591, "phone": "+91-9849011006", "delivery_radius_km": 8.0},
    {"name": "Local Butcher - Attapur", "area": "Attapur",
     "address_text": "PVNR Expressway Service Road, Attapur, Hyderabad, Telangana",
     "lat": 17.3348, "lng": 78.4397, "phone": "+91-9849011007", "delivery_radius_km": 9.0},
    {"name": "Local Butcher - Kompally", "area": "Kompally",
     "address_text": "Kompally Main Road, Kompally, Hyderabad, Telangana",
     "lat": 17.5454, "lng": 78.4867, "phone": "+91-9849011008", "delivery_radius_km": 8.0},
    {"name": "Local Butcher - Shamshabad", "area": "Shamshabad",
     "address_text": "Shamshabad Town Road, Shamshabad, Hyderabad, Telangana",
     "lat": 17.2403, "lng": 78.4294, "phone": "+91-9849011009", "delivery_radius_km": 8.0},
]

# Per-outlet stock multiplier applied to the existing Madhapur quantities —
# simulates different outlet sizes. Combined with STOCK_OVERRIDES below to
# deliberately create "not available here, but a nearby outlet has it"
# scenarios for check_product_availability to actually demonstrate.
OUTLET_MULTIPLIERS = {
    "Local Butcher - Kukatpally": 1.0,
    "Local Butcher - Secunderabad": 0.9,
    "Local Butcher - Banjara Hills": 0.7,
    "Local Butcher - Dilsukhnagar": 1.1,
    "Local Butcher - Uppal": 0.8,
    "Local Butcher - Attapur": 0.6,
    "Local Butcher - Kompally": 0.5,
    "Local Butcher - Shamshabad": 0.5,
}

STOCK_OVERRIDES = {
    ("Local Butcher - Banjara Hills", "Mutton Boneless Cubes"): 0,
    ("Local Butcher - Uppal", "Whole Chicken"): 0,
    ("Local Butcher - Kukatpally", "Prawns Medium Deveined"): 0,
    ("Local Butcher - Secunderabad", "Lamb Chops"): 1,
    ("Local Butcher - Dilsukhnagar", "Crab Cleaned"): 2,
    ("Local Butcher - Attapur", "Crab Cleaned"): 0,
    ("Local Butcher - Attapur", "Pomfret Whole"): 3,
    ("Local Butcher - Kompally", "Mutton Curry Cut"): 0,
    ("Local Butcher - Shamshabad", "Rohu Fish Curry Cut"): 0,
}

# Verified against the outlets above: ~3km from Madhapur (in range), ~7.3km
# from Uppal whose radius is 8km (in range but near the edge), and a
# different city entirely (out of range) — a believable reason a Hyderabad
# customer would have that address saved (visiting family), not a
# contrived example.
DEMO_ADDRESSES = [
    {"label": "Home", "address_text": "Kondapur, Hyderabad, Telangana",
     "lat": 17.4615, "lng": 78.3672, "is_default": True},
    {"label": "Office", "address_text": "ECIL, Hyderabad, Telangana",
     "lat": 17.4711, "lng": 78.5619, "is_default": False},
    {"label": "Parents' House (Warangal)", "address_text": "Hanamkonda, Warangal, Telangana",
     "lat": 17.9784, "lng": 79.5941, "is_default": False},
]

DEMO_USER_EMAIL = "fasiha@example.com"


def upgrade() -> None:
    bind = op.get_bind()
    opening, closing = time(8, 0), time(21, 0)

    outlet_rows = [
        {**o, "id": uuid.uuid4(), "city": "Hyderabad", "opening_time": opening,
         "closing_time": closing, "is_active": True}
        for o in NEW_OUTLETS
    ]
    op.bulk_insert(outlets_t, outlet_rows)
    outlet_id_by_name = {o["name"]: o["id"] for o in outlet_rows}

    products = bind.execute(text("SELECT id, name FROM products")).fetchall()

    stock_rows = []
    for outlet_name, outlet_id in outlet_id_by_name.items():
        multiplier = OUTLET_MULTIPLIERS[outlet_name]
        for product_id, product_name in products:
            base_qty = bind.execute(
                text("SELECT quantity FROM outlet_stock WHERE product_id = :pid LIMIT 1"),
                {"pid": product_id},
            ).scalar() or 20
            qty = STOCK_OVERRIDES.get((outlet_name, product_name))
            if qty is None:
                qty = round(float(base_qty) * multiplier)
            stock_rows.append(
                {"id": uuid.uuid4(), "outlet_id": outlet_id, "product_id": product_id, "quantity": qty, "version": 0}
            )
    op.bulk_insert(outlet_stock_t, stock_rows)

    user_id = bind.execute(text("SELECT id FROM users WHERE email = :email"), {"email": DEMO_USER_EMAIL}).scalar()
    if user_id is not None:
        address_rows = [{**a, "id": uuid.uuid4(), "user_id": user_id} for a in DEMO_ADDRESSES]
        op.bulk_insert(addresses_t, address_rows)


def downgrade() -> None:
    bind = op.get_bind()
    names_sql = ",".join(f"'{o['name']}'" for o in NEW_OUTLETS)
    bind.execute(text(f"DELETE FROM outlet_stock WHERE outlet_id IN (SELECT id FROM outlets WHERE name IN ({names_sql}))"))
    bind.execute(text(f"DELETE FROM outlets WHERE name IN ({names_sql})"))

    user_id = bind.execute(text("SELECT id FROM users WHERE email = :email"), {"email": DEMO_USER_EMAIL}).scalar()
    if user_id is not None:
        labels_sql = ",".join(f"'{a['label']}'" for a in DEMO_ADDRESSES)
        bind.execute(text(f"DELETE FROM addresses WHERE user_id = :uid AND label IN ({labels_sql})"), {"uid": user_id})
