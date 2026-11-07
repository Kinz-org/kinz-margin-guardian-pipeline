"""Tests for the price floor / headroom calculation (src/price_floor.py) and its CLI.

The floor is only useful if it agrees with the engine that actually raises the
alerts, so most of these pin it against ``compute_product_margins`` directly
rather than against the formula.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.demo import DEMO_PRODUCTS, run_demo
from scripts.price_floor import catalogue_rows, main
from src.margin_engine import compute_product_margins
from src.price_floor import exact_price_floor, headroom, price_floor


def _alerts(cogs, price, threshold=40.0, discount=0.85):
    r = compute_product_margins(1, "x", cogs, price, threshold, discount)
    return r.b2c_alert or r.b2b_alert


class TestPriceFloor:
    @pytest.mark.parametrize("product", DEMO_PRODUCTS, ids=lambda p: p.name)
    def test_floor_is_the_engine_boundary_for_demo_products(self, product):
        floor = price_floor(product.cogs_tnd)
        assert not _alerts(product.cogs_tnd, floor)
        assert _alerts(product.cogs_tnd, round(floor - 0.001, 3))

    @pytest.mark.parametrize("cogs", [0.5, 6.0, 19.0, 30.0, 123.456, 999.0])
    @pytest.mark.parametrize("threshold", [0.0, 15.0, 40.0, 72.5])
    @pytest.mark.parametrize("discount", [0.7, 0.85, 1.0])
    def test_floor_is_the_engine_boundary_across_settings(self, cogs, threshold, discount):
        floor = price_floor(cogs, threshold, discount)
        assert not _alerts(cogs, floor, threshold, discount)
        assert _alerts(cogs, round(floor - 0.001, 3), threshold, discount)

    def test_known_value_at_default_settings(self):
        # Exact formula: 30 / 0.6 / 0.85 = 58.8235...; the engine rounds margins to
        # 2 decimals before comparing, so it lets prices down to 58.819 through.
        assert exact_price_floor(30.0) == pytest.approx(58.8235294, abs=1e-6)
        assert price_floor(30.0) == 58.819

    def test_floor_is_within_a_few_millimes_of_the_formula(self):
        for cogs in (6.0, 30.0, 300.0):
            exact = exact_price_floor(cogs)
            assert exact - 0.05 < price_floor(cogs) <= exact + 0.001

    def test_b2b_is_the_binding_channel_when_discounted(self):
        # Without a B2B discount the two channels coincide; with one, the floor rises
        # by exactly the discount factor.
        assert exact_price_floor(30.0, 40.0, 0.85) == pytest.approx(exact_price_floor(30.0, 40.0, 1.0) / 0.85)

    def test_floor_rises_with_threshold_and_cogs(self):
        assert price_floor(30.0, 30.0) < price_floor(30.0, 40.0) < price_floor(30.0, 50.0)
        assert price_floor(20.0) < price_floor(30.0)

    @pytest.mark.parametrize(
        "cogs, threshold, discount",
        [(30.0, 100.0, 0.85), (30.0, 120.0, 0.85), (30.0, -1.0, 0.85),
         (0.0, 40.0, 0.85), (-5.0, 40.0, 0.85), (30.0, 40.0, 0.0), (float("nan"), 40.0, 0.85)],
    )
    def test_rejects_impossible_inputs(self, cogs, threshold, discount):
        with pytest.raises(ValueError):
            price_floor(cogs, threshold, discount)


class TestHeadroom:
    def test_positive_headroom_above_floor(self):
        h = headroom(30.0, 62.0)
        assert h.floor_tnd == 58.819
        assert h.headroom_tnd == pytest.approx(3.181)
        assert h.headroom_pct == pytest.approx(5.13)
        assert h.below_floor is False

    def test_negative_headroom_below_floor(self):
        h = headroom(19.0, 25.0)
        assert h.headroom_tnd < 0
        assert h.below_floor is True

    def test_at_the_floor_is_not_below(self):
        h = headroom(30.0, 58.819)
        assert h.headroom_tnd == 0
        assert h.below_floor is False

    def test_rejects_non_positive_price(self):
        with pytest.raises(ValueError):
            headroom(30.0, 0.0)


class TestCli:
    def test_catalogue_matches_demo_alerts(self):
        rows = catalogue_rows(seed=42)
        demo = run_demo(seed=42)
        assert len(rows) == 5
        assert [r["below_floor"] for r in rows] == [r.b2c_alert or r.b2b_alert for r in demo]

    @pytest.mark.parametrize("seed", [1, 7, 42, 2026])
    def test_catalogue_matches_demo_alerts_for_other_seeds(self, seed):
        rows = catalogue_rows(seed=seed)
        demo = run_demo(seed=seed)
        assert [r["below_floor"] for r in rows] == [r.b2c_alert or r.b2b_alert for r in demo]

    def test_table_output(self, capsys):
        assert main(["--seed", "42"]) == 0
        out = capsys.readouterr().out
        assert "Floor" in out and "Headroom" in out
        for product in DEMO_PRODUCTS:
            assert product.name in out

    def test_single_product(self, capsys):
        assert main(["--cogs", "30"]) == 0
        assert "58.819 TND" in capsys.readouterr().out

    def test_impossible_threshold_is_a_clean_error(self, capsys):
        assert main(["--cogs", "30", "--threshold", "100"]) == 2
        err = capsys.readouterr().err
        assert err.startswith("error:") and "Traceback" not in err

    def test_json_output(self, tmp_path, capsys):
        out = tmp_path / "floors.json"
        assert main(["--json", str(out)]) == 0
        data = json.loads(out.read_text())
        assert len(data) == 5
        assert {"product_name", "floor_tnd", "headroom_tnd", "below_floor"} <= set(data[0])
