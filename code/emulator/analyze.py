"""Summarize snapshot replays into the small CSVs committed under results/.

usage: python analyze.py <runs.csv> <hours.csv> <out_prefix> [--boot 2000]

Writes:
  <out_prefix>_summary.csv     pooled metrics per (hour kind, policy, variant), as % of node GPUs
  <out_prefix>_gain.csv        usable-capacity gain over the same policy with original requests, in points,
                               with 95% bootstrap CIs resampling ASWs (ci_*) and, more conservatively, clusters
                               (cl_ci_*; only 10 clusters, and ASWs within a cluster are correlated)
  <out_prefix>_cluster.csv     usable % (8 cores per GPU) per cluster, random hours only
Ratios are pooled (sum of free GPUs / sum of node GPUs), so large ASWs weigh more, as they do in the fleet.
"""
import argparse

import numpy as np
import pandas as pd

SUMS = ["node_gpus", "whole_free", "whole_free_cpu8", "whole_free_cpu16", "frac_residue", "failed_pods", "failed_gpu",
        "fit_1G8C", "fit_1G12C", "fit_4G32C", "fit_8G64C"]


def pooled(g):
    s = g[SUMS].sum()
    n = s.node_gpus
    return pd.Series({
        "snaps": g.snap.nunique(), "runs": len(g),
        "whole_free_pct": 100 * s.whole_free / n,
        "usable_cpu8_pct": 100 * s.whole_free_cpu8 / n,
        "usable_cpu16_pct": 100 * s.whole_free_cpu16 / n,
        "residue_pct": 100 * s.frac_residue / n,
        "failed_pods_per_run": s.failed_pods / len(g),
        "failed_gpu_pct": 100 * s.failed_gpu / n,
        # policies that leave pods unplaced look roomier than they are; charge unplaced GPU demand against the leftover
        "net_usable_cpu8_pct": 100 * (s.whole_free_cpu8 - s.failed_gpu) / n,
        "fit_8G64C_per_run": s.fit_8G64C / len(g),
    })


def gain_ci(df, base, var, col, boot, seed=0, unit="asw_id"):
    keys = ["snap", unit, "policy", "seed"]
    a = df[df.variant == base].set_index(keys)
    b = df[df.variant == var].set_index(keys)
    j = a[[col, "node_gpus"]].join(b[[col]], rsuffix="_v", how="inner")
    j["d"] = j[f"{col}_v"] - j[col]
    per = j.groupby(level=unit)[["d", "node_gpus"]].sum()
    point = 100 * per.d.sum() / per.node_gpus.sum()
    rng = np.random.default_rng(seed)
    idx = np.arange(len(per))
    bs = []
    for _ in range(boot):
        s = rng.choice(idx, len(idx))
        bs.append(100 * per.d.values[s].sum() / per.node_gpus.values[s].sum())
    lo, hi = np.percentile(bs, [2.5, 97.5])
    return point, lo, hi, len(per)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs")
    ap.add_argument("hours")
    ap.add_argument("out_prefix")
    ap.add_argument("--boot", type=int, default=2000)
    a = ap.parse_args()

    d = pd.read_csv(a.runs)
    h = pd.read_csv(a.hours)
    h["tag"] = [f"d{r.day:03d}h{r.hour:02d}" for r in h.itertuples()]
    d = d.merge(h[["tag", "reason"]], on="tag", how="left")
    d["kind"] = np.where(d.reason.str.contains("random"), "random", "spike")

    summ = d.groupby(["kind", "policy", "variant"]).apply(pooled).reset_index()
    summ.round(3).to_csv(f"{a.out_prefix}_summary.csv", index=False)

    sim = d[~d.policy.str.startswith("trace")]
    rows = []
    for kind, g in sim.groupby("kind"):
        for pol, gp in g.groupby("policy"):
            for v in sorted(set(gp.variant) - {"orig"}):
                for col in ["whole_free_cpu8", "whole_free_cpu16"]:
                    p, lo, hi, n = gain_ci(gp, "orig", v, col, a.boot)
                    _, clo, chi, nc = gain_ci(gp, "orig", v, col, a.boot, unit="cluster_id")
                    rows.append(dict(kind=kind, policy=pol, variant=v, metric=col, gain_pts=p, ci_lo=lo, ci_hi=hi,
                                     asws=n, cl_ci_lo=clo, cl_ci_hi=chi, clusters=nc))
    pd.DataFrame(rows).round(3).to_csv(f"{a.out_prefix}_gain.csv", index=False)

    r = d[d.kind == "random"]
    cl = r.groupby(["cluster_id", "policy", "variant"]).apply(pooled)["usable_cpu8_pct"].unstack([1, 2])
    cl.columns = [f"{p}:{v}" for p, v in cl.columns]
    cl.round(2).to_csv(f"{a.out_prefix}_cluster.csv")
    print(summ[summ.kind == "random"].round(2).to_string(index=False))
    print(pd.DataFrame(rows).round(2).to_string(index=False))


if __name__ == "__main__":
    main()
