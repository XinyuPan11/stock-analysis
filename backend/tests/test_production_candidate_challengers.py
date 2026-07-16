from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
SRC = BACKEND_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.research.production_candidate_challengers import (
    ProductionCandidateChallengerError,
    build_challengers,
    load_challenger_config,
    validate_challenger_config,
    write_challenger_outputs,
)
from stock_analysis.research.production_candidate_feature_matrix import (
    IDENTITY_COLUMNS,
    load_feature_config,
    sha256_file,
)


FEATURE_CONFIG = (
    REPO_ROOT / "research" / "configs" / "production_candidate_features.v1.json"
)
CHALLENGER_CONFIG = (
    REPO_ROOT
    / "research"
    / "configs"
    / "production_candidate_challengers.v1.json"
)
CLI = BACKEND_ROOT / "scripts" / "build_production_candidate_challengers.py"
AS_OF = "2024-10-31"


def _matrix(tmp_path: Path) -> Path:
    config = load_feature_config(FEATURE_CONFIG)
    rows = []
    symbols = ["sh.600001", "sh.600002", "sh.600003", "sh.600004"]
    for index, symbol in enumerate(symbols):
        row = {column: np.nan for column in config["output_feature_columns"]}
        row.update(
            {
                "dataset_version": config["dataset_version"],
                "feature_schema_version": config["feature_schema_version"],
                "feature_config_sha256": sha256_file(FEATURE_CONFIG),
                "foundation_id": config["foundation_id"],
                "production_baseline_id": config["production_baseline_id"],
                "symbol": symbol,
                "as_of_date": AS_OF,
                "latest_input_date": AS_OF,
                "source_snapshot_id": f"synthetic:{symbol}",
                "universe_id": "synthetic",
                "benchmark": "CSI300",
                "data_role": "consumed_development_smoke_only",
                "provider_access": False,
                "labels_joined": False,
                "leakage_guard_applied": True,
                "production_change": False,
                "limit_used": True,
                "observation_count": 130,
                "row_status": "ok",
                "missing_reason": "",
                "data_quality_status": "ok",
                "low_liquidity_warning": False,
                "total_score": 50 + index,
                "risk_score": 10 + index,
                "left_tail_risk_score": 0.4 - index * 0.05,
                "trend_acceleration_score": 0.2 + index * 0.1,
                "trend_smoothness_20": 0.4 + index * 0.05,
                "relative_amount_5_20": 0.8 + index * 0.1,
                "price_volume_agreement": 0.1 + index * 0.1,
                "low_position_score": 0.8 - index * 0.1,
                "recovery_strength_20": 0.05 + index * 0.01,
                "mean_reversion_opportunity_score": 0.3 + index * 0.1,
                "average_amount_20": 30_000_000 + index * 1_000_000,
                "amount_stability": 0.6 + index * 0.05,
                "crowding_risk_score": 0.2 + index * 0.1,
            }
        )
        rows.append(row)
    path = tmp_path / "features.csv"
    pd.DataFrame(rows).loc[
        :, [*IDENTITY_COLUMNS, *config["output_feature_columns"]]
    ].to_csv(path, index=False)
    return path


def _config() -> dict[str, object]:
    return load_challenger_config(
        CHALLENGER_CONFIG,
        feature_config_path=FEATURE_CONFIG,
    )


def test_valid_challenger_config_and_full_row_output(tmp_path: Path) -> None:
    result = build_challengers(
        feature_matrix_path=_matrix(tmp_path),
        feature_config_path=FEATURE_CONFIG,
        challenger_config_path=CHALLENGER_CONFIG,
    )

    assert result.report["challenger_count"] == 5
    assert len(result.frame) == 4 * 5
    assert result.report["boolean_cohort_truncation"] is False
    assert set(result.frame["effectiveness_status"]) == {"not_evaluated"}
    assert set(result.frame["production_change"]) == {False}


def test_unknown_feature_reference_fails() -> None:
    config = _config()
    changed = copy.deepcopy(config)
    changed["challengers"][0]["components"][0]["feature_id"] = "unknown_feature"

    with pytest.raises(
        ProductionCandidateChallengerError,
        match="unknown feature",
    ):
        validate_challenger_config(
            changed,
            feature_config=load_feature_config(FEATURE_CONFIG),
            feature_config_sha256=sha256_file(FEATURE_CONFIG),
        )


@pytest.mark.parametrize(
    "column",
    [
        "winner",
        "loser",
        "right_tail",
        "severe_drawdown",
        "future_return_20d",
    ],
)
def test_label_or_future_column_in_feature_matrix_fails(
    tmp_path: Path,
    column: str,
) -> None:
    path = _matrix(tmp_path)
    frame = pd.read_csv(path)
    frame[column] = False
    frame.to_csv(path, index=False)

    with pytest.raises(
        ProductionCandidateChallengerError,
        match="label or future-outcome",
    ):
        build_challengers(
            feature_matrix_path=path,
            feature_config_path=FEATURE_CONFIG,
            challenger_config_path=CHALLENGER_CONFIG,
        )


