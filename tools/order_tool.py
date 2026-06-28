"""
tools/order_tool.py — LangChain Tools for The Flame & Fork.

Two tools are defined here:
  • PlaceOrderTool  — validates items, resolves prices, writes to SQLite
  • GetOrderTool    — fetches an existing order by ID from SQLite
"""
from __future__ import annotations

from typing import Any, List, Optional, Type
from pydantic import BaseModel, Field
from langchain.tools import BaseTool

from utils.database import create_order, get_order


# ── Canonical price map ───────────────────────────────────────────────────────
# Must stay in sync with generate_menu_pdf.py
PRICE_MAP: dict[str, float] = {
    # Burgers
    "Classic Veg Burger"         : 149.0,
    "Paneer Tikka Burger"        : 199.0,
    "Aloo Tikki Burger"          : 139.0,
    "Cheese Burst Burger"        : 219.0,
    "Mexican Veg Burger"         : 209.0,
    # Pizzas
    "Margherita Pizza"           : 249.0,
    "Farmhouse Pizza"            : 329.0,
    "Paneer Tikka Pizza"         : 359.0,
    "Veggie Supreme Pizza"       : 349.0,
    "Cheese Burst Pizza"         : 389.0,
    # Pasta
    "White Sauce Pasta"          : 249.0,
    "Red Sauce Pasta"            : 239.0,
    "Pink Sauce Pasta"           : 259.0,
    "Pesto Pasta"                : 279.0,
    "Cheesy Baked Pasta"         : 299.0,
    # Rice & Indian Meals
    "Veg Biryani"                : 279.0,
    "Paneer Biryani"             : 319.0,
    "Jeera Rice"                 : 149.0,
    "Veg Pulao"                  : 219.0,
    "Dal Khichdi"                : 199.0,
    # Pav Bhaji & Street Food
    "Classic Pav Bhaji"          : 179.0,
    "Cheese Pav Bhaji"           : 229.0,
    "Jain Pav Bhaji"             : 199.0,
    "Extra Butter Pav Bhaji"     : 219.0,
    "Tawa Pulao"                 : 229.0,
    # Starters & Sides
    "French Fries"               : 129.0,
    "Peri Peri Fries"            : 149.0,
    "Cheese Garlic Bread"        : 179.0,
    "Veg Spring Rolls"           : 199.0,
    "Paneer Tikka"               : 299.0,
    "Hara Bhara Kabab"           : 229.0,
    # Drinks
    "Fresh Lime Soda"            : 89.0,
    "Cold Coffee"                : 169.0,
    "Mango Shake"                : 179.0,
    "Chocolate Shake"            : 189.0,
    "Oreo Shake"                 : 199.0,
    "Masala Chaas"               : 79.0,
    "Mineral Water"              : 30.0,
    "Soft Drinks"                : 60.0,
    # Desserts
    "Gulab Jamun (2 pcs)"        : 99.0,
    "Brownie with Ice Cream"     : 199.0,
    "Chocolate Lava Cake"        : 179.0,
    "Kulfi"                      : 119.0,
    "Falooda"                    : 199.0,
    "Ice Cream Sundae"           : 169.0,
}


def _resolve_item(name: str) -> Optional[tuple[str, float]]:
    """
    Case-insensitive fuzzy lookup against PRICE_MAP.
    Returns (canonical_name, price) or None if no match.
    """
    needle = name.lower().strip()
    # Exact match first
    for canon, price in PRICE_MAP.items():
        if needle == canon.lower():
            return canon, price
    # Substring match
    for canon, price in PRICE_MAP.items():
        if needle in canon.lower() or canon.lower() in needle:
            return canon, price
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  Tool 1 — PlaceOrderTool
# ─────────────────────────────────────────────────────────────────────────────
class _PlaceOrderInput(BaseModel):
    items: List[dict] = Field(
        ...,
        description=(
            "List of items to order. Each element must be a dict with keys "
            '"item_name" (str) and "quantity" (int ≥ 1). '
            'Example: [{"item_name": "Margherita", "quantity": 2}, '
            '{"item_name": "Milkshake", "quantity": 1}]'
        ),
    )
    customer: str = Field(
        default="Guest",
        description="The customer's name (optional, default 'Guest').",
    )
    notes: str = Field(
        default="",
        description="Any special instructions, e.g. 'extra spicy, no onions'.",
    )


