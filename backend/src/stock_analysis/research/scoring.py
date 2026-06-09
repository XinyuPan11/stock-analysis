from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from stock_analysis.research.factors import FACTOR_OUTPUT_COLUMNS


SCORE_OUTPUT_COLUMNS = [
    "symbol",
    "as_of_date",
    "total_score",
    "label",
    "confidence",
    "momentum_score",
    "trend_score",
    "relative_strength_score",
    "risk_score",
    "liquidity_score",
    "positive_evidence",
    "negative_evidence",
    "risk_flags",
    "warnings",
    "source",
]

COMPONENT_OUTPUT_COLUMNS = [
    "symbol",
    "as_of_date",
    "factor_group",
    "raw_value",
    "normalized_score",
    "weight",
    "contribution",
    "explanation",
]

LABEL_HIGH_CONFIDENCE = "\u9ad8\u7f6e\u4fe1\u5019\u9009"
LABEL_CANDIDATE = "\u5019\u9009\u5173\u6ce8"
LABEL_FOCUS = "\u91cd\u70b9\u89c2\u5bdf"
LABEL_WATCH = "\u89c2\u5bdf"
LABEL_HIGH_RISK = "\u98ce\u9669\u8fc7\u9ad8"
LABEL_INSUFFICIENT_DATA = "\u6570\u636e\u4e0d\u8db3"


@dataclass(frozen=True)
class ScoringConfig:
    data_points_minimum: int = 120
    high_risk_volatility_60d: float = 0.05
    high_risk_drawdown_60d: float = 0.25
    severe_risk_drawdown: float = 0.4
    high_confidence_threshold: float = 88.0
    candidate_threshold: float = 80.0
    focus_threshold: float = 65.0
    watch_threshold: float = 50.0
    min_high_confidence_risk_score: float = 10.0
    min_candidate_risk_score: float = 8.0


def score_factors(factor_df: pd.DataFrame, *, config: ScoringConfig | None = None) -> pd.DataFrame:
    """Score Phase 1 factor rows with interpretable rules only."""

    resolved_config = config or ScoringConfig()
    frame = _prepare_factor_frame(factor_df)
    components = calculate_score_components(frame)
    component_scores = _group_component_scores(components)
    rows: list[dict[str, object]] = []

    for _, row in frame.iterrows():
        symbol = str(row["symbol"])
        group_scores = component_scores.get(symbol, {})
        score_row = {
            "symbol": symbol,
            "as_of_date": str(row["as_of_date"]),
            "momentum_score": _round_score(group_scores.get("momentum", 0.0)),
            "trend_score": _round_score(group_scores.get("trend", 0.0)),
            "relative_strength_score": _round_score(group_scores.get("relative_strength", 0.0)),
            "risk_score": _round_score(group_scores.get("risk", 0.0)),
            "liquidity_score": _round_score(group_scores.get("liquidity", 0.0)),
            "warnings": str(row.get("warnings", "")),
            "source": str(row.get("source", "")),
        }
        total = sum(
            float(score_row[column])
            for column in [
                "momentum_score",
                "trend_score",
                "relative_strength_score",
                "risk_score",
                "liquidity_score",
            ]
        )
        risk_flags = _risk_flags(row, float(score_row["risk_score"]), resolved_config)
        data_flags = _data_quality_flags(row, resolved_config)
        confidence = _confidence(row, risk_flags=risk_flags, data_flags=data_flags)
        score_row["total_score"] = _round_score(total)
        score_row["risk_flags"] = ";".join(risk_flags)
        score_row["confidence"] = round(confidence, 3)
        score_row["label"] = _label(score_row, risk_flags=risk_flags, data_flags=data_flags, config=resolved_config)
        score_row["positive_evidence"] = _positive_evidence(score_row)
        score_row["negative_evidence"] = _negative_evidence(score_row, risk_flags=risk_flags, data_flags=data_flags)
        rows.append({column: score_row.get(column) for column in SCORE_OUTPUT_COLUMNS})

    return pd.DataFrame(rows, columns=SCORE_OUTPUT_COLUMNS).sort_values(
        ["total_score", "confidence", "symbol"], ascending=[False, False, True]
    ).reset_index(drop=True)


