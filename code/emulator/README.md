# Emulator: is freed GPU capacity reusable?

Right-sizing a pod frees part of its GPU slice, but a freed slice only matters if another job can use it. That takes a
whole free GPU with enough CPU next to it. This folder replays ASI trace snapshots through the
[FGD simulator](https://github.com/hkust-adsl/kubernetes-scheduler-simulator) (Weng et al., ATC '23, Apache-2.0) under
different pod sizes and placement policies. It then counts the whole free GPUs left over that still have 8 or 16 CPU
cores each.

Everything reads the public trace ZIP over HTTP range requests (`../scheduler_replay/rzip.py`), so no cloud account is
needed. Trace data is never committed. Only the small summaries in `results/` are.

## Pipeline

| Step | Script | Output (outside the repo) |
|---|---|---|
| 0. Build and validate the simulator | `patches/`, `validate_fgd.py` | `results/fgd_repro_*.csv` |
| 1. Load per cluster-hour (days 158–183) | `fetch_hours.py load` | `cluster_hour_load.parquet` |
| 2. Pick hours | `select_hours.py` | `hours.csv` (copied to `results/`) |
| 3. Fetch those hours and the hour before | `fetch_hours.py hours` | `hours/{pods,prev,srv}_dDDDhHH.parquet` (~3 GB) |
| 4. Build snapshots | `build_snapshots.py` | `snaps/<cl>_<asw>_<tag>/<variant>/{nodes,pods}.yaml`, `trace_place.csv` |
| 5. Replay | `run_snapshots.py` | one CSV row per (snapshot, variant, policy, seed), plus `trace_all` / `trace_hp` rows |
| 6. Summarize | `analyze.py` | `results/stage*_{summary,gain,cluster}.csv` |

```bash
SIM=../kubernetes-scheduler-simulator     # upstream 8f3d641 + patches/0001-16-gpus-per-node.patch, `make`
D=../emulator_data
uv run --with pandas --with pyarrow python code/emulator/fetch_hours.py load  $D/cluster_hour_load.parquet 158 183
uv run --with pandas --with pyarrow python code/emulator/select_hours.py      $D/cluster_hour_load.parquet $D/hours.csv
uv run --with pandas --with pyarrow python code/emulator/fetch_hours.py hours $D/hours $D/hours.csv
uv run --with pandas --with pyarrow --with pyyaml python code/emulator/build_snapshots.py $D/hours $D/hours.csv $D/snaps
# stage 1: FGD, all sizing variants, one seed
uv run --with pandas --with pyyaml python code/emulator/run_snapshots.py $D/snaps $SIM $D/stage1_fgd.csv \
    --seeds 42 --policies FGD --variants orig a1 a1cpu oracle oraclecpu --procs 14
# stage 2: all six policies, orig vs oracle, three seeds, 8 seeded random hours
uv run --with pandas --with pyyaml python code/emulator/run_snapshots.py $D/snaps $SIM $D/stage2_policies.csv \
    --seeds 42 43 44 --variants orig oracle --tags $(cat code/emulator/results/stage2_tags.txt) --procs 14
uv run --with pandas python code/emulator/analyze.py $D/stage1_fgd.csv $D/hours.csv code/emulator/results/stage1
uv run --with pytest --with pandas --with pyyaml --with pyarrow pytest code/emulator/tests -q
```

Stage 1 is 6,300 simulator runs and took 90 min on 14 cores.

## Design decisions

- **Snapshot.** A snapshot is taken at the start of hour h and holds the pods seen in both h−1 and h. Summing every row of
  an hour counts short-lived pods as if they overlapped.
- **Scope.** Three seeded ASWs (≥ 8 servers) per held-out cluster: 30 ASWs and about 46 servers per snapshot. The same
  servers are used every hour.
- **Hours.** 24 random test hours (seed 3392) plus 2 spike hours per cluster from that cluster's top decile of GPU
  allocation. All 42 hours fall in days 158–183. They were picked before any policy ran.
- **Only HP pods are placed.** With all pods, 61% of servers exceed CPU capacity in the trace, because "Other" pods are
  best-effort and CPU-only, and LP pods are preemptible. With HP pods alone, no server exceeds CPU or GPU. The trace's own
  placement is reported in both scopes (`trace_all`, `trace_hp`).
- **Variants.**
  - `orig`: the trace requests.
  - `a1`: Model A's history-rule slice for the covered test pods in the phase2 pod table.
  - `oracle`: a **ceiling**, not a policy. Each HP online-inference GPU pod gets this hour's average need, snapped up to
    the trace's 38-step slice ladder.
  - `*cpu`: also scales the pod's CPU by the same fraction.
- **Policies.** FGD, BestFit, DotProd, GpuPacking, GpuClustering and Random, using the flags from the authors'
  `generate_config_and_run.py`.
- **Metric.** `whole_free_cpu8` sums, per node, min(whole free GPUs, free cores // 8). `fit_<g>G<c>C` counts how many jobs
  of each profile still fit. Ratios are pooled over node GPUs. CIs are 95% bootstraps over the 30 ASWs.

## Simulator patch

Upstream caps nodes at 8 GPUs (`MaxNumGpuPerNode`), and its node export has 8 hard-coded GPU columns. ASI has 16-GPU
servers. `patches/0001-16-gpus-per-node.patch` raises the cap to 16 and builds the export header from the constant. The
patched build still matches the authors' `expected_results` exactly for all five deterministic policies. Random is
+0.06 points off, within its 0.32 seed SD (`validate_fgd.py`).

## Results: stage 1 (FGD, 720 random-hour snapshots)

| Placement / sizing | Whole free GPUs | Usable, 8 cores/GPU | Usable, 16 cores/GPU | Failed pods / run |
|---|---|---|---|---|
| Trace, all pods counted | 4.1% | 2.8% | 2.3% | n/a |
| Trace, HP pods only | 23.4% | 21.1% | 17.0% | n/a |
| FGD, original requests | 23.2% | 22.0% | 18.0% | 0.03 |
| FGD, A1 | 23.9% | 22.6% | 18.5% | 0.03 |
| FGD, A1 + CPU co-sizing | 23.9% | 22.7% | 18.6% | 0.02 |
| FGD, oracle (ceiling) | 38.9% | 31.5% | 25.1% | 0 |
| FGD, oracle + CPU co-sizing | 40.6% | 40.3% | 33.2% | 0 |

Gains in usable capacity (8 cores per GPU) over FGD with original requests, in points of node GPUs:

| Variant | Gain | 95% CI |
|---|---|---|
| A1 | +0.64 | 0.17 to 1.14 |
| A1 + CPU | +0.74 | 0.19 to 1.33 |
| Oracle | +9.5 | 7.5 to 13.2 |
| Oracle + CPU | +18.3 | 13.8 to 24.5 |

Spike hours give the same picture (`results/stage1_gain.csv`).

1. **The emulator fits the trace.** With original requests, FGD leaves 22.0% usable against the trace's own 21.1% (HP
   scope), and almost every pod places (0.03 failures per snapshot). Total free capacity is equal by construction, so
   this checks fragmentation and feasibility, not allocation (see the audit below).
2. **Accounting matters more than packing.** Counting every pod, as phase2's H12 does, leaves 2.8% usable. Counting only
   pods that hold guaranteed resources leaves 21%. Most of the gap is LP and best-effort pods already filling the spare
   capacity.
3. **A1's gain is real but small,** because A1 covers about 31 of about 500 HP pods per snapshot.
4. **Without CPU, freed GPU capacity is half stranded.** Perfect GPU sizing frees 15.7 points of whole GPUs, but only 9.5
   are usable with 8 cores each. Scaling CPU with the slice makes nearly all of it usable.
5. **Per cluster** (`results/stage1_cluster.csv`): the uniform 2-GPU cluster `3f39b4b6` starts lowest (6.3%) and gains
   most from the oracle.

## Results: stage 2 (six policies, 240 snapshots × 3 seeds)

Eight seeded random hours (`results/stage2_tags.txt`) × 30 ASWs. Some policies leave pods unplaced: GpuClustering and
Random each leave about 15.6% of GPU demand unplaced. Leaving pods out makes leftover capacity look larger, so
policies are compared on **net usable** = usable whole GPUs (8 cores each) − unplaced GPU demand, as % of node GPUs.

| Policy | Unplaced, orig | Net usable, orig | Net usable, oracle | Oracle gain (usable, 95% CI) |
|---|---|---|---|---|
| FGD | 0.01% | 22.9% | 32.4% | +9.5 (7.4–13.4) |
| GpuClustering | 15.6% | 22.9% | 32.7% | +4.8 (2.4–8.2) |
| BestFit | 0.6% | 22.5% | 31.4% | +8.5 (6.5–12.0) |
| GpuPacking | 0.05% | 22.5% | 31.2% | +8.7 (6.8–11.9) |
| DotProd | 5.0% | 22.4% | 30.8% | +8.3 (6.3–11.7) |
| Random | 15.6% | 20.0% | 24.2% | +3.9 (2.8–5.7) |

Seeds barely matter: across the 3 seeds, pooled net usable varies by at most 0.16 points for any policy.

1. **Pod sizing matters far more than placement policy.** With original requests, every non-random policy lands within
   0.6 points of every other on net usable. Perfect sizing adds 8–10 points under every one of them.
2. **FGD is the only policy that places every pod and still leaves the most usable capacity.** GpuClustering ties it on
   net, but only by leaving 15.6% of demand unplaced (24.5% in cluster `6d5f55ee`).
3. **The uniform 2-GPU cluster `3f39b4b6`** has little leftover under any policy (net 2.9–6.2% for non-random policies).
   FGD still does best there (6.2% vs 4.7–4.9% for BestFit/GpuPacking/DotProd). The Stanford report saw no policy
   effect on uniform nodes. Here pods are fractional, which gives FGD something to work with. This is one cluster
   with 3 ASWs, so treat it as a hint only.
4. The net metric charges unplaced demand one-for-one against leftover whole GPUs. That is a rough correction, so
   rankings within about 0.5 points should not be read as real differences.

## Methodology audit (2026-11-13)

Checked after the runs. What holds:

- **Run configuration.**
  - `-tuneseed` seeds Go's global RNG (`pkg/simulator/core.go:102`), which drives the pod shuffle
    (`simulator.go:850`). Workload tuning and inflation are off, so each run places exactly the snapshot's pods.
  - The GPU card-model annotation is enforced as a filter for every policy (`plugin/open_gpu_share.go:96`).
- **Reproducibility.**
  - Rerunning cached runs from scratch gives byte-identical node state for FGD, BestFit and GpuClustering.
  - **Random is not reproducible run to run.** `random_score.go:44` draws from the global RNG inside parallel
    scoring. One snapshot gave 744 vs 723 usable GPUs with the same seed. The authors' own Random reproduction drifts
    for the same reason. Treat Random results as statistical only.
- **Units.**
  - `avg_gpu_sm_util` is summed across a pod's GPUs (up to about 800 for 8-GPU pods), so dividing by `gpu_request`
    gives per-GPU share.
  - `gpu_mem_request` and `avg_gpu_mem_gib` are pod totals.
  - Fractional-GPU pods have no SM telemetry, so their oracle need is memory-only.
- **Where the oracle's freed GPUs come from** (4 hours, sampled ASWs):

  | Pod class | Share of freed GPUs |
  |---|---|
  | Single-GPU pods with full telemetry | 95.1% (84% of them memory-bound) |
  | Pods reporting zero utilisation (possibly missing telemetry) | 2.9% |
  | Fractional pods (memory-only need) | 1.1% |
  | Multi-GPU pods | 0.9% |

  So the doubtful cases do not drive the result.

What it changes:

- **The validation is weaker than "matches the trace within 1 point" suggests.** The emulator and the trace hold the
  same pods on the same servers, so total free GPU is equal by construction. The comparison only tests how leftover
  capacity fragments.
- The real evidence that the emulator is faithful is threefold:
  - the exact FGD reproduction;
  - nearly every trace HP pod fitting on its own ASW's servers under the GPU-type and CPU limits (0.03 failures per
    snapshot), which a wrong unit conversion would break;
  - fragmentation that stays close to the trace's own.