def test_mixed_as_of_dates_fail(tmp_path: Path) -> None:
    path = _matrix(tmp_path)
    frame = pd.read_csv(path)
    frame.loc[0, "as_of_date"] = "2024-11-29"
    frame.to_csv(path, index=False)

    with pytest.raises(
        ProductionCandidateChallengerError,
        match="Mixed as-of dates",
    ):
        build_challengers(
            feature_matrix_path=path,
            feature_config_path=FEATURE_CONFIG,
            challenger_config_path=CHALLENGER_CONFIG,
        )


def test_neutral_formula_and_ranking_are_deterministic(
    tmp_path: Path,
) -> None:
    path = _matrix(tmp_path)
    first = build_challengers(
        feature_matrix_path=path,
        feature_config_path=FEATURE_CONFIG,
        challenger_config_path=CHALLENGER_CONFIG,
    ).frame
    second = build_challengers(
        feature_matrix_path=path,
        feature_config_path=FEATURE_CONFIG,
        challenger_config_path=CHALLENGER_CONFIG,
    ).frame

    pd.testing.assert_frame_equal(first, second)
    for _, group in first[first["eligibility_status"] == "eligible"].groupby(
        "challenger_id"
    ):
        assert group.sort_values("challenger_rank")["challenger_rank"].tolist() == list(
            range(1, len(group) + 1)
        )


def test_missing_components_produce_explicit_ineligible_status(
    tmp_path: Path,
) -> None:
    path = _matrix(tmp_path)
    frame = pd.read_csv(path)
    frame.loc[0, "trend_smoothness_20"] = np.nan
    frame.to_csv(path, index=False)

    result = build_challengers(
        feature_matrix_path=path,
        feature_config_path=FEATURE_CONFIG,
        challenger_config_path=CHALLENGER_CONFIG,
    ).frame
    row = result[
        (result["symbol"] == "sh.600001")
        & (result["challenger_id"] == "trend_volume_quality_v1")
    ].iloc[0]

    assert row["eligibility_status"] == "ineligible_missing_or_prerequisite"
    assert row["missing_component_count"] == 1
    assert row["missing_component_ids"] == "trend_smoothness_20"
    assert pd.isna(row["challenger_rank"])


def test_effectiveness_or_outcome_tuning_claim_fails() -> None:
    config = _config()
    changed = copy.deepcopy(config)
    changed["challengers"][0]["effectiveness_status"] = "supported"

    with pytest.raises(
        ProductionCandidateChallengerError,
        match="claims effectiveness",
    ):
        validate_challenger_config(
            changed,
            feature_config=load_feature_config(FEATURE_CONFIG),
            feature_config_sha256=sha256_file(FEATURE_CONFIG),
        )


def test_feature_config_digest_mismatch_fails() -> None:
    config = _config()
    changed = copy.deepcopy(config)
    changed["feature_config_sha256"] = "0" * 64

    with pytest.raises(
        ProductionCandidateChallengerError,
        match="digest",
    ):
        validate_challenger_config(
            changed,
            feature_config=load_feature_config(FEATURE_CONFIG),
            feature_config_sha256=sha256_file(FEATURE_CONFIG),
        )


def test_challenger_config_digest_mismatch_fails(tmp_path: Path) -> None:
    changed = copy.deepcopy(_config())
    changed["challengers"][0]["purpose"] = "digest drift"
    path = tmp_path / "challengers.json"
    path.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(
        ProductionCandidateChallengerError,
        match="Challenger config digest mismatch",
    ):
        load_challenger_config(
            path,
            feature_config_path=FEATURE_CONFIG,
        )


def test_dry_run_cli_writes_nothing(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    completed = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--feature-matrix",
            str(_matrix(tmp_path)),
            "--feature-config",
            str(FEATURE_CONFIG),
            "--challenger-config",
            str(CHALLENGER_CONFIG),
            "--outputs-dir",
            str(outputs),
            "--dry-run",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout
    assert not outputs.exists()


def test_write_mode_writes_only_research_challenger_outputs(
    tmp_path: Path,
) -> None:
    result = build_challengers(
        feature_matrix_path=_matrix(tmp_path),
        feature_config_path=FEATURE_CONFIG,
        challenger_config_path=CHALLENGER_CONFIG,
    )
    outputs = tmp_path / "outputs"
    paths = write_challenger_outputs(result, outputs_dir=outputs)
    files = sorted(
        path.relative_to(outputs).as_posix()
        for path in outputs.rglob("*")
        if path.is_file()
    )

    assert files == [
        f"research/production_candidate_challengers_{AS_OF}.csv",
        f"research/production_candidate_challengers_{AS_OF}.json",
    ]
    payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert payload["metadata"]["results_are_effectiveness_evidence"] is False


def test_no_production_module_is_imported_or_invoked(tmp_path: Path) -> None:
    source = (
        SRC
        / "stock_analysis"
        / "research"
        / "production_candidate_challengers.py"
    ).read_text(encoding="utf-8")
    result = build_challengers(
        feature_matrix_path=_matrix(tmp_path),
        feature_config_path=FEATURE_CONFIG,
        challenger_config_path=CHALLENGER_CONFIG,
    )

    assert "stock_analysis.research.scoring" not in source
    assert "stock_analysis.research.pipeline" not in source
    assert result.report["provider_access"] is False
    assert result.report["production_change"] is False
