from google.genai import types


def _schema(type_: types.Type, description: str, enum: list[str] | None = None) -> types.Schema:
    kwargs = {"type": type_, "description": description}
    if enum:
        kwargs["enum"] = enum
    return types.Schema(**kwargs)


def _obj(properties: dict[str, types.Schema], required: list[str] | None = None) -> types.Schema:
    return types.Schema(type=types.Type.OBJECT, properties=properties, required=required or [])


# Note what's NOT here: none of these take a user_id, customer_id, or
# anything that would let the model specify whose data to read or write.
# The caller is always current_user from the JWT — see app/llm/tool_executor.py.
TOOL_DECLARATIONS = [
    types.FunctionDeclaration(
        name="get_profile",
        description="Get the authenticated customer's own profile: name, email, phone, preferred language.",
        parameters=_obj({}),
    ),
    types.FunctionDeclaration(
        name="list_addresses",
        description="List the customer's saved delivery addresses.",
        parameters=_obj({}),
    ),
    types.FunctionDeclaration(
        name="add_address",
        description=(
            "Save a new delivery address for the customer. Note: this does NOT geocode the address — "
            "it has no precise location on file until updated with one separately, so it works "
            "immediately for pickup but delivery-range checks (get_nearest_outlet, checkout) won't "
            "work for it yet. Mention this if the customer's intent is delivery to a brand-new address."
        ),
        parameters=_obj(
            {
                "label": _schema(types.Type.STRING, "Short label, e.g. 'Home', 'Office'"),
                "address_text": _schema(types.Type.STRING, "Full address text"),
                "is_default": _schema(types.Type.BOOLEAN, "Whether this becomes the default address"),
            },
            required=["label", "address_text"],
        ),
    ),
    types.FunctionDeclaration(
        name="update_address",
        description="Update the label, text, or default flag of one of the customer's saved addresses.",
        parameters=_obj(
            {
                "address_id": _schema(types.Type.STRING, "UUID of the address to update"),
                "label": _schema(types.Type.STRING, "New label, if changing it"),
                "address_text": _schema(types.Type.STRING, "New address text, if changing it"),
                "is_default": _schema(types.Type.BOOLEAN, "Whether this becomes the default address"),
            },
            required=["address_id"],
        ),
    ),
    types.FunctionDeclaration(
        name="remove_address",
        description=(
            "Delete one of the customer's saved addresses. Fails if it's linked to an existing order — "
            "that's expected, explain it rather than treating it as a bug."
        ),
        parameters=_obj({"address_id": _schema(types.Type.STRING, "UUID of the address to delete")}, required=["address_id"]),
    ),
    types.FunctionDeclaration(
        name="list_outlets",
        description="List all active outlet (butcher shop) locations.",
        parameters=_obj({}),
    ),
    types.FunctionDeclaration(
        name="get_nearest_outlet",
        description=(
            "Find the outlet nearest to one of the customer's saved addresses, and whether it can "
            "actually deliver there. Check the returned 'in_range' field — false means even the "
            "closest outlet can't reach that address (Local Butcher only serves within Hyderabad "
            "right now); don't proceed with a delivery order if it's false."
        ),
        parameters=_obj(
            {"address_id": _schema(types.Type.STRING, "UUID of the customer's saved address")},
            required=["address_id"],
        ),
    ),
    types.FunctionDeclaration(
        name="list_products",
        description=(
            "List available products, optionally filtered by category. Valid categories: "
            "'Poultry', 'Meat', 'Seafood', 'Farm Eggs'. If unsure a term maps to one of these "
            "(or the customer's query doesn't cleanly fit one), omit the filter and list everything."
        ),
        parameters=_obj({"category": _schema(types.Type.STRING, "Optional category filter — must be one of the valid categories listed above")}),
    ),
    types.FunctionDeclaration(
        name="check_product_availability",
        description=(
            "Check whether a product is in stock at a given outlet for a given quantity. If it isn't, "
            "this also finds the nearest OTHER outlet that has enough, and whether that outlet can "
            "deliver to the customer's address — use this instead of just reporting 'out of stock'."
        ),
        parameters=_obj(
            {
                "product_id": _schema(types.Type.STRING, "UUID of the product"),
                "outlet_id": _schema(types.Type.STRING, "UUID of the outlet to check first"),
                "quantity": _schema(types.Type.NUMBER, "Requested quantity"),
                "address_id": _schema(
                    types.Type.STRING,
                    "Optional UUID of the customer's address, used to find the nearest alternate outlet",
                ),
            },
            required=["product_id", "outlet_id", "quantity"],
        ),
    ),
    types.FunctionDeclaration(
        name="get_cart",
        description="Get the customer's current cart contents and subtotal.",
        parameters=_obj({}),
    ),
    types.FunctionDeclaration(
        name="add_to_cart",
        description="Add a product to the customer's cart (or increase quantity if already present).",
        parameters=_obj(
            {
                "product_id": _schema(types.Type.STRING, "UUID of the product"),
                "quantity": _schema(types.Type.NUMBER, "Quantity to add"),
            },
            required=["product_id", "quantity"],
        ),
    ),
    types.FunctionDeclaration(
        name="update_cart_item",
        description="Change the quantity of an item already in the customer's cart.",
        parameters=_obj(
            {
                "item_id": _schema(types.Type.STRING, "UUID of the cart item"),
                "quantity": _schema(types.Type.NUMBER, "New quantity"),
            },
            required=["item_id", "quantity"],
        ),
    ),
    types.FunctionDeclaration(
        name="remove_from_cart",
        description="Remove an item from the customer's cart.",
        parameters=_obj(
            {"item_id": _schema(types.Type.STRING, "UUID of the cart item")}, required=["item_id"]
        ),
    ),
    types.FunctionDeclaration(
        name="checkout",
        description="Place an order from everything currently in the customer's cart.",
        parameters=_obj(
            {
                "outlet_id": _schema(types.Type.STRING, "UUID of the outlet fulfilling the order"),
                "fulfillment_type": _schema(
                    types.Type.STRING, "Either 'delivery' or 'pickup'", enum=["delivery", "pickup"]
                ),
                "address_id": _schema(
                    types.Type.STRING, "UUID of the delivery address — required when fulfillment_type is 'delivery'"
                ),
            },
            required=["outlet_id", "fulfillment_type"],
        ),
    ),
    types.FunctionDeclaration(
        name="list_orders",
        description="List the customer's past and current orders.",
        parameters=_obj({}),
    ),
    types.FunctionDeclaration(
        name="get_order",
        description="Get full details and current status of one order.",
        parameters=_obj({"order_id": _schema(types.Type.STRING, "UUID of the order")}, required=["order_id"]),
    ),
    types.FunctionDeclaration(
        name="cancel_order",
        description="Cancel an order, if it's still in a cancellable state (pending or confirmed).",
        parameters=_obj({"order_id": _schema(types.Type.STRING, "UUID of the order")}, required=["order_id"]),
    ),
    types.FunctionDeclaration(
        name="update_order_item",
        description="Change the quantity of an item in an existing order, if the order is still modifiable.",
        parameters=_obj(
            {
                "order_id": _schema(types.Type.STRING, "UUID of the order"),
                "item_id": _schema(types.Type.STRING, "UUID of the order item"),
                "quantity": _schema(types.Type.NUMBER, "New quantity"),
            },
            required=["order_id", "item_id", "quantity"],
        ),
    ),
    types.FunctionDeclaration(
        name="remove_order_item",
        description=(
            "Remove an item from an existing order, if the order is still modifiable. "
            "Cannot remove the last remaining item — cancel the order instead."
        ),
        parameters=_obj(
            {
                "order_id": _schema(types.Type.STRING, "UUID of the order"),
                "item_id": _schema(types.Type.STRING, "UUID of the order item"),
            },
            required=["order_id", "item_id"],
        ),
    ),
    types.FunctionDeclaration(
        name="reorder_previous_order",
        description=(
            "Add all items from a previous order back into the customer's current cart, so they "
            "can quickly repeat a past order (\"reorder\", \"same as last time\", \"order what I "
            "got last Sunday\"). Uses the most recent order if no order_id is given."
        ),
        parameters=_obj(
            {"order_id": _schema(types.Type.STRING, "Optional UUID of the order to repeat — defaults to the most recent order")}
        ),
    ),
    types.FunctionDeclaration(
        name="search_knowledge_base",
        description=(
            "Search Local Butcher's general policy and support knowledge base — how the service "
            "works, cancellations, refunds, the wallet/cashback program, privacy and data, account "
            "deletion, contacting support. Use this for general 'how does X work' questions, NOT for "
            "product info, prices, stock, or the customer's own cart/orders (use the relevant tool "
            "for those instead). Does not know real-time inventory, live pricing, or a specific "
            "order's live status."
        ),
        parameters=_obj(
            {"query": _schema(types.Type.STRING, "The customer's question, in their own words")},
            required=["query"],
        ),
    ),
    types.FunctionDeclaration(
        name="create_support_ticket",
        description="File a support ticket for a complaint or issue, optionally linked to a specific order.",
        parameters=_obj(
            {
                "issue_text": _schema(types.Type.STRING, "Description of the issue"),
                "order_id": _schema(types.Type.STRING, "Optional UUID of the related order"),
            },
            required=["issue_text"],
        ),
    ),
]

TOOLS = types.Tool(function_declarations=TOOL_DECLARATIONS)
