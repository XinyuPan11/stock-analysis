from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
SRC = BACKEND_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.research.production_candidate_foundation import (
    ProductionCandidateFoundationError,
    audit_production_candidate_foundation,
    load_baseline_manifest,
    load_foundation_config,
    validate_baseline_manifest,
    validate_foundation_config,
)


BASELINE_PATH = (
    REPO_ROOT
    / "research"
    / "configs"
    / "production_candidate_baseline.v1.json"
)
FOUNDATION_PATH = (
    REPO_ROOT
    / "research"
    / "configs"
    / "production_candidate_research_foundation.v1.json"
)
CLI_PATH = (
    BACKEND_ROOT
    / "scripts"
    / "audit_production_candidate_foundation.py"
)


def _baseline() -> dict[str, object]:
    return load_baseline_manifest(BASELINE_PATH, repo_root=REPO_ROOT)


def _foundation() -> dict[str, object]:
    return load_foundation_config(FOUNDATION_PATH, repo_root=REPO_ROOT)


def test_valid_baseline_manifest_passes() -> None:
    baseline = _baseline()

    assert baseline["baseline_version"] == "production-candidate-baseline-v1"
    assert baseline["production_change"] is False
    assert len(baseline["scoring_contract"]["components"]) == 17


def test_valid_research_foundation_config_passes() -> None:
    foundation = _foundation()

    assert foundation["feature_schema_version"] == (
        "production_candidate_feature_matrix.v1"
    )
    assert foundation["label_schema_version"] == (
        "production_candidate_label_matrix.v1"
    )
    assert foundation["provider_access"] is False


def test_missing_baseline_provenance_fails() -> None:
    changed = copy.deepcopy(_baseline())
    changed["captured_from_commit"] = ""

    with pytest.raises(
        ProductionCandidateFoundationError,
        match="lacks immutable commit",
    ):
        validate_baseline_manifest(changed, repo_root=REPO_ROOT)


def test_unknown_feature_status_fails() -> None:
    changed = copy.deepcopy(_foundation())
    changed["feature_registry"][0]["production_status"] = "production_ready"

    with pytest.raises(
        ProductionCandidateFoundationError,
        match="Unknown feature production status",
    ):
        validate_foundation_config(changed, repo_root=REPO_ROOT)


def test_duplicate_feature_id_fails() -> None:
    changed = copy.deepcopy(_foundation())
    changed["feature_registry"].append(
        copy.deepcopy(changed["feature_registry"][0])
    )

    with pytest.raises(
        ProductionCandidateFoundationError,
        match="Duplicate feature IDs",
    ):
        validate_foundation_config(changed, repo_root=REPO_ROOT)


def test_future_return_feature_fails() -> None:
    changed = copy.deepcopy(_foundation())
    changed["feature_registry"][0]["feature_id"] = "future_return_20d"

    with pytest.raises(
        ProductionCandidateFoundationError,
        match="Future or outcome-derived",
    ):
        validate_foundation_config(changed, repo_root=REPO_ROOT)


@pytest.mark.parametrize("feature_id", ["winner", "loser"])
def test_winner_or_loser_feature_fails(feature_id: str) -> None:
    changed = copy.deepcopy(_foundation())
    changed["feature_registry"][0]["feature_id"] = feature_id

    with pytest.raises(
        ProductionCandidateFoundationError,
        match="Privileged outcome label",
    ):
        validate_foundation_config(changed, repo_root=REPO_ROOT)


def test_post_asof_dependency_fails() -> None:
    changed = copy.deepcopy(_foundation())
    changed["feature_registry"][0][
        "point_in_time_rule"
    ] = "source trade_date > as_of_date"

    with pytest.raises(
        ProductionCandidateFoundationError,
        match="not point-in-time safe",
    ):
        validate_foundation_config(changed, repo_root=REPO_ROOT)


def test_consumed_window_mislabeled_unseen_fails() -> None:
    changed = copy.deepcopy(_foundation())
    changed["data_roles"]["consumed_windows"][0]["role"] = (
        "fresh_unseen_holdout"
    )

    with pytest.raises(
        ProductionCandidateFoundationError,
        match="cannot be described as fresh unseen",
    ):
        validate_foundation_config(changed, repo_root=REPO_ROOT)


def test_u3_reassignment_fails() -> None:
    changed = copy.deepcopy(_foundation())
    changed["data_roles"]["reserved_windows"][0][
        "reassignable_to_phase4"
    ] = True

    with pytest.raises(
        ProductionCandidateFoundationError,
        match="U3 identity or reservation",
    ):
        validate_foundation_config(changed, repo_root=REPO_ROOT)


def test_production_change_true_fails() -> None:
    changed = copy.deepcopy(_foundation())
    changed["production_change"] = True

    with pytest.raises(
        ProductionCandidateFoundationError,
        match="identity or safety flag",
    ):
        validate_foundation_config(changed, repo_root=REPO_ROOT)


def test_provider_access_true_fails() -> None:
    changed = copy.deepcopy(_foundation())
    changed["provider_access"] = True

    with pytest.raises(
        ProductionCandidateFoundationError,
        match="identity or safety flag",
    ):
        validate_foundation_config(changed, repo_root=REPO_ROOT)


def test_feature_label_separation_is_enforced() -> None:
    changed = copy.deepcopy(_foundation())
    changed["row_identities"]["feature_label_tables_separate"] = False

    with pytest.raises(
        ProductionCandidateFoundationError,
        match="must remain separate",
    ):
        validate_foundation_config(changed, repo_root=REPO_ROOT)


def test_unknown_production_eligibility_status_fails() -> None:
    changed = copy.deepcopy(_foundation())
    changed["allowed_statuses"].append("production_ready")

    with pytest.raises(
        ProductionCandidateFoundationError,
        match="production eligibility status",
    ):
        validate_foundation_config(changed, repo_root=REPO_ROOT)


def test_dry_run_writes_no_output(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    completed = subprocess.run(
        [
            sys.executable,
            str(CLI_PATH),
            "--repo-root",
            str(REPO_ROOT),
            "--outputs-dir",
            str(outputs),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["status"] == "safe"
    assert report["dry_run"] is True
    assert report["outputs_written"] is False
    assert not outputs.exists()


def test_write_mode_writes_only_allowed_research_audit(
    tmp_path: Path,
) -> None:
    outputs = tmp_path / "outputs"
    completed = subprocess.run(
        [
            sys.executable,
            str(CLI_PATH),
            "--repo-root",
            str(REPO_ROOT),
            "--outputs-dir",
            str(outputs),
            "--write-output",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    files = [path.relative_to(outputs).as_posix() for path in outputs.rglob("*") if path.is_file()]
    assert files == [
        "research/production_candidate_foundation_audit.json"
    ]
    payload = json.loads(
        (
            outputs
            / "research"
            / "production_candidate_foundation_audit.json"
        ).read_text(encoding="utf-8")
    )
    assert payload["production_change"] is False
    assert payload["provider_access"] is False
    assert payload["outputs_written"] is True


def test_audit_does_not_import_or_invoke_production_modules() -> None:
    report = audit_production_candidate_foundation(repo_root=REPO_ROOT)
    source = (
        SRC
        / "stock_analysis"
        / "research"
        / "production_candidate_foundation.py"
    ).read_text(encoding="utf-8")

    assert "stock_analysis.research.scoring" not in source
    assert "stock_analysis.research.pipeline" not in source
    assert report["production_modules_invoked"] is False
    assert report["features_generated"] is False
    assert report["labels_generated"] is False
    assert report["backtest_run"] is False
