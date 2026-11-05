"""
Unit tests for the technical/ indicator functions used by FeatureSnapshot.
See Plan_v3 §2.2.
"""
import numpy as np
import pandas as pd
import pytest

from features.indicators import add_indicators, atr_wilder, ema, rsi_wilder


def make_df(closes, highs=None, lows=None, volumes=None):
    n = len(closes)
    closes = pd.Series(closes, dtype=float)
    highs = pd.Series(highs, dtype=float) if highs is not None else closes + 1
    lows = pd.Series(lows, dtype=float) if lows is not None else closes - 1
    volumes = pd.Series(volumes, dtype=float) if volumes is not None else pd.Series([10_000.0] * n)
    return pd.DataFrame({"open": closes, "high": highs, "low": lows, "close": closes, "volume": volumes})


def test_ema_of_a_constant_series_equals_the_constant():
    df = make_df([100.0] * 60)
    series = ema(df["close"], 20)
    assert series.dropna().unique().tolist() == pytest.approx([100.0])


def test_rsi_on_constant_price_is_neutral_50():
    df = make_df([100.0] * 60)
    series = rsi_wilder(df["close"], 14)
    assert series.dropna().round(6).unique().tolist() == pytest.approx([50.0])


def test_rsi_on_strictly_rising_series_approaches_100():
    closes = [100.0 + i for i in range(60)]
    df = make_df(closes)
    series = rsi_wilder(df["close"], 14)
    assert series.iloc[-1] > 99.0


def test_atr_hand_computed_example():
    # Day1 H=10 L=8 C=9 -> TR=2 (no prev close)
    # Day2 H=11 L=9 C=10, prev_close=9 -> TR=max(2, |11-9|=2, |9-9|=0)=2
    # Day3 H=12 L=9 C=11, prev_close=10 -> TR=max(3, |12-10|=2, |9-10|=1)=3
    # Day4 H=13 L=10 C=12, prev_close=11 -> TR=max(3, |13-11|=2, |10-11|=1)=3
    # Wilder ATR(period=2, alpha=0.5, adjust=False): y0=2 (hidden), y1=0.5*2+0.5*2=2,
    # y2=0.5*3+0.5*2=2.5, y3=0.5*3+0.5*2.5=2.75
    df = pd.DataFrame(
        {
            "open": [9.0, 10.0, 11.0, 12.0],
            "high": [10.0, 11.0, 12.0, 13.0],
            "low": [8.0, 9.0, 9.0, 10.0],
            "close": [9.0, 10.0, 11.0, 12.0],
            "volume": [1000.0, 1000.0, 1000.0, 1000.0],
        }
    )
    atr = atr_wilder(df, period=2)
    assert np.isnan(atr.iloc[0])
    assert atr.iloc[1] == pytest.approx(2.0)
    assert atr.iloc[2] == pytest.approx(2.5)
    assert atr.iloc[3] == pytest.approx(2.75)


def test_flat_price_guard_does_not_raise_and_neutralises_adx_and_volume_surge():
    df = make_df([100.0] * 300, volumes=[10_000.0] * 300)
    enriched = add_indicators(df)  # must not raise
    tail = enriched.iloc[-1]
    assert tail["adx_14"] == pytest.approx(0.0)
    assert tail["volume_surge"] == pytest.approx(1.0)
    assert np.isfinite(tail["adx_14"])
    assert np.isfinite(tail["volume_surge"])


def test_add_indicators_produces_every_expected_column():
    df = make_df([100.0 + i * 0.1 for i in range(260)])
    enriched = add_indicators(df)
    for col in [
        "ema_20", "ema_50", "ema_200", "ema_20_above_50", "rsi_14", "macd_hist",
        "atr_14", "adx_14", "volume_surge", "obv", "obv_slope_sign",
        "dist_52w_high_pct", "dist_52w_low_pct",
        "kaufman_er_20", "zscore_close_20", "parkinson_vol_ratio", "skew_60",
    ]:
        assert col in enriched.columns


def test_quant_indicators_values():
    # Strictly monotonically increasing series: KER should be exactly 1.0
    closes = [100.0 + i for i in range(100)]
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    df = make_df(closes, highs=highs, lows=lows)
    enriched = add_indicators(df)
    tail = enriched.iloc[-1]

    # KER on monotonic trend = 1.0
    assert tail["kaufman_er_20"] == pytest.approx(1.0, abs=1e-4)
    # Z-score on strong monotonic trend is positive
    assert tail["zscore_close_20"] > 1.5
    # Parkinson volatility is positive
    assert tail["parkinson_vol_ratio"] > 0.0
    # Skewness is finite
    assert np.isfinite(tail["skew_60"])


def test_dist_52w_high_is_never_positive_and_low_never_negative():
    df = make_df([100.0 + 10 * np.sin(i / 10) for i in range(260)])
    enriched = add_indicators(df)
    valid_high = enriched["dist_52w_high_pct"].dropna()
    valid_low = enriched["dist_52w_low_pct"].dropna()
    assert (valid_high <= 1e-9).all()
    assert (valid_low >= -1e-9).all()


def test_obv_slope_sign_is_minus_one_zero_or_plus_one():
    df = make_df([100.0 + i for i in range(40)])
    enriched = add_indicators(df)
    valid = enriched["obv_slope_sign"].dropna()
    assert set(valid.unique().tolist()) <= {-1.0, 0.0, 1.0}
