from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.portfolio.portfolio_rules import allocation_counts, get_default_portfolio_rules
from stock_analysis.portfolio.simulator import PortfolioValidationConfig, build_portfolio_holdings, load_list_payloads, run_portfolio_validation


class PortfolioSimulatorTests(unittest.TestCase):
    def test_equal_weight_top_10_portfolio_builds_correctly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_portfolio_fixture(root)
            rule = next(rule for rule in get_default_portfolio_rules() if rule.portfolio_id == "high_confidence_top10")
            payloads = load_list_payloads(root / "outputs", "2024-01-31", [rule])

            holdings = build_portfolio_holdings(rule, payloads)

            self.assertEqual(len(holdings), 10)
            self.assertAlmostEqual(sum(float(row["portfolio_weight"]) for row in holdings), 1.0)
            self.assertEqual(holdings[0]["symbol"], "AAA01")

    def test_top_20_portfolio_uses_twenty_items_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_portfolio_fixture(root)
            rule = next(rule for rule in get_default_portfolio_rules() if rule.portfolio_id == "high_confidence_top20")
            payloads = load_list_payloads(root / "outputs", "2024-01-31", [rule])

            holdings = build_portfolio_holdings(rule, payloads)

            self.assertEqual(len(holdings), 20)

    def test_mixed_baseline_allocation_counts(self) -> None:
        rule = next(rule for rule in get_default_portfolio_rules() if rule.portfolio_id == "mixed_baseline")

        self.assertEqual(allocation_counts(rule), {"trend_leaders": 4, "accumulation_watch": 3, "long_term_stable": 3})

    def test_high_risk_active_is_observation_only(self) -> None:
        rule = next(rule for rule in get_default_portfolio_rules() if rule.portfolio_id == "high_risk_active_observation")

        self.assertTrue(rule.observation_only)

    def test_run_portfolio_validation_dry_run_writes_no_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_portfolio_fixture(root)

            result = run_portfolio_validation(
                PortfolioValidationConfig(
                    as_of_date="2024-01-31",
                    horizon_days=60,
                    outputs_dir=root / "outputs",
                    portfolio_ids=("high_confidence_top10",),
                    dry_run=True,
                )
            )

            self.assertEqual(result["summary"]["status"], "dry_run")
            self.assertTrue(result["summary"]["no_future_leakage"])
            self.assertEqual(result["outputs"], {})
            self.assertFalse((root / "outputs" / "portfolios").exists())


def write_portfolio_fixture(root: Path) -> None:
    outputs = root / "outputs"
    (outputs / "lists").mkdir(parents=True)
    (outputs / "validation").mkdir(parents=True)
    for list_id, prefix, count in [
        ("high_confidence_candidates", "AAA", 25),
        ("trend_leaders", "TRD", 12),
        ("accumulation_watch", "ACC", 12),
        ("long_term_stable", "LTS", 12),
        ("breakout_watch", "BRK", 12),
        ("high_risk_active", "RSK", 12),
    ]:
        _write_json(
            outputs / "lists" / f"{list_id}_2024-01-31.json",
            {
                "list_id": list_id,
                "as_of_date": "2024-01-31",
                "items": [_item(f"{prefix}{index:02d}", index) for index in range(1, count + 1)],
            },
        )
    _write_json(outputs / "lists" / "rebound_watch_2024-01-31.json", {"list_id": "rebound_watch", "as_of_date": "2024-01-31", "items": []})
    rows = []
    for symbol in [f"AAA{index:02d}" for index in range(1, 26)] + [f"TRD{index:02d}" for index in range(1, 13)] + [f"ACC{index:02d}" for index in range(1, 13)] + [f"LTS{index:02d}" for index in range(1, 13)] + [f"BRK{index:02d}" for index in range(1, 13)] + [f"RSK{index:02d}" for index in range(1, 13)]:
        rows.append(
            {
                "symbol": symbol,
                "as_of_date": "2024-01-31",
                "horizon_days": 60,
                "future_return": 0.1 if not symbol.endswith("02") else -0.05,
                "future_excess_return": 0.02 if not symbol.endswith("02") else -0.08,
                "outperformed_benchmark": not symbol.endswith("02"),
                "max_drawdown_during_holding": -0.04 if not symbol.endswith("02") else -0.2,
                "data_quality": "ok",
            }
        )
    pd.DataFrame(rows).to_csv(outputs / "validation" / "walk_forward_predictions_2024-01-31_60d.csv", index=False, encoding="utf-8")


def _item(symbol: str, rank: int) -> dict[str, object]:
    return {
        "symbol": symbol,
        "name": f"Name {symbol}",
        "rank": rank,
        "total_score": 100 - rank,
        "primary_type": "technical_candidate",
        "secondary_tags": ["trend", "liquidity"],
    }


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

