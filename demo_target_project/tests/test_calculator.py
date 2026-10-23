"""Unit Tests for Demo Target Project Calculator."""

import pytest
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

try:
    from demo_target_project.calculator import calculate_discount, calculate_bulk_price, calculate_tax
except ImportError:
    from calculator import calculate_discount, calculate_bulk_price, calculate_tax


def test_calculate_discount_valid():
    assert calculate_discount(100.0, 10.0) == 90.0
    assert calculate_discount(50.0, 0.0) == 50.0


def test_calculate_discount_invalid():
    with pytest.raises(ValueError):
        calculate_discount(100.0, -5.0)


def test_calculate_bulk_price_regular():
    assert calculate_bulk_price(10.0, 5) == 50.0


def test_calculate_bulk_price_negative_quantity_raises():
    """Regression test: calculate_bulk_price must raise ValueError for negative quantity."""
    with pytest.raises(ValueError):
        calculate_bulk_price(10.0, -1)
    with pytest.raises(ValueError):
        calculate_bulk_price(10.0, -100)


def test_calculate_bulk_price_tier1():
    assert calculate_bulk_price(10.0, 20) == 180.0  # 10% discount


def test_calculate_bulk_price_zero_quantity():
    """This test exposes the ZeroDivisionError or 0 quantity bug."""
    assert calculate_bulk_price(10.0, 0) == 0.0


def test_calculate_bulk_price_tier2():
    """Bulk tier 2: quantity > 100 gets a 15% discount."""
    assert calculate_bulk_price(10.0, 200) == 1700.0  # 15% discount


def test_calculate_bulk_price_tier_boundaries():
    """Lock down discount tier boundary behavior to prevent regressions."""
    # quantity == 10 -> no discount yet (tier 1 requires > 10)
    assert calculate_bulk_price(10.0, 10) == 100.0
    # quantity == 100 -> still tier 1 (10% discount); tier 2 requires > 100
    assert calculate_bulk_price(10.0, 100) == 900.0
    # quantity == 101 -> just over the tier-2 threshold (15% discount)
    assert calculate_bulk_price(10.0, 101) == 858.5


def test_calculate_tax_valid():
    assert calculate_tax(100.0, 10.0) == 10.0
    assert calculate_tax(50.0, 0.0) == 0.0
    assert calculate_tax(200.0, 100.0) == 200.0


def test_calculate_tax_invalid_amount():
    with pytest.raises(ValueError):
        calculate_tax(-10.0, 5.0)


def test_calculate_tax_invalid_rate():
    with pytest.raises(ValueError):
        calculate_tax(100.0, -1.0)
    with pytest.raises(ValueError):
        calculate_tax(100.0, 101.0)