def calculate_score_components(factor_df: pd.DataFrame) -> pd.DataFrame:
    """Return raw factor values, normalized scores, weights, and point contributions."""

    frame = _prepare_factor_frame(factor_df)
    rows: list[dict[str, object]] = []
    percentile_columns = {
        "momentum_20d": _percentile(frame["momentum_20d"]),
        "momentum_60d": _percentile(frame["momentum_60d"]),
        "momentum_120d": _percentile(frame["momentum_120d"]),
        "rs_20d": _percentile(frame["rs_20d"]),
        "rs_60d": _percentile(frame["rs_60d"]),
        "rs_120d": _percentile(frame["rs_120d"]),
        "volatility_20d": _percentile(frame["volatility_20d"], higher_is_better=False),
        "volatility_60d": _percentile(frame["volatility_60d"], higher_is_better=False),
        "max_drawdown_20d": _percentile(_drawdown_severity(frame["max_drawdown_20d"]), higher_is_better=False),
        "max_drawdown_60d": _percentile(_drawdown_severity(frame["max_drawdown_60d"]), higher_is_better=False),
        "avg_amount_20d": _percentile(_winsorize(frame["avg_amount_20d"])),
        "avg_amount_60d": _percentile(_winsorize(frame["avg_amount_60d"])),
        "avg_volume_20d": _percentile(_winsorize(frame["avg_volume_20d"])),
        "avg_volume_60d": _percentile(_winsorize(frame["avg_volume_60d"])),
    }

    for idx, row in frame.iterrows():
        symbol = str(row["symbol"])
        as_of_date = str(row["as_of_date"])
        rows.extend(
            [
                _component(symbol, as_of_date, "momentum_20d", row["momentum_20d"], percentile_columns["momentum_20d"].iloc[idx], 7.5),
                _component(symbol, as_of_date, "momentum_60d", row["momentum_60d"], percentile_columns["momentum_60d"].iloc[idx], 10.0),
                _component(symbol, as_of_date, "momentum_120d", row["momentum_120d"], percentile_columns["momentum_120d"].iloc[idx], 7.5),
                _component(symbol, as_of_date, "above_ma20", row["above_ma20"], 1.0 if _truthy_bool(row["above_ma20"]) else 0.0, 6.0),
                _component(symbol, as_of_date, "above_ma60", row["above_ma60"], 1.0 if _truthy_bool(row["above_ma60"]) else 0.0, 6.0),
                _component(
                    symbol,
                    as_of_date,
                    "ma_bullish_alignment",
                    row["ma_bullish_alignment"],
                    1.0 if _truthy_bool(row["ma_bullish_alignment"]) else 0.0,
                    8.0,
                ),
                _component(symbol, as_of_date, "rs_20d", row["rs_20d"], percentile_columns["rs_20d"].iloc[idx], 6.0),
                _component(symbol, as_of_date, "rs_60d", row["rs_60d"], percentile_columns["rs_60d"].iloc[idx], 8.0),
                _component(symbol, as_of_date, "rs_120d", row["rs_120d"], percentile_columns["rs_120d"].iloc[idx], 6.0),
                _component(symbol, as_of_date, "volatility_20d", row["volatility_20d"], percentile_columns["volatility_20d"].iloc[idx], 6.0),
                _component(symbol, as_of_date, "volatility_60d", row["volatility_60d"], percentile_columns["volatility_60d"].iloc[idx], 6.0),
                _component(symbol, as_of_date, "max_drawdown_20d", row["max_drawdown_20d"], percentile_columns["max_drawdown_20d"].iloc[idx], 4.0),
                _component(symbol, as_of_date, "max_drawdown_60d", row["max_drawdown_60d"], percentile_columns["max_drawdown_60d"].iloc[idx], 4.0),
                _component(symbol, as_of_date, "avg_amount_20d", row["avg_amount_20d"], percentile_columns["avg_amount_20d"].iloc[idx], 5.25),
                _component(symbol, as_of_date, "avg_amount_60d", row["avg_amount_60d"], percentile_columns["avg_amount_60d"].iloc[idx], 5.25),
                _component(symbol, as_of_date, "avg_volume_20d", row["avg_volume_20d"], percentile_columns["avg_volume_20d"].iloc[idx], 2.25),
                _component(symbol, as_of_date, "avg_volume_60d", row["avg_volume_60d"], percentile_columns["avg_volume_60d"].iloc[idx], 2.25),
            ]
        )

    return pd.DataFrame(rows, columns=COMPONENT_OUTPUT_COLUMNS)


