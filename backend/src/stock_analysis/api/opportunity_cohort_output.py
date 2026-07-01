from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from stock_analysis.research.feature_only_snapshot import find_outcome_columns
from stock_analysis.research.opportunity_cohorts import (
    COHORT_CAVEATS,
    COHORT_ROLES,
)


OPPORTUNITY_COHORT_DISPLAY_IDS = {
    cohort_id: f"H{index}"
    for index, cohort_id in enumerate(COHORT_ROLES, start=1)
}

OPPORTUNITY_COHORT_CAVEATS = [
    "Research-only opportunity cohorts.",
    "Not validated.",
    "Not investment advice.",
    "Smoke counts are execution evidence only, not performance evidence.",
    "H1-H3 are opportunity observations; H4-H5 are non-blocking risk annotations.",
    "No production score, rank, list, threshold, or recommendation is changed.",
]


def load_research_opportunity_cohorts(
    outputs_dir: str | Path,
    *,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    research_dir = Path(outputs_dir).resolve() / "research"
    selected_date = as_of_date or _latest_output_date(research_dir)
    if not selected_date:
        return _unavailable_payload()

    source_path = research_dir / f"opportunity_cohorts_{selected_date}.json"
    if not source_path.exists():
        return _unavailable_payload(as_of_date=selected_date)

    payload = _read_json(source_path)
    if not isinstance(payload, dict):
        return _blocked_payload(
            as_of_date=selected_date,
            source_output_path=source_path,
            violations=["invalid_or_unreadable_json"],
        )

    metadata = payload.get("metadata")
    records = payload.get("records")
    summaries = payload.get("cohorts")
    violations = _safety_violations(metadata, records, summaries)
    if violations:
        return _blocked_payload(
            as_of_date=selected_date,
            source_output_path=source_path,
            violations=violations,
        )

    assert isinstance(metadata, dict)
    assert isinstance(records, list)
    assert isinstance(summaries, list)
    summary_by_id = {
        str(item.get("cohort_id")): item
        for item in summaries
        if isinstance(item, dict)
    }
    groups = []
    for cohort_id, cohort_role in COHORT_ROLES.items():
        cohort_records = [
            record
            for record in records
            if isinstance(record, dict)
            and str(record.get("cohort_id")) == cohort_id
        ]
        members = [
            record for record in cohort_records
            if record.get("cohort_member") is True
        ]
        summary = summary_by_id.get(cohort_id, {})
        groups.append(
            {
                "display_id": OPPORTUNITY_COHORT_DISPLAY_IDS[cohort_id],
                "cohort_id": cohort_id,
                "cohort_role": cohort_role,
                "member_count": len(members),
                "evaluated_count": len(cohort_records),
                "blocked_row_count": sum(
                    record.get("annotation_status")
                    == "excluded_missing_required_fields"
                    for record in cohort_records
                ),
                "empty": not members,
                "caveat": str(
                    summary.get("caveat") or COHORT_CAVEATS[cohort_id]
                ),
                "items": members,
            }
        )

    return {
        "ok": True,
        "available": True,
        "status": "available",
        "message": "",
        "research_only": True,
        "provider_access": False,
        "labels_joined": False,
        "production_change": False,
        "as_of_date": str(metadata.get("as_of_date") or selected_date),
        "config_version": metadata.get("config_version"),
        "source_snapshot_path": metadata.get("source_snapshot_path"),
        "source_output_path": str(source_path),
        "cohort_count": len(groups),
        "groups": groups,
        "caveats": list(OPPORTUNITY_COHORT_CAVEATS),
    }


def _safety_violations(
    metadata: Any,
    records: Any,
    summaries: Any,
) -> list[str]:
    violations: list[str] = []
    if not isinstance(metadata, dict):
        violations.append("missing_metadata")
    else:
        if metadata.get("research_only") is not True:
            violations.append("metadata.research_only_must_be_true")
        if metadata.get("provider_access") is not False:
            violations.append("metadata.provider_access_must_be_false")
        if metadata.get("labels_joined") is not False:
            violations.append("metadata.labels_joined_must_be_false")
        if metadata.get("production_change") is not False:
            violations.append("metadata.production_change_must_be_false")

    if not isinstance(records, list) or any(
        not isinstance(record, dict) for record in records
    ):
        violations.append("records_must_be_a_list_of_objects")
    else:
        forbidden_fields = find_outcome_columns(
            _collect_mapping_keys({"records": records, "cohorts": summaries})
        )
        violations.extend(
            f"forbidden_outcome_field:{field}"
            for field in forbidden_fields
        )
        if any(record.get("research_only") is not True for record in records):
            violations.append("records.research_only_must_be_true")
        unknown_ids = sorted(
            {
                str(record.get("cohort_id"))
                for record in records
                if str(record.get("cohort_id")) not in COHORT_ROLES
            }
        )
        violations.extend(
            f"unknown_cohort_id:{cohort_id}" for cohort_id in unknown_ids
        )

    if not isinstance(summaries, list) or any(
        not isinstance(summary, dict) for summary in summaries
    ):
        violations.append("cohorts_must_be_a_list_of_objects")
    else:
        summary_ids = {
            str(summary.get("cohort_id")) for summary in summaries
        }
        if summary_ids != set(COHORT_ROLES):
            violations.append("cohorts_must_define_exactly_h1_h5")

    return sorted(set(violations))


def _collect_mapping_keys(value: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            keys.append(str(key))
            keys.extend(_collect_mapping_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.extend(_collect_mapping_keys(child))
    return keys


def _empty_groups() -> list[dict[str, Any]]:
    return [
        {
            "display_id": OPPORTUNITY_COHORT_DISPLAY_IDS[cohort_id],
            "cohort_id": cohort_id,
            "cohort_role": cohort_role,
            "member_count": 0,
            "evaluated_count": 0,
            "blocked_row_count": 0,
            "empty": True,
            "caveat": COHORT_CAVEATS[cohort_id],
            "items": [],
        }
        for cohort_id, cohort_role in COHORT_ROLES.items()
    ]


def _unavailable_payload(
    *,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "available": False,
        "status": "unavailable",
        "message": (
            "Research opportunity cohort output unavailable. Generate a "
            "label-free research output first."
        ),
        "research_only": True,
        "provider_access": False,
        "labels_joined": False,
        "production_change": False,
        "as_of_date": as_of_date,
        "config_version": None,
        "source_snapshot_path": None,
        "source_output_path": None,
        "cohort_count": len(COHORT_ROLES),
        "groups": _empty_groups(),
        "caveats": list(OPPORTUNITY_COHORT_CAVEATS),
    }


def _blocked_payload(
    *,
    as_of_date: str,
    source_output_path: Path,
    violations: list[str],
) -> dict[str, Any]:
    return {
        **_unavailable_payload(as_of_date=as_of_date),
        "status": "blocked_unsafe_output",
        "message": "Research opportunity cohort output blocked by safety checks.",
        "source_output_path": str(source_output_path),
        "safety_violations": sorted(set(violations)),
    }


def _latest_output_date(research_dir: Path) -> str | None:
    if not research_dir.exists():
        return None
    pattern = re.compile(
        r"^opportunity_cohorts_(\d{4}-\d{2}-\d{2})\.json$"
    )
    dates = {
        match.group(1)
        for path in research_dir.iterdir()
        if (match := pattern.match(path.name))
    }
    return max(dates) if dates else None


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None

