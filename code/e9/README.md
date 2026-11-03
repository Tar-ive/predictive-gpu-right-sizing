# E9: leak-free workload history and peak-aware labels

Rebuilds the Model A dataset (D1) from the raw ASI trace on Amazon Athena, then re-runs the Model A notebook's own
LOCO evaluation and go/no-go gate on four variants. Run on Nov 3, 2026; Athena cost about $1.46.

## Results (unseen clusters, reclaimed share of reserved GPU-hours at U ≤ 5%)

| Variant | History rule (A1) | XGBoost (A3) | Gate |
|---|---|---|---|
| `leaky_p90`: history from pods *admitted* on earlier days (original export) | 20.8% | 21.3% | NO-GO |
| `clean_p90`: history from pods *finished* before admission | 20.8% | 21.0% | NO-GO |
| `clean_p99`: label = P99 of hourly need | 14.3% | 13.0% | NO-GO |
| `clean_max`: label = max of hourly need | 12.9% | 12.2% | NO-GO |

- The rebuild reproduces the original D1 exactly (294,465 pods) and the paper's numbers (A1 20.8%, A3 21.3% vs. 21.9%).
- The leak was real but small: removing it drops A3 by about 0.3 points and its pinball wins from 5/10 to 3/10 clusters.
- With peak-aware labels the history rule beats XGBoost.

## Run order

| Step | File | What it does |
|---|---|---|
| 1 | `sql/01_d1_hourly.sql`, `sql/01b_*.sql` | **Large scan.** Slim hourly table for online-inference rec/genai pods, all 185 days (day 5 hour 06 skipped: INT64 columns) |
| 2 | `sql/02_server_hour.sql` | **Large scan.** Per server-hour allocation over all pods |
| 3 | `sql/03_pod_summary.sql` | Per-pod admission attributes and P90 / P99 / max labels |
| 4 | `sql/04_cluster_hour.sql` | Cluster-hour load from `server_hour` |
| 5 | `sql/05_export.sql` | Pods with a workload id plus every D1 pod, with admission context; download `athena-tables/d1_export/` |
| 6 | `build_d1.py <export_dir> <out_root>` | Builds the four D1 variants and the 27-size slice ladder (`sql/ladder.sql`) |
| 7 | `run_gate.py` | Executes the Model A notebook cells (setup → LOCO → gate → matched risk) on one variant; writes `e9_summary.json` |

```bash
for v in leaky_p90 clean_p90 clean_p99 clean_max; do
  ISAN_DATA_DIR=out_root/$v ISAN_OUT_DIR=results/$v ISAN_NJOBS=4 python run_gate.py
done
```

D1 is the pods admitted on days 14–183 with ≥24 observed hours and both SM and memory labels. That filter reproduces
the original export's row count exactly. Not reproduced: the two ASW (access-switch) features, which are not in `pod_hourly`.
On macOS, XGBoost needs `libomp`; scikit-learn's bundled copy works via `DYLD_LIBRARY_PATH`.