def _prepare_factor_frame(factor_df: pd.DataFrame) -> pd.DataFrame:
    if factor_df is None or factor_df.empty:
        raise ValueError("factor data is empty.")
    missing = [column for column in FACTOR_OUTPUT_COLUMNS if column not in factor_df.columns]
    if missing:
        raise ValueError(f"Factor data missing required columns: {missing}")

    frame = factor_df.loc[:, FACTOR_OUTPUT_COLUMNS].copy()
    numeric_columns = [
        "momentum_20d",
        "momentum_60d",
        "momentum_120d",
        "ma5",
        "ma20",
        "ma60",
        "rs_20d",
        "rs_60d",
        "rs_120d",
        "volatility_20d",
        "volatility_60d",
        "max_drawdown",
        "max_drawdown_20d",
        "max_drawdown_60d",
        "avg_amount_20d",
        "avg_amount_60d",
        "avg_volume_20d",
        "avg_volume_60d",
        "data_points",
    ]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in ["symbol", "as_of_date", "source", "warnings"]:
        frame[column] = frame[column].fillna("").astype(str)
    return frame.reset_index(drop=True)


def _percentile(series: pd.Series, *, higher_is_better: bool = True) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    ranks = numeric.rank(method="average", pct=True, ascending=higher_is_better)
    return ranks.fillna(0.0).clip(0.0, 1.0)


