"""Price floor and headroom: how low can the competitor price go before a product alerts?

For each product, prints the lowest competitor price (to the millime) at which
neither the B2C nor the B2B margin falls below the alert threshold, and how far
today's simulated competitor price sits above (or below) that floor. Uses the same
synthetic catalogue and price simulation as ``scripts/demo.py``, so the two agree:
a product shown here as below its floor is exactly a product the demo flags ALERT.

No Docker, no Postgres, no secrets.

Usage:
    python scripts/price_floor.py                      # demo catalogue, seed 42
    python scripts/price_floor.py --seed 7 --json /tmp/floors.json
    python scripts/price_floor.py --cogs 30            # one product, default threshold
    python scripts/price_floor.py --cogs 30 --price 62 --threshold 35
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.demo import DEMO_PRODUCTS, simulate_competitor_prices
from src.config import B2B_DISCOUNT_FACTOR, DEFAULT_ALERT_THRESHOLD_PCT
from src.price_floor import headroom, price_floor


def catalogue_rows(
    seed: int,
    threshold_pct: float = DEFAULT_ALERT_THRESHOLD_PCT,
    b2b_discount: float = B2B_DISCOUNT_FACTOR,
) -> list[dict]:
    """One row per demo product: COGS, today's price, floor and headroom."""
    prices = simulate_competitor_prices(DEMO_PRODUCTS, seed)
    rows = []
    for product in DEMO_PRODUCTS:
        h = headroom(product.cogs_tnd, prices[product.product_id], threshold_pct, b2b_discount)
        rows.append({"product_name": product.name, "cogs_tnd": product.cogs_tnd, **asdict(h)})
    return rows


def render_table(rows: list[dict]) -> str:
    headers = ("Product", "COGS", "Competitor", "Floor", "Headroom", "Headroom %", "Status")
    cells = [
        (
            r["product_name"],
            f"{r['cogs_tnd']:.3f}",
            f"{r['competitor_price_tnd']:.3f}",
            f"{r['floor_tnd']:.3f}",
            f"{r['headroom_tnd']:+.3f}",
            f"{r['headroom_pct']:+.2f}%",
            "BELOW FLOOR" if r["below_floor"] else "ok",
        )
        for r in rows
    ]
    widths = [max(len(h), *(len(c[i]) for c in cells)) for i, h in enumerate(headers)]
    lines = ["  ".join(h.ljust(w) for h, w in zip(headers, widths, strict=True))]
    lines.append("  ".join("-" * w for w in widths))
    lines += ["  ".join(c.ljust(w) for c, w in zip(row, widths, strict=True)) for row in cells]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for the simulated competitor prices.")
    parser.add_argument("--cogs", type=float, help="Compute the floor for one product with this COGS (TND).")
    parser.add_argument("--price", type=float, help="With --cogs: today's competitor price, to show headroom.")
    parser.add_argument("--threshold", type=float, default=DEFAULT_ALERT_THRESHOLD_PCT,
                        help=f"Alert threshold in %% (default {DEFAULT_ALERT_THRESHOLD_PCT}).")
    parser.add_argument("--b2b-discount", type=float, default=B2B_DISCOUNT_FACTOR,
                        help=f"B2B price = competitor price x this factor (default {B2B_DISCOUNT_FACTOR}).")
    parser.add_argument("--json", type=Path, default=None, help="Also write the rows as JSON to this path.")
    args = parser.parse_args(argv)

    if args.price is not None and args.cogs is None:
        parser.error("--price needs --cogs")

    try:
        if args.cogs is not None:
            if args.price is not None:
                h = headroom(args.cogs, args.price, args.threshold, args.b2b_discount)
                rows = [{"product_name": "(given)", "cogs_tnd": args.cogs, **asdict(h)}]
                print(render_table(rows))
            else:
                floor = price_floor(args.cogs, args.threshold, args.b2b_discount)
                rows = [{"product_name": "(given)", "cogs_tnd": args.cogs, "floor_tnd": floor}]
                print(
                    f"Price floor for COGS {args.cogs:.3f} TND at a {args.threshold:g}% threshold "
                    f"(B2B factor {args.b2b_discount:g}): {floor:.3f} TND"
                )
        else:
            rows = catalogue_rows(args.seed, args.threshold, args.b2b_discount)
            print(render_table(rows))
            below = [r["product_name"] for r in rows if r["below_floor"]]
            if below:
                print(f"\nBelow floor today (would alert): {', '.join(below)}")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        args.json.write_text(json.dumps(rows, indent=2))
        print(f"\nWrote {len(rows)} rows to {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
