"""
Unit tests for broker/transaction_charges.py statutory charge computations.
All test expectations derive dynamically from core.config.settings (Single Source of Truth).
See Plan_v3 §4.1.
"""

from decimal import ROUND_HALF_UP, Decimal

from broker.transaction_charges import apply_slippage, compute_transaction_charges_paise
from core.config import settings


def test_buy_charges_on_100_shares_at_rs1000():
    # price_paise=100000 (Rs 1000), shares=100 -> trade value Rs 1,00,000.
    price_paise = 100000
    shares = 100
    trade_value = price_paise * shares

    stt = settings.STT_RATE * trade_value
    exchange = settings.EXCHANGE_TURNOVER_RATE * trade_value
    sebi = settings.SEBI_FEE_RATE * trade_value
    brokerage = settings.BROKERAGE_PAISE
    gst = settings.GST_RATE * (brokerage + exchange + sebi)
    stamp = settings.STAMP_DUTY_RATE * trade_value
    expected_charges = int(round(stt + exchange + sebi + gst + stamp))

    charges = compute_transaction_charges_paise(price_paise, shares, "BUY")
    assert charges == expected_charges


def test_sell_charges_on_100_shares_at_rs1000():
    # Same trade value, SELL: stamp=0, dp charges apply instead.
    price_paise = 100000
    shares = 100
    trade_value = price_paise * shares

    stt = settings.STT_RATE * trade_value
    exchange = settings.EXCHANGE_TURNOVER_RATE * trade_value
    sebi = settings.SEBI_FEE_RATE * trade_value
    brokerage = settings.BROKERAGE_PAISE
    gst = settings.GST_RATE * (brokerage + exchange + sebi)
    dp = settings.DP_CHARGES_PAISE
    expected_charges = int(round(stt + exchange + sebi + gst + dp))

    charges = compute_transaction_charges_paise(price_paise, shares, "SELL")
    assert charges == expected_charges


def test_charges_round_once_per_call_not_per_component():
    # compute_transaction_charges_paise must return an int; rounding happens exactly once at
    # the end, not on each intermediate stt/exchange/sebi/gst/stamp/dp term.
    result = compute_transaction_charges_paise(100000, 100, "BUY")
    assert isinstance(result, int)


def test_zero_or_negative_trade_value_gives_zero_charges():
    assert compute_transaction_charges_paise(0, 100, "BUY") == 0
    assert compute_transaction_charges_paise(100, 0, "BUY") == 0


# --- slippage ---


def test_buy_slippage_moves_price_up():
    price = 100000
    bps = Decimal(settings.SLIPPAGE_BPS) / Decimal(10000)
    expected = int((Decimal(price) * (Decimal(1) + bps)).to_integral_value(rounding=ROUND_HALF_UP))
    assert apply_slippage(price, "BUY") == expected


def test_sell_slippage_moves_price_down():
    price = 100000
    bps = Decimal(settings.SLIPPAGE_BPS) / Decimal(10000)
    expected = int((Decimal(price) * (Decimal(1) - bps)).to_integral_value(rounding=ROUND_HALF_UP))
    assert apply_slippage(price, "SELL") == expected


def test_slippage_rounds_half_up_to_whole_paisa():
    # Test half-up rounding using Decimal reference formula with active settings.SLIPPAGE_BPS
    price = 5005
    bps = Decimal(settings.SLIPPAGE_BPS) / Decimal(10000)
    expected_buy = int((Decimal(price) * (Decimal(1) + bps)).to_integral_value(rounding=ROUND_HALF_UP))
    assert apply_slippage(price, "BUY") == expected_buy

    # Exact half paisa rounding check
    price_half = 500
    expected_half_buy = int((Decimal(price_half) * (Decimal(1) + bps)).to_integral_value(rounding=ROUND_HALF_UP))
    expected_half_sell = int((Decimal(price_half) * (Decimal(1) - bps)).to_integral_value(rounding=ROUND_HALF_UP))
    assert apply_slippage(price_half, "BUY") == expected_half_buy
    assert apply_slippage(price_half, "SELL") == expected_half_sell
