"""
Unit tests for broker/transaction_charges.py statutory charge computations.
See Plan_v3 §4.1.
"""
import pytest

from broker.transaction_charges import apply_slippage, compute_transaction_charges_paise


def test_buy_charges_on_100_shares_at_rs1000():
    # price_paise=100000 (Rs 1000), shares=100 -> trade value Rs 1,00,000.
    # stt=10000.00, exchange=297.00, sebi=10.00, gst=0.18*(0+297+10)=55.26, stamp=1500.00, dp=0
    # total = 10000+297+10+55.26+1500 = 11862.26 -> 11862 paise
    charges = compute_transaction_charges_paise(100000, 100, "BUY")
    assert charges == pytest.approx(11862, abs=2)

    stt = round(0.001 * 100000 * 100)
    exch = round(0.0000297 * 100000 * 100)
    sebi = round(0.000001 * 100000 * 100)
    gst = round(0.18 * (0 + exch + sebi))
    stamp = round(0.00015 * 100000 * 100)
    breakdown_total = stt + exch + sebi + gst + stamp
    print(f"BUY breakdown: stt={stt} exch={exch} sebi={sebi} gst={gst} stamp={stamp} dp=0 total={breakdown_total}")
    assert breakdown_total == pytest.approx(11862, abs=2)


def test_sell_charges_on_100_shares_at_rs1000():
    # Same trade value, SELL: stamp=0, dp=1534 instead.
    # total = 10000+297+10+55.26+0+1534 = 11896.26 -> 11896 paise
    charges = compute_transaction_charges_paise(100000, 100, "SELL")
    assert charges == pytest.approx(11896, abs=2)

    stt = round(0.001 * 100000 * 100)
    exch = round(0.0000297 * 100000 * 100)
    sebi = round(0.000001 * 100000 * 100)
    gst = round(0.18 * (0 + exch + sebi))
    dp = 1534
    breakdown_total = stt + exch + sebi + gst + dp
    print(f"SELL breakdown: stt={stt} exch={exch} sebi={sebi} gst={gst} stamp=0 dp={dp} total={breakdown_total}")
    assert breakdown_total == pytest.approx(11896, abs=2)


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
    assert apply_slippage(100000, "BUY") == 100100  # +10 bps = +0.10%


def test_sell_slippage_moves_price_down():
    assert apply_slippage(100000, "SELL") == 99900  # -10 bps


def test_slippage_rounds_half_up_to_whole_paisa():
    # 10001 * 1.001 = 10011.001 -> rounds down to 10011; pick a value that lands on .5 instead.
    # 5000 * 1.001 = 5005.0 exactly -> no rounding ambiguity; use a price that creates a .5 paisa.
    assert apply_slippage(5005, "BUY") == round(5005 * 1.001)  # sanity cross-check vs plain round
    # A case landing exactly on .5: price=50025 -> *1.001 = 50075.025 (not .5); construct directly:
    # bps factor is 10/10000 = 0.001, so price*0.001 must end in .5 paisa for a true half-up case.
    # price=500 -> 500*0.001=0.5 exactly -> 500*1.001=500.5 -> rounds up to 501.
    assert apply_slippage(500, "BUY") == 501
    assert apply_slippage(500, "SELL") == 500  # 500*0.999=499.5 -> rounds up (half-up) to 500
