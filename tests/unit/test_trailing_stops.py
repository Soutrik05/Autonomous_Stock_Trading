"""
Unit tests for broker-level graduated trailing stop mechanics.
"""

from broker.trailing import compute_graduated_stop


def test_graduated_stop_sub_1r():
    # Entry 100,00 (10000 paise), initial stop 95,00 (9500 paise), risk = 500 paise
    # Peak price 103,00 (10300 paise) -> peak gain = 300 (< 1.0x risk 500)
    stop = compute_graduated_stop(
        avg_entry_price_paise=10000,
        current_stop_paise=9500,
        initial_stop_paise=9500,
        peak_price_paise=10300,
    )
    assert stop == 9500  # unadjusted


def test_graduated_stop_1r_breakeven_ratchet():
    # Peak price 106,00 (10600 paise) -> peak gain = 600 (>= 1.0x risk 500, < 2.0x risk 1000)
    stop = compute_graduated_stop(
        avg_entry_price_paise=10000,
        current_stop_paise=9500,
        initial_stop_paise=9500,
        peak_price_paise=10600,
    )
    assert stop == 10000  # ratcheted to breakeven


def test_graduated_stop_2r_lock_50_pct():
    # Peak price 112,00 (11200 paise) -> peak gain = 1200 (>= 2.0x risk 1000, < 3.0x risk 1500)
    # Locked gain = 50% of 1200 = 600 -> stop = 10000 + 600 = 10600 (+1.2R)
    stop = compute_graduated_stop(
        avg_entry_price_paise=10000,
        current_stop_paise=10000,
        initial_stop_paise=9500,
        peak_price_paise=11200,
    )
    assert stop == 10600


def test_graduated_stop_3r_lock_70_pct():
    # Peak price 118,00 (11800 paise) -> peak gain = 1800 (>= 3.0x risk 1500)
    # Locked gain = 70% of 1800 = 1260 -> stop = 10000 + 1260 = 11260 (+2.52R)
    stop = compute_graduated_stop(
        avg_entry_price_paise=10000,
        current_stop_paise=10600,
        initial_stop_paise=9500,
        peak_price_paise=11800,
    )
    assert stop == 11260


def test_graduated_stop_monotonic_never_decreases():
    # If price pulls back, current stop at 11260 must NEVER decrease
    stop = compute_graduated_stop(
        avg_entry_price_paise=10000,
        current_stop_paise=11260,
        initial_stop_paise=9500,
        peak_price_paise=10800,  # lower peak passed
    )
    assert stop == 11260


def test_graduated_stop_fallback_risk():
    # When initial_stop_paise is None and current_stop is at breakeven (10000)
    # Risk defaults to 2.5% of 10000 = 250 paise
    # Peak price 10800 -> peak gain 800 (>= 3.0x 250 = 750) -> lock 70% of 800 = 560
    stop = compute_graduated_stop(
        avg_entry_price_paise=10000,
        current_stop_paise=10000,
        initial_stop_paise=None,
        peak_price_paise=10800,
    )
    assert stop == 10560


def test_graduated_stop_peak_below_entry_stays_unadjusted():
    # Trade entered at 10000 with stop at 9500. Peak was 9800 (underwater trade).
    stop = compute_graduated_stop(
        avg_entry_price_paise=10000,
        current_stop_paise=9500,
        initial_stop_paise=9500,
        peak_price_paise=9800,
    )
    assert stop == 9500


def test_graduated_stop_1_5r_lock_35_pct():
    # Entry 100,00 (10000 paise), risk 500 paise.
    # Peak price 108,00 (10800 paise) -> peak gain = 800 (>= 1.5x risk 750, < 2.0x risk 1000)
    # Locked gain = 35% of 800 = 280 -> stop = 10000 + 280 = 10280
    stop = compute_graduated_stop(
        avg_entry_price_paise=10000,
        current_stop_paise=10000,
        initial_stop_paise=9500,
        peak_price_paise=10800,
    )
    assert stop == 10280


def test_graduated_stop_absolute_10pct_lock():
    # Wide stop investor (RJ): entry 100,00, initial stop 86,00 (risk 1400 paise = 14%)
    # Peak price 113,00 (11300 paise) -> peak gain = 1300 (only 0.93R, but >= 10% absolute gain)
    # Locked gain = 35% of 1300 = 455 -> stop = 10000 + 455 = 10455
    stop = compute_graduated_stop(
        avg_entry_price_paise=10000,
        current_stop_paise=8600,
        initial_stop_paise=8600,
        peak_price_paise=11300,
    )
    assert stop == 10455


def test_graduated_stop_invalid_initial_stop_falls_back_to_current_or_default():
    # 1. When initial_stop is invalid (> entry), but current_stop is valid (9500), uses current_stop risk (500)
    # Peak gain 600 >= 1x 500 (< 1.5x 750) -> ratchets to breakeven (10000)
    stop1 = compute_graduated_stop(
        avg_entry_price_paise=10000,
        current_stop_paise=9500,
        initial_stop_paise=10500,
        peak_price_paise=10600,
    )
    assert stop1 == 10000

    # 2. When both initial_stop and current_stop are invalid (> entry), falls back to 2.5% default risk (250)
    # Peak gain 800 >= 3x 250 -> lock 70% of 800 = 560 -> 10560
    stop2 = compute_graduated_stop(
        avg_entry_price_paise=10000,
        current_stop_paise=10500,
        initial_stop_paise=10500,
        peak_price_paise=10800,
    )
    assert stop2 == 10560
