"""
Kinz Margin Guardian - price floor and headroom.

The margin engine answers "is today's margin below the threshold?". This module
answers the question a pricing decision needs first: "how low can the competitor
price go before this product alerts, and how much room is left today?"

The B2C price is the competitor price ``p`` and the B2B price is ``p * d``, so a
margin of at least ``t`` percent on both channels needs::

    p >= cogs / (1 - t/100)         (B2C)
    p >= cogs / ((1 - t/100) * d)   (B2B, the binding one whenever d < 1)

``src.margin_engine`` rounds margins to 2 decimals *before* comparing them with
the threshold, so its real alert boundary sits a few millimes below that exact
value. ``price_floor`` starts from the exact formula and then walks it to the
lowest millime price at which ``compute_product_margins`` itself raises no alert,
so the floor reported here and the alerts the pipeline sends can never disagree.

Functions:
  - price_floor: lowest competitor price (TND, to the millime) with no alert
  - headroom: how far today's competitor price can fall before it alerts
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from src.config import B2B_DISCOUNT_FACTOR, DEFAULT_ALERT_THRESHOLD_PCT
from src.margin_engine import compute_product_margins

MILLIME = 0.001  # smallest TND unit; floors are reported to this precision
_MAX_STEPS = 10_000  # safety bound on the walk; real cases need a handful


@dataclass(frozen=True)
class Headroom:
    """Today's position of one product against its price floor."""
    floor_tnd: float
    competitor_price_tnd: float
    headroom_tnd: float  # competitor price minus floor; negative = already alerting
    headroom_pct: float  # headroom as a % of today's competitor price
    below_floor: bool


def _validate(cogs: float, threshold_pct: float, b2b_discount: float) -> None:
    if not math.isfinite(cogs) or cogs <= 0:
        raise ValueError(f"COGS must be a positive number, got {cogs}")
    if not math.isfinite(threshold_pct) or not 0 <= threshold_pct < 100:
        raise ValueError(
            f"threshold must be at least 0 and below 100%, got {threshold_pct}: "
            "no price can reach a margin of 100% or more"
        )
    if not math.isfinite(b2b_discount) or b2b_discount <= 0:
        raise ValueError(f"B2B discount factor must be positive, got {b2b_discount}")


def _alerts(cogs: float, price: float, threshold_pct: float, b2b_discount: float) -> bool:
    r = compute_product_margins(0, "", cogs, price, threshold_pct, b2b_discount)
    return r.b2c_alert or r.b2b_alert


def exact_price_floor(
    cogs: float,
    threshold_pct: float = DEFAULT_ALERT_THRESHOLD_PCT,
    b2b_discount: float = B2B_DISCOUNT_FACTOR,
) -> float:
    """The unrounded floor from the formula, before the engine's rounding."""
    _validate(cogs, threshold_pct, b2b_discount)
    keep = 1 - threshold_pct / 100
    return max(cogs / keep, cogs / (keep * b2b_discount))


def price_floor(
    cogs: float,
    threshold_pct: float = DEFAULT_ALERT_THRESHOLD_PCT,
    b2b_discount: float = B2B_DISCOUNT_FACTOR,
) -> float:
    """Lowest competitor price, to the millime, at which neither channel alerts.

    Agrees with ``compute_product_margins`` by construction: the engine raises no
    alert at the returned price and raises one at the returned price minus 1 millime.

    Raises ``ValueError`` for a non-positive COGS or discount, or a threshold
    outside ``[0, 100)``.
    """
    exact = exact_price_floor(cogs, threshold_pct, b2b_discount)
    price = round(math.ceil(exact / MILLIME) * MILLIME, 3)

    steps = 0
    # Float safety: if the ceiling still alerts, move up until it doesn't.
    while _alerts(cogs, price, threshold_pct, b2b_discount):
        price = round(price + MILLIME, 3)
        steps += 1
        if steps > _MAX_STEPS:  # pragma: no cover - would mean the engine changed
            raise RuntimeError("price floor search did not converge")
    # Then down, while the engine's 2-decimal rounding still lets it through.
    while price > MILLIME:
        lower = round(price - MILLIME, 3)
        if _alerts(cogs, lower, threshold_pct, b2b_discount):
            break
        price = lower
        steps += 1
        if steps > _MAX_STEPS:  # pragma: no cover
            raise RuntimeError("price floor search did not converge")
    return price


def headroom(
    cogs: float,
    competitor_price: float,
    threshold_pct: float = DEFAULT_ALERT_THRESHOLD_PCT,
    b2b_discount: float = B2B_DISCOUNT_FACTOR,
) -> Headroom:
    """How far today's competitor price can fall before the product alerts."""
    if not math.isfinite(competitor_price) or competitor_price <= 0:
        raise ValueError(f"competitor price must be a positive number, got {competitor_price}")
    floor = price_floor(cogs, threshold_pct, b2b_discount)
    room = round(competitor_price - floor, 3)
    return Headroom(
        floor_tnd=floor,
        competitor_price_tnd=competitor_price,
        headroom_tnd=room,
        headroom_pct=round(room / competitor_price * 100, 2),
        # Ask the engine directly rather than compare with the floor, so a price
        # given to a finer precision than the millime is judged exactly as the
        # pipeline would judge it.
        below_floor=_alerts(cogs, competitor_price, threshold_pct, b2b_discount),
    )
