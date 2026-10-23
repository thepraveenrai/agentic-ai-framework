"""Calculator and Pricing Engine for Demo Target Project."""

from typing import Dict, Any


def calculate_discount(price: float, discount_percent: float) -> float:
    """Calculate discounted price after applying percentage."""
    if discount_percent < 0 or discount_percent > 100:
        raise ValueError("Discount percent must be between 0 and 100")
    return price * (1.0 - (discount_percent / 100.0))


def calculate_bulk_price(unit_price: float, quantity: int) -> float:
    if quantity < 0:
        raise ValueError("Quantity must be non-negative")
    if quantity > 100:
        return unit_price * quantity * 0.85
    elif quantity > 10:
        return unit_price * quantity * 0.90
    return unit_price * quantity


def calculate_tax(amount: float, rate: float) -> float:
    """Calculate the tax amount for a given pre-tax amount and tax rate.

    Args:
        amount: The pre-tax amount (must be non-negative).
        rate: The tax rate as a percentage (must be between 0 and 100).

    Returns:
        The tax amount computed as amount * (rate / 100.0).

    Raises:
        ValueError: If amount is negative or rate is outside [0, 100].
    """
    if amount < 0:
        raise ValueError("Amount must be non-negative")
    if rate < 0 or rate > 100:
        raise ValueError("Tax rate must be between 0 and 100")
    return amount * (rate / 100.0)
