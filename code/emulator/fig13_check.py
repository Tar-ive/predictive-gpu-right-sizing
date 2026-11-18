"""Compare why free GPU capacity is unusable with the cause ordering in ASI's Figure 13 (no pods resized).

usage: python fig13_check.py <snap_dir> <hours.csv> <out.csv> [--policy FGD] [--seed 42]

For each ASI new-job profile, free GPU capacity is split into usable / fractional / insufficient CPU / multi-GPU
shortfall (metrics.causes), pooled over the random-hour snapshots, for three placements: the trace with all pods,
the trace with HP pods only, and the simulator (original requests). Reads cached simulator runs; runs nothing.

The pattern expected from ASI Figure 13 (as recorded in the plan, task 2.4):
  fractional near zero; insufficient CPU dominant for high CPU/GPU profiles (1G8C, 8G128C);
  multi-GPU shortfall dominant for mid sizes (4G32C through 8G64C).
"""
import argparse
import os

import pandas as pd

import metrics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("snap_dir")
    ap.add_argument("hours")
    ap.add_argument("out")
    ap.add_argument("--policy", default="FGD")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    h = pd.read_csv(a.hours)
    tags = {f"d{r.day:03d}h{r.hour:02d}" for r in h.itertuples() if "random" in r.reason}
    meta = pd.read_csv(os.path.join(a.snap_dir, "snapshots.csv"))
    meta = meta[meta.tag.isin(tags)]

    nodes = {"trace_all": [], "trace_hp": [], f"sim_{a.policy}": []}
    tp = pd.read_csv(os.path.join(a.snap_dir, "trace_place.csv"))
    tp = tp[tp.tag.isin(tags)]
    for scope, g in tp.groupby("scope"):
        nodes[f"trace_{scope}"] = list(metrics.trace_nodes(g))
    missing = 0
    for s in meta.snap:
        f = os.path.join(a.snap_dir, s, "runs", f"orig_{a.policy}_{a.seed}", "snapshot", "InitSchedule",
                         "node-snapshot.csv")
        if os.path.exists(f):
            nodes[f"sim_{a.policy}"] += list(metrics.sim_nodes(pd.read_csv(f)))
        else:
            missing += 1

    rows = []
    for placement, ns in nodes.items():
        total = sum(n[0] for n in ns)
        for g, c in metrics.PROFILES:
            parts = metrics.causes(ns, g, c)
            free = sum(parts.values())
            row = {"placement": placement, "profile": f"{g}G{c}C", "node_gpus": total, "free_gpus": free}
            for k, v in parts.items():
                row[f"{k}_share_of_free"] = v / free if free else 0.0
            row["dominant_loss"] = max(metrics.CAUSES[1:], key=lambda k: parts[k])
            rows.append(row)
    out = pd.DataFrame(rows)
    out.round(4).to_csv(a.out, index=False)
    print(f"{len(meta)} snapshots, {missing} simulator runs missing")
    print(out.drop(columns=["node_gpus"]).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