- **ASI Figure 13 cause ordering: partial match** (`fig13_check.py`, `results/fig13_check.csv`; random hours, original
  requests). The expected pattern is taken from the plan's summary of the paper (task 2.4), not re-read from the
  paper itself. Results are the same in all three placements (trace with all pods, trace HP only, FGD):
  - fractional residue is near zero (0.4–2.2% of free GPU) ✓
  - insufficient CPU dominates 1G8C ✓ and 8G128C ✓ (in the all-pods trace it essentially ties: 0.34 vs 0.36)
  - multi-GPU shortfall dominates 8G64C ✓ and 8G96C
  - ✗ for 4G32C, 4G48C and 4G64C, insufficient CPU edges out shortfall (trace HP: 0.10 vs 0.09 at 4G32C). ASI
    expects shortfall there. Possible causes: the ASW sample, the fleet-wide vs ASW scope, or how a node short of
    both GPUs and CPU is attributed (here: shortfall only if fewer than g whole GPUs remain).
- **Profiles fixed.** The first runs used a made-up profile grid. `metrics.PROFILES` now matches ASI Figure 13 (1G8C,
  1G12C, 4G32C, 4G48C, 4G64C, 8G64C, 8G96C, 8G128C). Results were re-scored from the cached runs. The headline
  `whole_free_cpu8/16` metrics are unaffected.
- **Cluster-level CIs.** Only 10 clusters, and ASWs within a cluster are correlated, so `*_gain.csv` now also
  resamples clusters (`cl_ci_*`):

  | Variant (FGD, random hours) | Gain | ASW CI | Cluster CI |
  |---|---|---|---|
  | A1 | +0.64 | 0.17–1.14 | 0.05–1.38 |
  | Oracle | +9.5 | 7.5–13.2 | 7.8–19.8 |
  | Oracle + CPU | +18.3 | 13.8–24.5 | 12.6–38.2 |

  Prefer the cluster CI in the paper.
- **The method is not the FGD paper's.** FGD fills a cluster to saturation by sampling pods and reports allocation
  rate. This study places a fixed snapshot and measures what is left. Only the simulator and policies are borrowed.

## Limitations

- The oracle uses the hourly *average* need. Peaks are higher, so it overstates what any sizing can recover.
- The simulator models CPU and GPU only. The trace has no server memory capacity.
- Snapshots are static, with no arrivals or departures, matching the published FGD method.
- The ASW scope forbids moving pods across ASWs, which is conservative.
- The days 158–183 were seen before the phase2 rules were written (`phase2_hourly_analysis/rules/decision_rules.md`),
  so these results are exploratory, not confirmatory.