class PlaceOrderTool(BaseTool):
    """Custom tool: validates items, resolves prices, writes order to SQLite."""

    name: str        = "place_order"
    description: str = (
        "Use this tool to place (save) a confirmed food order to the database. "
        "Provide a list of items with their names and quantities. "
        "The tool resolves prices automatically and returns a formatted order confirmation."
    )
    args_schema: Type[BaseModel] = _PlaceOrderInput

    # ------------------------------------------------------------------
    def _run(
        self,
        items: List[dict],
        customer: str = "Guest",
        notes: str = "",
    ) -> str:
        resolved   : list[dict] = []
        unresolved : list[str]  = []

        for entry in items:
            raw_name = str(entry.get("item_name", "")).strip()
            quantity = max(1, int(entry.get("quantity", 1)))
            match    = _resolve_item(raw_name)

            if match:
                canon_name, unit_price = match
                resolved.append({
                    "item_name" : canon_name,
                    "quantity"  : quantity,
                    "unit_price": unit_price,
                })
            else:
                unresolved.append(raw_name)

        if unresolved:
            return (
                "The following items were **not found** on our menu and could not be ordered:\n"
                + "\n".join(f"  • {n}" for n in unresolved)
                + "\n\nPlease ask the customer to choose from the available menu items."
            )

        if not resolved:
            return "No valid items were provided. Please specify at least one menu item."

        result = create_order(items=resolved, customer=customer, notes=notes)

        lines = [
            f"  • {i['item_name']}  ×{i['quantity']}  "
            f"(₹{i['unit_price']:.2f} ea) = ₹{i['quantity'] * i['unit_price']:.2f}"
            for i in resolved
        ]
        return (
            f"**Order #{result['order_id']} confirmed!**\n\n"
            f"Customer : {result['customer']}\n"
            f"Items    :\n" + "\n".join(lines) + "\n\n"
            f"**Total  : ₹{result['total']:.2f}**\n"
            f"Placed at: {result['created_at']}\n"
            f"Status   : {result['status']}"
        )

    async def _arun(self, *args: Any, **kwargs: Any) -> str:  # async support
        return self._run(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
#  Tool 2 — GetOrderTool
# ─────────────────────────────────────────────────────────────────────────────
class _GetOrderInput(BaseModel):
    order_id: int = Field(..., description="The numeric order ID to look up.")


class GetOrderTool(BaseTool):
    """Custom tool: retrieves a single order from SQLite by order ID."""

    name: str        = "get_order"
    description: str = (
        "Use this tool to look up the status and details of an existing order "
        "using its order ID number."
    )
    args_schema: Type[BaseModel] = _GetOrderInput

    # ------------------------------------------------------------------
    def _run(self, order_id: int) -> str:
        order = get_order(order_id)
        if order is None:
            return f"Order #{order_id} was not found in the database."

        lines = [
            f"  • {i['item_name']}  ×{i['quantity']}  = ₹{i['subtotal']:.2f}"
            for i in order["items"]
        ]
        notes_line = f"\nNotes    : {order['notes']}" if order.get("notes") else ""
        return (
            f"**Order #{order['id']}**\n\n"
            f"Customer : {order['customer']}\n"
            f"Items    :\n" + "\n".join(lines) + "\n\n"
            f"Total    : ₹{order['total']:.2f}\n"
            f"Status   : {order['status']}\n"
            f"Placed   : {order['created_at']}"
            + notes_line
        )

    async def _arun(self, *args: Any, **kwargs: Any) -> str:
        return self._run(*args, **kwargs)
