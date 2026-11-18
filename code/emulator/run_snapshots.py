"""Replay every snapshot through the FGD simulator under each placement policy, then score leftover capacity.

usage: python run_snapshots.py <snap_dir> <sim_dir> <out.csv> [--seeds 42 43 44] [--procs 12] [--variants orig a1 a1cpu]
                                [--policies ...] [--limit N]

<sim_dir> is a built checkout of hkust-adsl/kubernetes-scheduler-simulator (bin/simon present). Each run places the
snapshot's pods from empty in a seeded random order (the trace has no sub-hour arrival order) and exports the node
state. Unlike the FGD paper, the workload is not inflated or sampled to saturation: each run places exactly the
snapshot's pods. -tuneseed seeds Go's global RNG, which drives the shuffle (tuning itself is off). Deterministic
policies reproduce bit-for-bit; Random does not, because it draws from that RNG inside parallel scoring. Runs are cached: an existing node-snapshot.csv is not re-run.
Also scores the trace's own placement (trace_place.csv) with the same metrics, as policy "trace".
"""
import argparse
import glob
import os
import re
import subprocess
import sys
from multiprocessing import Pool

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import metrics  # noqa: E402

POLICIES = {   # flags as in the authors' run scripts (experiments/run_scripts/expected_run_scripts_0511.sh)
    "Random": ["-Random", "1000", "-gpusel", "random"],
    "DotProd": ["-DotProd", "1000", "-gpusel", "best", "-dimext", "merge", "-norm", "max"],
    "GpuClustering": ["-GpuClustering", "1000"],
    "GpuPacking": ["-GpuPacking", "1000"],
    "BestFit": ["-BestFit", "1000"],
    "FGD": ["-FGD", "1000", "-gpusel", "FGD", "-dimext", "share", "-norm", "max"],
}
FAIL_RE = re.compile(r"failed to schedule pod\(asi/(p\d+)\): <CPU:\s*([\d.]+), GPU: (\d+) x \{(\d+)\}m")


def run_one(job):
    sim, snap_var, policy, seed = job
    # outputs must live OUTSIDE the input folder: simon loads every YAML under -f recursively
    exp = os.path.join(os.path.dirname(snap_var), "runs", f"{os.path.basename(snap_var)}_{policy}_{seed}")
    node_csv = os.path.join(exp, "snapshot", "InitSchedule", "node-snapshot.csv")
    if not os.path.exists(node_csv):
        os.makedirs(exp, exist_ok=True)
        cmd = [sys.executable, "scripts/generate_config_and_run.py", "-d", os.path.abspath(exp), "-e", "-b",
               "-f", os.path.abspath(snap_var), *POLICIES[policy], "-tuneseed", str(seed), "--shuffle-pod=true",
               "-z", os.path.abspath(os.path.join(exp, "snapshot"))]
        with open(os.path.join(exp, "terminal.out"), "w") as f:
            r = subprocess.run(cmd, cwd=sim, stdout=f, stderr=subprocess.STDOUT)
        if r.returncode != 0 or not os.path.exists(node_csv):
            return {"snap_var": snap_var, "policy": policy, "seed": seed, "error": f"rc={r.returncode}"}
    nodes = pd.read_csv(node_csv)
    row = metrics.summarize(metrics.sim_nodes(nodes))
    fails = []
    for log in glob.glob(os.path.join(exp, "log-*.log")):
        with open(log) as f:
            fails += FAIL_RE.findall(f.read())
    row.update(failed_pods=len(fails),
               failed_gpu=sum(int(n) * int(m) / 1000 for _, _, n, m in fails),
               failed_gpu_pods=sum(1 for _, _, n, _ in fails if int(n) > 0))
    snap, var = os.path.basename(os.path.dirname(snap_var)), os.path.basename(snap_var)
    row.update(snap=snap, variant=var, policy=policy, seed=seed)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("snap_dir")
    ap.add_argument("sim_dir")
    ap.add_argument("out")
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    ap.add_argument("--procs", type=int, default=12)
    ap.add_argument("--variants", nargs="+", default=["orig", "a1", "a1cpu"])
    ap.add_argument("--policies", nargs="+", default=list(POLICIES))
    ap.add_argument("--limit", type=int, default=0, help="only the first N snapshots (smoke test)")
    ap.add_argument("--tags", nargs="+", default=None, help="only these hours, e.g. d160h12")
    a = ap.parse_args()

    meta = pd.read_csv(os.path.join(a.snap_dir, "snapshots.csv"))
    if a.tags:
        meta = meta[meta.tag.isin(a.tags)]
    snaps = list(meta.snap)[: a.limit or None]
    jobs = [(a.sim_dir, os.path.join(a.snap_dir, s, v), p, sd)
            for s in snaps for v in a.variants for p in a.policies for sd in a.seeds]
    # largest snapshots first, so the pool doesn't end on one long straggler
    size = dict(zip(meta.snap, meta.pods))
    jobs.sort(key=lambda j: -size[os.path.basename(os.path.dirname(j[1]))])
    print(f"{len(jobs)} runs", flush=True)
    rows = []
    with Pool(a.procs) as pool:
        for i, r in enumerate(pool.imap_unordered(run_one, jobs), 1):
            rows.append(r)
            if i % 50 == 0 or i == len(jobs):
                print(f"{i}/{len(jobs)}", flush=True)

    tp = pd.read_csv(os.path.join(a.snap_dir, "trace_place.csv"))
    for (tag, cl, asw, scope), g in tp.groupby(["tag", "cluster_id", "asw_id", "scope"]):
        snap = f"{cl[:8]}_{asw[:8]}_{tag}"
        if snap in snaps:
            row = metrics.summarize(metrics.trace_nodes(g))
            row.update(snap=snap, variant="orig", policy=f"trace_{scope}", seed=0, failed_pods=0, failed_gpu=0.0,
                       failed_gpu_pods=0)
            rows.append(row)
    out = pd.DataFrame(rows).merge(meta, on="snap", how="left")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    out.to_csv(a.out, index=False)
    errs = out["error"].notna().sum() if "error" in out else 0
    print(f"wrote {len(out)} rows to {a.out}; errors: {errs}")


if __name__ == "__main__":
    main()
