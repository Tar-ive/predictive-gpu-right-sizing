# Phase 2: Hourly pod analysis in Snowflake

The hourly part of the GPU right-sizing project: loading the Alibaba ASI hourly trace into Snowflake,
replaying Model A's slices hour by hour, testing a fallback, measuring how much freed GPU is usable,
and testing workload mixing. Model A / Model B notebooks and their data live elsewhere in this repo.

## Results in one place

| Test | Result |
| --- | --- |
| Hourly replay | A1 short in 0.44% of pod-hours on unseen clusters (A3: 1.39%), mostly GPU memory; 0.5-1.2% of pods cause 66-73% of short hours |
| H11 fallback | Supported: full request after 6 h short cuts short pod-hours 0.93% -> 0.18%, keeps 95% of savings |
| H8 early resize | Not supported: early use underestimates later need |
| H12 usable capacity | Rejected: 30% of freed GPU-hours form whole GPUs, 3.8% usable with enough CPU |
| H5 workload mixing | Mostly not supported: no difference in need or accuracy once cluster and GPU type are controlled |
| H7 on D1 | Not testable: 99.9% of right-sizing pods are high-priority |

## Run order

| Step | Where | Code | Outputs (`snowflake_outputs/`) |
| --- | --- | --- | --- |
| 1. Load pod-hourly trace, days 158-184, day/hour from folder names | Colab, then Snowflake | `colab/01_load_trace_to_snowflake.py`, `sql/01_load_pod_hourly.sql` | `01_*` |
| 2. Load server inventory | Colab (`TABLE = "asi_opensource_server_hourly"`), then Snowflake | `sql/02_load_server_hourly.sql` | `02_*` |
| 3. Export Model A slices from the notebooks | Colab, last cell of the Model A notebook | `colab/03_export_predictions_v1_cell.py` (v2: `04_...`) | - |
| 4. Upload D1 (as `MODEL_A`) and predictions (as `PRED_A_V1`) | Colab | `colab/02_upload_parquet_to_snowflake.py` | - |
| 5. Hourly replay | Snowflake | `sql/03_hourly_replay_v1.sql` | `03_*` |
| 6. Fallback and early resize | Snowflake, then `analysis/fallback_selection.py` | `sql/04_fallback_v1.sql` | `04_*` |
| 7. Capacity replay | Snowflake, then `analysis/capacity_summary.py` | `sql/07_capacity_replay_time_weighted.sql` | `07_*` |
| 8. Workload mixing (H5) | Snowflake, then `analysis/h5_h7_analysis.py` | `sql/08_h5_h7_pod_table.sql` | `08_*` |
| 9. Optional: v2 hybrid through steps 5-7 | Snowflake | `sql/09_v2_hybrid_tests.sql` | not run yet |

`sql/05` is the first capacity replay, which counted short-lived batch pods for whole hours (115%
allocation); `sql/06` is the diagnosis and `sql/07` the corrected, time-weighted version. Their
outputs are kept for the record.

## Notes

- **No credentials.** Scripts ask for the Snowflake password at run time; fill in your own account
  identifier and username.
- **No data files.** The trace is public; the Snowflake tables are rebuilt by steps 1-4.
- `08_h5_h7__pod_table.csv` (11.6 MB) is one row per test pod; it can be rebuilt with `sql/08`.
- Decision rules, and whether each was fixed before results were seen: `rules/decision_rules.md`.

## Requirements

Python 3.10+, pandas, numpy, scipy, statsmodels, pyarrow, snowflake-connector-python, remotezip.
Snowflake: an X-Small warehouse for most steps, Medium for the large joins (the SQL sets this).
