"""
Computes statutory charges (STT, exchange, SEBI, stamp duty, GST, DP) in integer paise per fill,
and applies slippage to a fill price. All inputs/outputs are integer paise; each function rounds
exactly once.
See Plan_v3 §4.1.
"""
from decimal import ROUND_HALF_UP, Decimal

from settings import settings


def compute_transaction_charges_paise(price_paise: int, shares: int, side: str) -> int:
    """Exact Plan_v3 §4.1 formula. `side` is 'BUY' or 'SELL'. Stamp duty is BUY-only, DP
    charges are SELL-only; both ride on GST only via exchange+SEBI+brokerage, not themselves."""
    trade_value_paise = price_paise * shares
    if trade_value_paise <= 0:
        return 0

    stt = settings.STT_RATE * trade_value_paise
    exchange = settings.EXCHANGE_TURNOVER_RATE * trade_value_paise
    sebi = settings.SEBI_FEE_RATE * trade_value_paise
    brokerage = settings.BROKERAGE_PAISE  # already in paise, not a rate
    gst = settings.GST_RATE * (brokerage + exchange + sebi)
    stamp = settings.STAMP_DUTY_RATE * trade_value_paise if side == "BUY" else 0.0
    dp = settings.DP_CHARGES_PAISE if side == "SELL" else 0

    total = stt + exchange + sebi + gst + stamp + dp
    return int(round(total))


def apply_slippage(price_paise: int, side: str) -> int:
    """BUY fills at price x (1 + SLIPPAGE_BPS/10000); SELL fills at price x (1 - .../10000).
    Rounded half-up to the nearest whole paisa."""
    bps = Decimal(settings.SLIPPAGE_BPS) / Decimal(10000)
    factor = Decimal(1) + bps if side == "BUY" else Decimal(1) - bps
    return int((Decimal(price_paise) * factor).to_integral_value(rounding=ROUND_HALF_UP))
