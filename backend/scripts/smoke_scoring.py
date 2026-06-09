from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.research.factor_explanation import explain_factor_contributions
from stock_analysis.research.recommendation_engine import rank_candidates
from stock_analysis.research.scoring import score_factors


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a sample smoke test for scoring, ranking, and factor explanation.")
    parser.add_argument("--sample", action="store_true", help="Use an in-memory sample factor table.")
    parser.add_argument("--top-n", type=int, default=3)
    args = parser.parse_args()

    if not args.sample:
        raise ValueError("Only --sample is supported in Task 4 smoke test. Provider-based scoring comes after batch factors.")

    factor_frame = _sample_factor_frame()
    scored = score_factors(factor_frame)
    ranked = rank_candidates(factor_frame, top_n=args.top_n)
    leader = str(ranked.iloc[0]["symbol"]) if not ranked.empty else ""
    explanations = explain_factor_contributions(factor_frame, symbol=leader).head(8)

    output = {
        "status": "ok",
        "mode": "sample",
        "input_rows": len(factor_frame),
        "score_rows": len(scored),
        "top_n": args.top_n,
        "ranked": _records(ranked),
        "leader_explanation_sample": _records(explanations),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


def _sample_factor_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _factor_row("AAA", name="strong"),
            _factor_row(
                "BBB",
                name="middle",
                momentum_20d=0.08,
                momentum_60d=0.10,
                momentum_120d=0.12,
                rs_20d=0.02,
                rs_60d=0.03,
                rs_120d=0.04,
                above_ma60=False,
                ma_bullish_alignment=False,
                volatility_20d=0.03,
                volatility_60d=0.035,
                max_drawdown=-0.18,
                max_drawdown_20d=-0.08,
                max_drawdown_60d=-0.10,
                avg_amount_20d=80_000_000,
                avg_amount_60d=70_000_000,
                avg_volume_20d=8_000_000,
                avg_volume_60d=7_000_000,
            ),
            _factor_row(
                "CCC",
                name="high-risk",
                momentum_20d=-0.05,
                momentum_60d=-0.08,
                momentum_120d=-0.12,
                rs_20d=-0.04,
                rs_60d=-0.06,
                rs_120d=-0.08,
                above_ma20=False,
                above_ma60=False,
                ma_bullish_alignment=False,
                volatility_20d=0.08,
                volatility_60d=0.09,
                max_drawdown=-0.45,
                max_drawdown_20d=-0.22,
                max_drawdown_60d=-0.35,
                avg_amount_20d=20_000_000,
                avg_amount_60d=18_000_000,
                avg_volume_20d=2_000_000,
                avg_volume_60d=1_800_000,
            ),
        ]
    )


def _factor_row(symbol: str, name: str, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "symbol": symbol,
        "as_of_date": "2024-01-31",
        "momentum_20d": 0.20,
        "momentum_60d": 0.30,
        "momentum_120d": 0.40,
        "ma5": 12.0,
        "ma20": 11.0,
        "ma60": 10.0,
        "above_ma20": True,
        "above_ma60": True,
        "ma_bullish_alignment": True,
        "rs_20d": 0.08,
        "rs_60d": 0.12,
        "rs_120d": 0.16,
        "volatility_20d": 0.01,
        "volatility_60d": 0.012,
        "max_drawdown": -0.08,
        "max_drawdown_20d": -0.02,
        "max_drawdown_60d": -0.04,
        "avg_amount_20d": 200_000_000,
        "avg_amount_60d": 180_000_000,
        "avg_volume_20d": 20_000_000,
        "avg_volume_60d": 18_000_000,
        "data_points": 180,
        "source": f"sample:{name}",
        "warnings": "",
    }
    row.update(overrides)
    return row


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [{key: _clean(value) for key, value in row.items()} for row in frame.to_dict(orient="records")]


def _clean(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return _clean(value.item())
    return value


if __name__ == "__main__":
    raise SystemExit(main())
