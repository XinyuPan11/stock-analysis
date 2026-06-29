# Phase 2.10.1 Validation Bias Limitation Flags

## Why This Phase Exists

Phase 2.10 prevents daily price, factor, scoring, filtering, and ranking inputs from using rows after an `as_of_date`. Future prices remain available only to explicit future-return label calculations.

That protection does not make the complete historical universe point-in-time correct. The current stock-universe and security-status data are current or non-versioned snapshots. A historical validation can therefore remain exposed to survivorship bias or historical status-classification limitations even when its price and factor inputs are correctly guarded.

Phase 2.10.1 makes that distinction visible in validation JSON and Markdown reports. It does not change validation calculations.

## Protected Data Boundary

The following status fields describe the protection supplied by Phase 2.10:

```text
price_point_in_time_guard_applied = true
feature_input_point_in_time_status = guarded
future_label_window_status = explicit_future_only
```

Their meaning is:

- OHLCV inputs used by filters, factors, scores, rankings, and research are restricted to `trade_date <= as_of_date`.
- Future prices are used only by explicit validation labels after candidate features and scores have been fixed.
- The existing factor, score, rank, and future-return formulas are unchanged.

## Snapshot-limited Metadata

The following fields deliberately report a limitation:

```text
universe_point_in_time_status = current_snapshot_limited
listing_status_point_in_time_status = current_snapshot_limited
st_status_point_in_time_status = current_snapshot_limited
suspension_status_point_in_time_status = current_snapshot_limited
```

These values mean that historical membership and status decisions may rely on current or non-versioned metadata. They do not mean that price rows after the as-of date were used.

## Known Bias Limitations

Walk-forward summaries include a machine-readable `known_bias_limitations` list:

```text
historical_universe_membership_not_versioned
historical_listing_delisting_status_not_versioned
historical_st_status_not_versioned
historical_suspension_status_not_fully_versioned
controlled_validation_not_final_production_grade_historical_simulation
```

The generated walk-forward Markdown report repeats the statuses and limitations in a dedicated section so the qualification is not hidden in JSON.

## How To Interpret Phase 2.11 Results

Phase 2.11 results should be interpreted as controlled validation:

1. Price and factor timing is guarded.
2. Future returns are evaluation labels only.
3. Historical universe membership and security status are not yet fully versioned.
4. Results may support comparison across controlled windows, but they are not final production-grade historical simulations.
5. A result must not be described as fully free from survivorship bias until historical universe and status snapshots are available and used.

The existing `no_future_leakage = true` field continues to describe the guarded feature/label date boundary. The new fields qualify the separate universe and status metadata limitation.

## Output Locations

The metadata is included in:

```text
outputs/validation/walk_forward_summary_<as_of_date>_<horizon>d.json
outputs/validation/walk_forward_report_<as_of_date>_<horizon>d.md
```

Controlled validation batch summaries embed the walk-forward summary and therefore retain the same metadata.

## Tests

Run the targeted tests:

```powershell
python -B -m pytest -p no:cacheprovider backend\tests\test_validation_bias_metadata.py backend\tests\test_walk_forward_validation.py -q
```

The tests verify:

- all required point-in-time and snapshot-limitation fields;
- a fresh limitations list for every metadata payload;
- propagation into walk-forward summaries;
- visible limitation language in generated Markdown reports.

No BaoStock access, prewarm, full workflow, or long validation is required.

## Non-goals

Phase 2.10.1 does not:

- reconstruct historical stock-universe membership;
- version listing, delisting, ST, or suspension status;
- alter scoring or ranking formulas;
- alter factor calculations;
- alter validation label definitions or calculations;
- claim production-grade historical simulation quality.
