import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.address import AddressRead
from app.schemas.cart import cart_item_to_detailed
from app.schemas.order import order_to_read
from app.schemas.outlet import OutletRead
from app.schemas.product import ProductRead
from app.schemas.support import SupportTicketRead
from app.llm import knowledge_base
from app.services import (
    address_service,
    availability_service,
    cart_service,
    order_service,
    outlet_service,
    product_service,
    support_service,
)


class ToolExecutionError(Exception):
    """Message is meant to be read back to the LLM, not raised to the HTTP client."""


def _uuid(args: dict, key: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(args[key]))
    except (KeyError, ValueError, TypeError):
        raise ToolExecutionError(f"'{key}' is missing or not a valid id")


def _optional_uuid(args: dict, key: str) -> uuid.UUID | None:
    return uuid.UUID(str(args[key])) if args.get(key) else None


async def _get_profile(db: AsyncSession, user: User, args: dict) -> dict:
    # Deliberately NOT UserRead.model_validate(user) — that includes `id`.
    # The system prompt already says never reveal user IDs; this makes it
    # true architecturally too, so a misbehaving model has no id to recite
    # even if the instruction gets ignored.
    return {
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "preferred_language": user.preferred_language,
    }


async def _list_addresses(db: AsyncSession, user: User, args: dict) -> dict:
    addresses = await address_service.list_addresses(db, user.id)
    return {"addresses": [AddressRead.model_validate(a).model_dump(mode="json") for a in addresses]}


async def _add_address(db: AsyncSession, user: User, args: dict) -> dict:
    label = (args.get("label") or "").strip()
    address_text = (args.get("address_text") or "").strip()
    if not label or not address_text:
        raise ToolExecutionError("label and address_text are required.")
    # lat/lng are deliberately never set from chat — the model has no real
    # way to know a text address's coordinates and must not guess them.
    # This address works for pickup immediately; delivery-range checks
    # need it updated with real coordinates first (see AddressMissingLocationError).
    address = await address_service.create_address(
        db, user.id, label, address_text, lat=None, lng=None, is_default=bool(args.get("is_default") or False)
    )
    return AddressRead.model_validate(address).model_dump(mode="json")


async def _update_address(db: AsyncSession, user: User, args: dict) -> dict:
    address_id = _uuid(args, "address_id")
    try:
        address = await address_service.update_address(
            db,
            user.id,
            address_id,
            label=args.get("label"),
            address_text=args.get("address_text"),
            lat=None,  # never touched from chat — see _add_address
            lng=None,
            is_default=args.get("is_default"),
        )
    except address_service.AddressNotFoundError:
        raise ToolExecutionError("That address wasn't found.")
    return AddressRead.model_validate(address).model_dump(mode="json")


async def _remove_address(db: AsyncSession, user: User, args: dict) -> dict:
    address_id = _uuid(args, "address_id")
    try:
        await address_service.delete_address(db, user.id, address_id)
    except address_service.AddressNotFoundError:
        raise ToolExecutionError("That address wasn't found.")
    except address_service.AddressInUseError:
        raise ToolExecutionError("That address is linked to an existing order and can't be deleted.")
    return {"removed": True}


async def _list_outlets(db: AsyncSession, user: User, args: dict) -> dict:
    outlets = await outlet_service.list_outlets(db)
    return {"outlets": [OutletRead.model_validate(o).model_dump(mode="json") for o in outlets]}


async def _get_nearest_outlet(db: AsyncSession, user: User, args: dict) -> dict:
    address_id = _uuid(args, "address_id")
    try:
        outlet, distance, in_range = await outlet_service.get_nearest_outlet(db, user.id, address_id)
    except outlet_service.AddressNotFoundError:
        raise ToolExecutionError("That address wasn't found.")
    except outlet_service.AddressMissingLocationError:
        raise ToolExecutionError(
            "That address doesn't have location details on file yet, so delivery distance can't be checked "
            "for it — try a different saved address, or ask about pickup instead."
        )
    except outlet_service.NoActiveOutletsError:
        raise ToolExecutionError("No active outlets are available right now.")
    data = OutletRead.model_validate(outlet).model_dump(mode="json")
    data["distance_km"] = round(distance, 2)
    # False means even the closest outlet can't deliver this far — the
    # system prompt handles telling the customer this warmly.
    data["in_range"] = in_range
    return data


async def _list_products(db: AsyncSession, user: User, args: dict) -> dict:
    products = await product_service.list_products(db, category=args.get("category"))
    return {"products": [ProductRead.model_validate(p).model_dump(mode="json") for p in products]}


