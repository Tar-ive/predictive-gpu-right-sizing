"""Pick snapshot hours: random test hours shared by all clusters, plus spike hours per cluster.

usage: python select_hours.py <cluster_hour_load.parquet> <out_hours.csv> [--random 24] [--spikes-per-cluster 2]
                              [--first-day 158] [--last-day 183] [--seed 3392]

Spike hours: an hour in the top decile of that cluster's time-weighted GPU allocation (sum used_gpu_hours) over the
test days. Hours are drawn without looking at any policy result. The output lists each hour once with its reason(s).
"""
import argparse

import numpy as np
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("load")
    ap.add_argument("out")
    ap.add_argument("--random", type=int, default=24)
    ap.add_argument("--spikes-per-cluster", type=int, default=2)
    ap.add_argument("--first-day", type=int, default=158)
    ap.add_argument("--last-day", type=int, default=183)
    ap.add_argument("--seed", type=int, default=3392)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)

    L = pd.read_parquet(a.load)
    L = L[(L.day >= a.first_day) & (L.day <= a.last_day)]
    L = L[~((L.day == a.first_day) & (L.hour == 0))]          # a snapshot needs the previous hour
    all_hours = L[["day", "hour"]].drop_duplicates().sort_values(["day", "hour"]).to_numpy()

    picks = {}
    for i in rng.choice(len(all_hours), size=a.random, replace=False):
        picks.setdefault(tuple(all_hours[i]), []).append("random")
    for cl, g in L.groupby("cluster_id"):
        top = g[g.gpu_hours >= g.gpu_hours.quantile(0.9)]
        for i in rng.choice(len(top), size=min(a.spikes_per_cluster, len(top)), replace=False):
            r = top.iloc[i]
            picks.setdefault((int(r.day), int(r.hour)), []).append(f"spike:{cl[:8]}")
    out = pd.DataFrame([{"day": d, "hour": h, "reason": "|".join(v)} for (d, h), v in sorted(picks.items())])
    out.to_csv(a.out, index=False)
    print(f"{len(out)} hours ({a.random} random, {sum('spike' in r for r in out.reason)} with a spike)")


if __name__ == "__main__":
    main()
