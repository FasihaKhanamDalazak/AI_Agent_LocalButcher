from fastapi import APIRouter

from app.api.v1.endpoints import addresses, auth, cart, chat, orders, outlets, products, staff, support, voice

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(outlets.router, prefix="/outlets", tags=["outlets"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(cart.router, prefix="/cart", tags=["cart"])
api_router.include_router(orders.router, prefix="/orders", tags=["orders"])
api_router.include_router(addresses.router, prefix="/addresses", tags=["addresses"])
api_router.include_router(support.router, prefix="/support-tickets", tags=["support"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(voice.router, prefix="/chat/voice", tags=["voice"])
api_router.include_router(staff.router, prefix="/staff", tags=["staff"])