async def _check_product_availability(db: AsyncSession, user: User, args: dict) -> dict:
    product_id = _uuid(args, "product_id")
    outlet_id = _uuid(args, "outlet_id")
    quantity = float(args.get("quantity") or 1)
    address_id = _optional_uuid(args, "address_id")
    try:
        result = await availability_service.check_availability(
            db, product_id, outlet_id, quantity, address_id=address_id, user_id=user.id
        )
    except availability_service.OutletNotFoundError:
        raise ToolExecutionError("That outlet wasn't found.")
    if result.get("alternate_outlet") is not None:
        result["alternate_outlet"] = OutletRead.model_validate(result["alternate_outlet"]).model_dump(mode="json")
    result["product_id"] = str(result["product_id"])
    result["outlet_id"] = str(result["outlet_id"])
    return result


async def _get_cart(db: AsyncSession, user: User, args: dict) -> dict:
    rows = await cart_service.get_cart(db, user.id)
    items = [cart_item_to_detailed(item, product).model_dump(mode="json") for item, product in rows]
    return {"items": items, "subtotal": round(sum(i["line_total"] for i in items), 2)}


async def _add_to_cart(db: AsyncSession, user: User, args: dict) -> dict:
    product_id = _uuid(args, "product_id")
    quantity = float(args.get("quantity") or 0)
    try:
        item, product = await cart_service.add_to_cart(db, user.id, product_id, quantity)
    except cart_service.ProductNotFoundError:
        raise ToolExecutionError("That product wasn't found or isn't currently available.")
    except cart_service.QuantityLimitError as e:
        raise ToolExecutionError(f"The maximum allowed quantity for this product is {e.limit}.")
    return cart_item_to_detailed(item, product).model_dump(mode="json")


async def _update_cart_item(db: AsyncSession, user: User, args: dict) -> dict:
    item_id = _uuid(args, "item_id")
    quantity = float(args.get("quantity") or 0)
    try:
        item, product = await cart_service.update_cart_item(db, user.id, item_id, quantity)
    except cart_service.CartItemNotFoundError:
        raise ToolExecutionError("That cart item wasn't found.")
    except cart_service.QuantityLimitError as e:
        raise ToolExecutionError(f"The maximum allowed quantity for this product is {e.limit}.")
    return cart_item_to_detailed(item, product).model_dump(mode="json")


async def _remove_from_cart(db: AsyncSession, user: User, args: dict) -> dict:
    item_id = _uuid(args, "item_id")
    try:
        await cart_service.remove_from_cart(db, user.id, item_id)
    except cart_service.CartItemNotFoundError:
        raise ToolExecutionError("That cart item wasn't found.")
    return {"removed": True}


async def _checkout(db: AsyncSession, user: User, args: dict) -> dict:
    outlet_id = _uuid(args, "outlet_id")
    fulfillment_type = args.get("fulfillment_type")
    address_id = _optional_uuid(args, "address_id")
    try:
        order = await order_service.checkout(db, user.id, outlet_id, fulfillment_type, address_id)
    except order_service.EmptyCartError:
        raise ToolExecutionError("The cart is empty — add items before checking out.")
    except order_service.AddressRequiredError:
        raise ToolExecutionError("A delivery address is required for delivery orders.")
    except order_service.AddressNotFoundError:
        raise ToolExecutionError("That address wasn't found.")
    except order_service.OutletNotFoundError:
        raise ToolExecutionError("That outlet wasn't found.")
    except order_service.AddressMissingLocationError:
        raise ToolExecutionError(
            "That address doesn't have location details on file yet, so I can't confirm delivery is possible "
            "there — try a different saved address, or choose pickup instead."
        )
    except order_service.DeliveryOutOfRangeError as e:
        raise ToolExecutionError(
            f"That address is about {e.distance_km:.1f} km from {e.outlet_name}, which only delivers "
            f"within {e.radius_km:.0f} km — outside what we can currently reach."
        )
    except order_service.InsufficientStockError as e:
        raise ToolExecutionError(f"Only {e.available} of {e.product_name} is available at that outlet.")
    return order_to_read(order).model_dump(mode="json")


async def _list_orders(db: AsyncSession, user: User, args: dict) -> dict:
    orders = await order_service.list_orders(db, user.id)
    return {"orders": [order_to_read(o).model_dump(mode="json") for o in orders]}


async def _get_order(db: AsyncSession, user: User, args: dict) -> dict:
    order_id = _uuid(args, "order_id")
    try:
        order = await order_service.get_order(db, user.id, order_id)
    except order_service.OrderNotFoundError:
        raise ToolExecutionError("That order wasn't found.")
    return order_to_read(order).model_dump(mode="json")


async def _cancel_order(db: AsyncSession, user: User, args: dict) -> dict:
    order_id = _uuid(args, "order_id")
    try:
        order = await order_service.cancel_order(db, user.id, order_id)
    except order_service.OrderNotFoundError:
        raise ToolExecutionError("That order wasn't found.")
    except order_service.OrderNotCancellableError as e:
        raise ToolExecutionError(f"This order can't be cancelled — it's already {e.status_label}.")
    return order_to_read(order).model_dump(mode="json")


