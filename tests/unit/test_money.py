"""
Unit tests for core/money.py paise/rupee conversion helpers.
See Plan_v3 Core Architectural Principles 7.
"""

from decimal import Decimal

import pytest

from core.money import format_rupees, paise_to_rupees, rupees_to_paise


def test_rupees_to_paise_basic():
    assert rupees_to_paise("940.50") == 94050
    assert rupees_to_paise(940.50) == 94050
    assert rupees_to_paise(100) == 10000


def test_rupees_to_paise_rounds_half_up():
    assert rupees_to_paise("1.005") == 101  # 100.5 paise -> 101


def test_paise_to_rupees_basic():
    assert paise_to_rupees(94050) == Decimal("940.50")
    assert paise_to_rupees(0) == Decimal("0.00")


def test_paise_to_rupees_requires_int():
    with pytest.raises(TypeError):
        paise_to_rupees(940.5)


def test_format_rupees():
    assert format_rupees(94050) == "₹940.50"


def test_round_trip_is_exact():
    for rupees in ["0.00", "1.00", "940.50", "99999.99"]:
        paise = rupees_to_paise(rupees)
        assert paise_to_rupees(paise) == Decimal(rupees)