def _winsorize(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.dropna().empty:
        return numeric
    lower = numeric.quantile(0.05)
    upper = numeric.quantile(0.95)
    return numeric.clip(lower=lower, upper=upper)


def _drawdown_severity(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").abs()


def _component(
    symbol: str,
    as_of_date: str,
    factor_group: str,
    raw_value: object,
    normalized_score: object,
    weight: float,
) -> dict[str, object]:
    normalized = 0.0 if pd.isna(normalized_score) else float(normalized_score)
    contribution = normalized * weight
    return {
        "symbol": symbol,
        "as_of_date": as_of_date,
        "factor_group": factor_group,
        "raw_value": None if pd.isna(raw_value) else raw_value,
        "normalized_score": round(normalized, 6),
        "weight": weight,
        "contribution": round(contribution, 6),
        "explanation": _component_explanation(factor_group, raw_value, normalized, contribution),
    }


def _component_explanation(factor_group: str, raw_value: object, normalized: float, contribution: float) -> str:
    if factor_group.startswith("momentum"):
        return f"{factor_group}\u6a2a\u622a\u9762\u5206\u4f4d\u6570 {normalized:.0%}\uff0c\u8d21\u732e {contribution:.2f} \u5206\u3002"
    if factor_group.startswith("rs_"):
        return f"{factor_group}\u8d85\u989d\u6536\u76ca\u5206\u4f4d\u6570 {normalized:.0%}\uff0c\u8d21\u732e {contribution:.2f} \u5206\u3002"
    if factor_group.startswith("volatility"):
        return f"{factor_group}\u4f4e\u6ce2\u52a8\u5206\u4f4d\u6570 {normalized:.0%}\uff0c\u8d21\u732e {contribution:.2f} \u5206\u3002"
    if factor_group.startswith("max_drawdown"):
        return f"{factor_group}\u5c0f\u56de\u64a4\u5206\u4f4d\u6570 {normalized:.0%}\uff0c\u8d21\u732e {contribution:.2f} \u5206\u3002"
    if factor_group.startswith("avg_"):
        return f"{factor_group}\u6d41\u52a8\u6027\u5206\u4f4d\u6570 {normalized:.0%}\uff0c\u8d21\u732e {contribution:.2f} \u5206\u3002"
    if factor_group == "above_ma20":
        return "\u4ef7\u683c\u7ad9\u4e0a MA20\u3002" if _truthy_bool(raw_value) else "\u4ef7\u683c\u672a\u7ad9\u4e0a MA20\u3002"
    if factor_group == "above_ma60":
        return "\u4ef7\u683c\u7ad9\u4e0a MA60\u3002" if _truthy_bool(raw_value) else "\u4ef7\u683c\u672a\u7ad9\u4e0a MA60\u3002"
    if factor_group == "ma_bullish_alignment":
        return "\u6ee1\u8db3 MA5 > MA20 > MA60 \u591a\u5934\u6392\u5217\u3002" if _truthy_bool(raw_value) else "\u672a\u6ee1\u8db3 MA5 > MA20 > MA60 \u591a\u5934\u6392\u5217\u3002"
    return f"{factor_group}\u8d21\u732e {contribution:.2f} \u5206\u3002"


def _group_component_scores(components: pd.DataFrame) -> dict[str, dict[str, float]]:
    groups = {
        "momentum": {"momentum_20d", "momentum_60d", "momentum_120d"},
        "trend": {"above_ma20", "above_ma60", "ma_bullish_alignment"},
        "relative_strength": {"rs_20d", "rs_60d", "rs_120d"},
        "risk": {"volatility_20d", "volatility_60d", "max_drawdown_20d", "max_drawdown_60d"},
        "liquidity": {"avg_amount_20d", "avg_amount_60d", "avg_volume_20d", "avg_volume_60d"},
    }
    result: dict[str, dict[str, float]] = {}
    for symbol, stock_components in components.groupby("symbol"):
        result[str(symbol)] = {}
        for group_name, factor_names in groups.items():
            score = stock_components.loc[stock_components["factor_group"].isin(factor_names), "contribution"].sum()
            result[str(symbol)][group_name] = float(score)
    return result


def _risk_flags(row: pd.Series, risk_score: float, config: ScoringConfig) -> list[str]:
    flags: list[str] = []
    volatility_60d = row.get("volatility_60d")
    drawdown_60d = _abs_optional(row.get("max_drawdown_60d"))
    drawdown_all = _abs_optional(row.get("max_drawdown"))
    if risk_score < 5:
        flags.append("very_low_risk_score")
    if volatility_60d is not None and volatility_60d >= config.high_risk_volatility_60d:
        flags.append("high_60d_volatility")
    if drawdown_60d is not None and drawdown_60d >= config.high_risk_drawdown_60d:
        flags.append("large_60d_drawdown")
    if drawdown_all is not None and drawdown_all >= config.severe_risk_drawdown:
        flags.append("severe_max_drawdown")
    return flags


def _data_quality_flags(row: pd.Series, config: ScoringConfig) -> list[str]:
    flags: list[str] = []
    warnings = _warning_set(row.get("warnings", ""))
    if pd.isna(row.get("data_points")) or float(row.get("data_points", 0)) < config.data_points_minimum:
        flags.append("insufficient_data_points")
    severe_warnings = {
        "insufficient_120d_history",
        "missing_benchmark_data",
        "benchmark_insufficient_120d_history",
        "missing_adj_close_fallback_to_close",
    }
    flags.extend(sorted(warnings & severe_warnings))
    required = [
        "momentum_120d",
        "rs_60d",
        "volatility_60d",
        "max_drawdown_60d",
        "avg_amount_20d",
        "avg_volume_20d",
    ]
    missing_required = [column for column in required if pd.isna(row.get(column))]
    if missing_required:
        flags.append("missing_required_factor")
    return flags


def _confidence(row: pd.Series, *, risk_flags: list[str], data_flags: list[str]) -> float:
    confidence = 1.0
    confidence -= min(0.45, 0.15 * len(set(data_flags)))
    confidence -= min(0.35, 0.12 * len(set(risk_flags)))
    warning_count = len(_warning_set(row.get("warnings", "")))
    confidence -= min(0.20, 0.04 * warning_count)
    return max(0.0, round(confidence, 3))


def _label(
    score_row: dict[str, object],
    *,
    risk_flags: list[str],
    data_flags: list[str],
    config: ScoringConfig,
) -> str:
    total = float(score_row["total_score"])
    risk_score = float(score_row["risk_score"])
    confidence = float(score_row["confidence"])
    severe_risk = "very_low_risk_score" in risk_flags or "severe_max_drawdown" in risk_flags
    if severe_risk:
        return LABEL_HIGH_RISK
    if data_flags and confidence < 0.7:
        return LABEL_INSUFFICIENT_DATA
    if (
        total >= config.high_confidence_threshold
        and confidence >= 0.75
        and risk_score >= config.min_high_confidence_risk_score
        and not risk_flags
        and not data_flags
    ):
        return LABEL_HIGH_CONFIDENCE
    if total >= config.candidate_threshold and risk_score >= config.min_candidate_risk_score:
        return LABEL_CANDIDATE
    if total >= config.focus_threshold:
        return LABEL_FOCUS
    if total >= config.watch_threshold:
        return LABEL_WATCH
    if risk_score < 6 or risk_flags:
        return LABEL_HIGH_RISK
    return LABEL_WATCH


def _positive_evidence(score_row: dict[str, object]) -> str:
    evidence: list[str] = []
    if float(score_row["momentum_score"]) >= 18:
        evidence.append("\u52a8\u91cf\u5206\u4f4d\u9760\u524d")
    if float(score_row["trend_score"]) >= 14:
        evidence.append("\u8d8b\u52bf\u7ed3\u6784\u8f83\u5f3a")
    if float(score_row["relative_strength_score"]) >= 14:
        evidence.append("\u76f8\u5bf9\u6caa\u6df1300\u8d85\u989d\u6536\u76ca\u8f83\u5f3a")
    if float(score_row["risk_score"]) >= 14:
        evidence.append("\u6ce2\u52a8\u548c\u56de\u64a4\u76f8\u5bf9\u53ef\u63a7")
    if float(score_row["liquidity_score"]) >= 10:
        evidence.append("\u8fd1\u671f\u6d41\u52a8\u6027\u8f83\u597d")
    if not evidence and float(score_row["total_score"]) >= 50:
        evidence.append("\u7efc\u5408\u56e0\u5b50\u5904\u4e8e\u53ef\u89c2\u5bdf\u533a\u95f4")
    return "\uff1b".join(evidence)


def _negative_evidence(
    score_row: dict[str, object],
    *,
    risk_flags: list[str],
    data_flags: list[str],
) -> str:
    evidence: list[str] = []
    if float(score_row["momentum_score"]) < 10:
        evidence.append("\u52a8\u91cf\u6392\u540d\u504f\u5f31")
    if float(score_row["trend_score"]) < 10:
        evidence.append("\u8d8b\u52bf\u7ed3\u6784\u4e0d\u5b8c\u6574")
    if float(score_row["relative_strength_score"]) < 8:
        evidence.append("\u76f8\u5bf9\u5f3a\u5ea6\u504f\u5f31\u6216\u57fa\u51c6\u6570\u636e\u4e0d\u8db3")
    if float(score_row["risk_score"]) < 8:
        evidence.append("\u98ce\u9669\u5f97\u5206\u504f\u4f4e")
    if float(score_row["liquidity_score"]) < 5:
        evidence.append("\u6d41\u52a8\u6027\u5f97\u5206\u504f\u4f4e")
    if data_flags:
        evidence.append("\u6570\u636e\u5b8c\u6574\u6027\u4e0d\u8db3")
    if risk_flags:
        evidence.append("\u5b58\u5728\u98ce\u9669\u6807\u8bb0: " + ",".join(risk_flags))
    return "\uff1b".join(evidence)


def _warning_set(value: object) -> set[str]:
    text = "" if value is None else str(value)
    return {item.strip() for item in text.split(";") if item.strip()}


def _truthy_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _abs_optional(value: object) -> float | None:
    if pd.isna(value):
        return None
    return abs(float(value))


def _round_score(value: object) -> float:
    return round(float(value), 4)
