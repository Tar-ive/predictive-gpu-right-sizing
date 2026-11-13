# Decision rules for the hourly analysis

Days 158-183 had already been seen when these rules were written, so all results here are
exploratory, even where the rule was fixed before the test was run.

| Test | Rule | Fixed | Before results? |
| --- | --- | --- | --- |
| Hourly replay (sql/03) | No threshold; reported descriptively | - | No: threshold deferred until after results |
| H11 fallback (sql/04) | Choose k in {1,3,6,12,24} on pods admitted days 158-170: cut short pod-hours >= 50% and keep >= 80% of freed GPU-hours vs no fallback; pick the one freeing most; report once on days 171-183 | 8 Nov 2026 | Yes |
| H8 early resize (sql/04) | Same selection rule as H11 | 8 Nov 2026 | Yes |
| H12 capacity (sql/05-07) | Supported if, under ideal sharing, >= 50% of freed GPU-hours become usable whole-GPU capacity with enough CPU | 8 Nov 2026 | Yes |
| H12 time weighting (sql/07) | Pod-hours weighted by share of the hour present (used_gpu_hours / gpu_request), after the first run (sql/05) showed 115% allocation | 8 Nov 2026 | Method fix after first run; rule unchanged |
| H5 mixing (sql/08) | Recommendation pods only; server mix in the hour before admission; supported if lower need and smaller within-workload spread on rec-dominated servers in most GPU types | 8 Nov 2026 | Yes |
| v2 hybrid (sql/09) | Same rules as H11 and H12, unchanged | 8 Nov 2026 | Hybrid itself was designed after test days were seen |
