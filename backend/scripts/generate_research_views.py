from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.research.multi_label import label_candidates, serialize_label_rows_for_csv
from stock_analysis.research.multi_list import build_multi_lists, list_by_id
from stock_analysis.research.universe_quality import build_label_input_rows, build_stock_index


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate static Phase 2.7 multi-label and multi-list research views.")
    parser.add_argument("--date", required=True, help="Output date, for example 2024-01-31.")
    parser.add_argument("--outputs-dir", default=str(REPO_ROOT / "outputs"), help="Root outputs directory.")
    parser.add_argument("--cache-dir", default=str(REPO_ROOT / "data" / "cache" / "daily-use"), help="Local cache directory used only for already-cached stock_universe.csv.")
    parser.add_argument("--top-n", type=int, default=30, help="Maximum rows per generated list.")
    args = parser.parse_args()

    outputs_dir = Path(args.outputs_dir)
    source_files = _source_files(outputs_dir, args.date)
    candidates = _load_json_rows(source_files["candidates"])
    factors = _load_optional_json_rows(source_files["factors"])
    failed_symbols = _load_optional_csv(source_files["failed_symbols"])
    stock_universe = _load_stock_universe(Path(args.cache_dir))

    label_inputs, excluded_non_stock = build_label_input_rows(
        candidates,
        factors=factors,
        failed_symbols=failed_symbols,
        stock_universe=stock_universe,
        as_of_date=args.date,
    )
    labels = label_candidates(
        label_inputs,
        factors=factors,
        failed_symbols=failed_symbols,
        reports_dir=outputs_dir / "reports",
        as_of_date=args.date,
    )
    multi_lists = build_multi_lists(labels, top_n=args.top_n, as_of_date=args.date)
    stock_index = build_stock_index(
        labels,
        excluded_non_stock=excluded_non_stock,
        candidates=candidates,
        factors=factors,
        failed_symbols=failed_symbols,
        multi_lists=multi_lists,
        reports_dir=outputs_dir / "reports",
        as_of_date=args.date,
    )

    labels_dir = outputs_dir / "labels"
    lists_dir = outputs_dir / "lists"
    search_dir = outputs_dir / "search"
    labels_dir.mkdir(parents=True, exist_ok=True)
    lists_dir.mkdir(parents=True, exist_ok=True)
    search_dir.mkdir(parents=True, exist_ok=True)

    label_json = labels_dir / f"candidate_labels_{args.date}.json"
    stock_label_json = labels_dir / f"stock_labels_{args.date}.json"
    label_csv = labels_dir / f"candidate_labels_{args.date}.csv"
    stock_label_csv = labels_dir / f"stock_labels_{args.date}.csv"
    excluded_json = labels_dir / f"excluded_non_stock_{args.date}.json"
    excluded_csv = labels_dir / f"excluded_non_stock_{args.date}.csv"
    multi_list_json = lists_dir / f"multi_lists_{args.date}.json"
    stock_index_json = search_dir / f"stock_index_{args.date}.json"

    _write_json(label_json, labels.to_dict(orient="records"))
    _write_json(stock_label_json, labels.to_dict(orient="records"))
    serialize_label_rows_for_csv(labels).to_csv(label_csv, index=False, encoding="utf-8")
    serialize_label_rows_for_csv(labels).to_csv(stock_label_csv, index=False, encoding="utf-8")
    _write_json(excluded_json, excluded_non_stock)
    pd.DataFrame(excluded_non_stock).to_csv(excluded_csv, index=False, encoding="utf-8")
    _write_json(stock_index_json, stock_index)

    payload = {
        "status": "ok",
        "as_of_date": args.date,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_files": {key: str(path) for key, path in source_files.items() if path.exists()},
        "source_universe_count": len(labels),
        "excluded_non_stock_count": len(excluded_non_stock),
        "stock_index": str(stock_index_json),
        **multi_lists,
    }
    _write_json(multi_list_json, payload)
    by_id = list_by_id(multi_lists)
    for list_id, list_payload in by_id.items():
        _write_json(lists_dir / f"{list_id}_{args.date}.json", list_payload)

    print(
        json.dumps(
            {
                "status": "ok",
                "labels": str(label_json),
                "stock_labels": str(stock_label_json),
                "labels_csv": str(label_csv),
                "excluded_non_stock": str(excluded_json),
                "stock_index": str(stock_index_json),
                "label_count": int(len(labels)),
                "excluded_non_stock_count": int(len(excluded_non_stock)),
                "multi_lists": str(multi_list_json),
                "list_ids": list(by_id),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _source_files(outputs_dir: Path, date: str) -> dict[str, Path]:
    return {
        "candidates": outputs_dir / "daily" / f"candidates_{date}.json",
        "factors": outputs_dir / "daily" / f"factors_{date}.json",
        "failed_symbols": outputs_dir / "errors" / f"failed_symbols_{date}.csv",
    }


def _load_json_rows(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        raise FileNotFoundError(f"Required input file not found: {path}")
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"Expected a JSON list: {path}")
    return rows


def _load_optional_json_rows(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return _load_json_rows(path)


def _load_optional_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _load_stock_universe(cache_dir: Path) -> pd.DataFrame:
    candidates = sorted(cache_dir.rglob("stock_universe.csv")) if cache_dir.exists() else []
    if not candidates:
        return pd.DataFrame()
    return pd.read_csv(candidates[0], dtype=str)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