async def _update_order_item(db: AsyncSession, user: User, args: dict) -> dict:
    order_id = _uuid(args, "order_id")
    item_id = _uuid(args, "item_id")
    quantity = float(args.get("quantity") or 0)
    try:
        order = await order_service.update_order_item(db, user.id, order_id, item_id, quantity)
    except order_service.OrderNotFoundError:
        raise ToolExecutionError("That order wasn't found.")
    except order_service.OrderNotModifiableError as e:
        raise ToolExecutionError(f"This order can no longer be modified — it's already {e.status_label}.")
    except order_service.ItemNotInOrderError:
        raise ToolExecutionError("That item isn't part of this order.")
    except order_service.QuantityLimitError as e:
        raise ToolExecutionError(f"The maximum allowed quantity for this product is {e.limit}.")
    except order_service.InsufficientStockError as e:
        raise ToolExecutionError(f"Only {e.available} of {e.product_name} is available at that outlet.")
    return order_to_read(order).model_dump(mode="json")


async def _remove_order_item(db: AsyncSession, user: User, args: dict) -> dict:
    order_id = _uuid(args, "order_id")
    item_id = _uuid(args, "item_id")
    try:
        order = await order_service.remove_order_item(db, user.id, order_id, item_id)
    except order_service.OrderNotFoundError:
        raise ToolExecutionError("That order wasn't found.")
    except order_service.OrderNotModifiableError as e:
        raise ToolExecutionError(f"This order can no longer be modified — it's already {e.status_label}.")
    except order_service.ItemNotInOrderError:
        raise ToolExecutionError("That item isn't part of this order.")
    except order_service.CannotRemoveLastItemError:
        raise ToolExecutionError("Can't remove the last item in an order — cancel the order instead.")
    return order_to_read(order).model_dump(mode="json")


async def _reorder_previous_order(db: AsyncSession, user: User, args: dict) -> dict:
    order_id = _optional_uuid(args, "order_id")
    try:
        added, skipped = await order_service.reorder(db, user.id, order_id)
    except order_service.OrderNotFoundError:
        raise ToolExecutionError("No previous order was found to reorder.")
    return {
        "added": [cart_item_to_detailed(item, product).model_dump(mode="json") for item, product in added],
        "skipped": skipped,
    }


async def _search_knowledge_base(db: AsyncSession, user: User, args: dict) -> dict:
    query = (args.get("query") or "").strip()
    if not query:
        raise ToolExecutionError("query is required.")
    return {"results": knowledge_base.search(query)}


async def _create_support_ticket(db: AsyncSession, user: User, args: dict) -> dict:
    issue_text = (args.get("issue_text") or "").strip()
    if not issue_text:
        raise ToolExecutionError("issue_text is required.")
    order_id = _optional_uuid(args, "order_id")
    try:
        ticket = await support_service.create_ticket(db, user.id, issue_text, order_id)
    except support_service.OrderNotFoundError:
        raise ToolExecutionError("That order wasn't found.")
    return SupportTicketRead.model_validate(ticket).model_dump(mode="json")


_HANDLERS = {
    "get_profile": _get_profile,
    "list_addresses": _list_addresses,
    "add_address": _add_address,
    "update_address": _update_address,
    "remove_address": _remove_address,
    "list_outlets": _list_outlets,
    "get_nearest_outlet": _get_nearest_outlet,
    "list_products": _list_products,
    "check_product_availability": _check_product_availability,
    "get_cart": _get_cart,
    "add_to_cart": _add_to_cart,
    "update_cart_item": _update_cart_item,
    "remove_from_cart": _remove_from_cart,
    "checkout": _checkout,
    "list_orders": _list_orders,
    "get_order": _get_order,
    "cancel_order": _cancel_order,
    "update_order_item": _update_order_item,
    "remove_order_item": _remove_order_item,
    "reorder_previous_order": _reorder_previous_order,
    "search_knowledge_base": _search_knowledge_base,
    "create_support_ticket": _create_support_ticket,
}


async def execute_tool(db: AsyncSession, user: User, tool_name: str, args: dict) -> dict:
    """
    The single choke point every LLM tool call passes through. `user` comes
    from the authenticated request (get_current_user in the endpoint layer)
    — never from `args`. No handler above accepts or trusts a user id
    supplied by the model; that's what makes "show me another customer's
    orders" have no code path to succeed through, regardless of phrasing.
    """
    handler = _HANDLERS.get(tool_name)
    if handler is None:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        return await handler(db, user, args or {})
    except ToolExecutionError as e:
        return {"error": str(e)}
