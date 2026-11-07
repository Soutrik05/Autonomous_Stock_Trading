"""
Graduated trailing stop mechanics.
Enforces broker-level profit locking to eliminate GAVE_BACK_PROFIT alpha leak:
- Peak gain < 1.0x initial risk: keep initial stop
- Peak gain >= 1.0x initial risk: breakeven ratchet (raise stop to avg entry price)
- Peak gain >= 2.0x initial risk: lock in 50% of peak gain (stop = entry + 0.50 * peak_gain)
- Peak gain >= 3.0x initial risk: lock in 70% of peak gain (stop = entry + 0.70 * peak_gain)

All stops ratchet monotonically upwards (never decrease).
"""


def compute_graduated_stop(
    avg_entry_price_paise: int,
    current_stop_paise: int,
    initial_stop_paise: int | None,
    peak_price_paise: int,
) -> int:
    """
    Computes the ratcheted stop price in paise based on graduated risk multiples.
    """
    if avg_entry_price_paise <= 0:
        return current_stop_paise

    # Determine original risk distance
    if initial_stop_paise and 0 < initial_stop_paise < avg_entry_price_paise:
        initial_risk = avg_entry_price_paise - initial_stop_paise
    elif current_stop_paise and 0 < current_stop_paise < avg_entry_price_paise:
        initial_risk = avg_entry_price_paise - current_stop_paise
    else:
        # Fallback to standard 2.5% risk distance
        initial_risk = max(1, int(avg_entry_price_paise * 0.025))

    initial_risk = max(1, initial_risk)
    peak_gain = max(0, peak_price_paise - avg_entry_price_paise)

    if peak_gain >= 3.0 * initial_risk:
        candidate_stop = avg_entry_price_paise + int(peak_gain * 0.70)
    elif peak_gain >= 2.0 * initial_risk:
        candidate_stop = avg_entry_price_paise + int(peak_gain * 0.50)
    elif peak_gain >= 1.0 * initial_risk:
        candidate_stop = avg_entry_price_paise
    else:
        candidate_stop = current_stop_paise

    return max(current_stop_paise, candidate_stop)
