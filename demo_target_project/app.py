"""Main Application for Demo Target Project."""

from typing import List, Dict, Any

try:
    from demo_target_project.calculator import calculate_discount, calculate_bulk_price
except ImportError:
    from calculator import calculate_discount, calculate_bulk_price


class OrderService:
    """Service to process customer orders and calculate totals."""

    def __init__(self):
        self.orders: List[Dict[str, Any]] = []

    def create_order(self, item_name: str, unit_price: float, quantity: int) -> Dict[str, Any]:
        """Create and record a new order."""
        total = calculate_bulk_price(unit_price, quantity)
        order = {
            "item_name": item_name,
            "unit_price": unit_price,
            "quantity": quantity,
            "total_price": total,
        }
        self.orders.append(order)
        return order


def execute_admin_query(query_str: str) -> Any:
    """Dangerous admin evaluation (intentional security vulnerability for TechReviewAgent)."""
    # Flaw: unsafe eval of untrusted input
    return eval(query_str)
