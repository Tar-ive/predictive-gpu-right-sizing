# Peak-hour robustness check

Does the ~21% reclaim hold through traffic spikes, or does it come from overnight lulls? Results are in §6.5 of the preprint (`sections/peak.tex`).

Runs on Amazon Athena directly against the trace in S3. It reads about 22 GiB of the 328 GiB `pod_hourly` table once (about $0.12); all later queries read the 1.2 GiB extract. The whole analysis cost about $0.27.

## Run order

| Step | File | What it does |
|---|---|---|
| 1 | `sql/01_setup.sql` | Athena database + `pod_hourly` table with partition projection over `day=`/`hour=` folders |
| 2 | `sql/02_slice_sizes.sql` | Distinct slice sizes (run per day range; days 0–5 use an incompatible type) |
| 3 | `sql/03_extract_pop_hourly.sql` | **The one large scan.** Online-inference rec/genai whole-GPU pods, days 157–184, hourly SM and memory need |
| 4 | `sql/04_check.sql` | Row/pod counts and nulls |
| 5 | `sql/05_cluster_hour_deciles.sql` | Per-cluster demand deciles; decile 10 = spike hours |
| 6 | `sql/06_pod_labels.sql` | Per-pod labels: P90, P99, max, P90 and max over spike hours → download as `labels.csv` |
| 7 | `reclaim.py labels.csv` | Snaps labels to the slice ladder, prints the reclaim table, writes `slices.csv` |
| 8 | `sql/07_pod_slice_table.sql` | Upload `slices.csv` to `s3://<bucket>/athena-tables/pod_slice/` first, then register it |
| 9 | `sql/08_overruns_by_decile.sql`, `sql/09_overruns_by_hour.sql` | Share of pod-hours over the slice, shortfall vs reclaimed |
| 10 | `sql/10_cluster_hour_shortfall.sql` | Per cluster-hour shortfall as a share of freed capacity |

`athena.py <file.sql> [--rows N] [--csv out.csv]` runs a file through the AWS CLI and prints the scan size and cost. Set the bucket and database at the top of the file.

## Notes

- Slices are **oracle** (each pod's own realized label), so results measure how much opportunity survives peaks, not model accuracy.
- Hourly averages hide sub-hour bursts; "spike" means high hourly inference demand, not measured latency.
- No trace data is committed here.
