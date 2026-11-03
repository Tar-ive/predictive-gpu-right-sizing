"""E9: rebuild D1 from the Athena export with leaky vs. leak-free workload history and P90 / P99 / max labels.

usage: python build_d1.py <export_dir> <out_root>

Writes <out_root>/<variant>/ISAN3392_D1_rightsizing.parquet for each variant, plus a D2 file
holding only the deployable slice sizes (the Model A notebook reads its ladder from D2).

History rules (features WL_HIST_*, built from every pod of the same workload in the export):
  day        pods ADMITTED on an earlier day. This is how the original Snowflake export was built.
             A sibling admitted yesterday may still be running, so its label includes hours after
             the current pod's admission: future information.
  completed  pods that FINISHED (last observed hour + 1) at or before the current pod's admission.
"""
import bisect
import glob
import os
import sys

import numpy as np
import pandas as pd

LABELS = {"p90": ("sm_p90", "mem_p90"), "p99": ("sm_p99", "mem_p99"), "max": ("sm_max", "mem_max")}
VARIANTS = {"leaky_p90": ("day", "p90"), "clean_p90": ("completed", "p90"),
            "clean_p99": ("completed", "p99"), "clean_max": ("completed", "max")}
HIST = ["wl_hist_pod_count", "wl_hist_days_observed", "wl_hist_mvf_p90", "wl_hist_mvf_max",
        "wl_hist_mvf_mean", "wl_hist_sm_p90", "wl_hist_dur_mean"]


def q90(sorted_vals):
    n = len(sorted_vals)
    h = 0.9 * (n - 1); lo = int(h); hi = min(lo + 1, n - 1)
    return sorted_vals[lo] + (h - lo) * (sorted_vals[hi] - sorted_vals[lo])


def history(pool, queries, rule):
    """pool/queries: DataFrames sharing workload_id. Returns DataFrame of HIST cols indexed like queries."""
    out = np.full((len(queries), len(HIST)), np.nan)
    pg = pool.groupby("workload_id", sort=False).indices
    for wl, qi in queries.groupby("workload_id", sort=False).indices.items():
        if wl not in pg: continue
        p = pool.iloc[pg[wl]]
        key = (p["adm_day"] if rule == "day" else p["t_end"]).to_numpy()
        o = np.argsort(key, kind="stable"); key = key[o]
        y, sm, dur, day = (p[c].to_numpy()[o] for c in ("mvf", "sm", "n_pod_hours", "adm_day"))
        seen, new = set(), np.zeros(len(o))
        for i, d in enumerate(day):
            if d not in seen: seen.add(d); new[i] = 1
        c_days, c_y, c_dur = np.cumsum(new), np.cumsum(y), np.cumsum(dur)
        c_max = np.maximum.accumulate(y)
        q = queries.iloc[qi]
        thr = (q["adm_day"] if rule == "day" else q["t_first"]).to_numpy()
        ks = np.searchsorted(key, thr, side="left" if rule == "day" else "right")
        order = np.argsort(ks, kind="stable")
        sy, ss, filled = [], [], 0
        for j in order:
            k = ks[j]
            if k == 0: continue
            while filled < k:
                bisect.insort(sy, y[filled]); bisect.insort(ss, sm[filled]); filled += 1
            out[qi[j]] = (k, c_days[k - 1], q90(sy), c_max[k - 1], c_y[k - 1] / k, q90(ss), c_dur[k - 1] / k)
    return pd.DataFrame(out, columns=HIST, index=queries.index)


def main(src, root):
    df = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(os.path.join(src, "*"))) if os.path.getsize(f) > 0],
                   ignore_index=True)
    df["adm_day"] = df["t_first"] // 24
    df["t_end"] = df["t_last"] + 1
    d1 = (df["n_pod_hours"] >= 24) & df["sm_p90"].notna() & df["mem_p90"].notna() & df["adm_day"].between(14, 183)
    print(f"export rows {len(df):,} | D1 rows {d1.sum():,} (original export: 294,465)")

    base = df[d1].copy()
    g = base["gpu_request"].astype(float)
    base["vram_entitled_gib"] = base["gpu_mem_request"] / 2**30
    base["gpu_mem_per_gpu"] = base["vram_entitled_gib"] / g
    base["cpu_per_gpu"] = base["cpu_request_cores"] / g
    base["adm_hour"] = base["t_first"] % 24
    base["adm_dow_idx"] = base["adm_day"] % 7
    base["hour_sin"], base["hour_cos"] = np.sin(2 * np.pi * base.adm_hour / 24), np.cos(2 * np.pi * base.adm_hour / 24)
    base["dow_sin"], base["dow_cos"] = np.sin(2 * np.pi * base.adm_dow_idx / 7), np.cos(2 * np.pi * base.adm_dow_idx / 7)
    base["is_whole_gpu"] = ((g >= 1) & (g == np.floor(g))).astype(int)
    base["is_fractional"] = (g < 1).astype(int)
    base["is_multi_gpu"] = (g > 1).astype(int)
    base["has_workload_id"] = base["workload_id"].notna().astype(int)
    base["server_gpu_occupancy_at_submit"] = base["server_alloc_gpu_at_submit"] / base["server_gpus"]
    base["is_genai_request"] = base["is_genai_request"].astype(float)

    pool_all = df[df["workload_id"].notna()].copy()
    queries = base[base["workload_id"].notna()]
    keep = ["pod_id", "workload_id", "adm_day", "cluster_id", "gpu_spec_public", "priority_class", "model_type_public",
            "gpu_request", "vram_entitled_gib", "cpu_request_cores", "server_gpu_count", "server_cpu_capacity_cores",
            "gpu_mem_per_gpu", "cpu_per_gpu", "adm_hour", "adm_dow_idx", "hour_sin", "hour_cos", "dow_sin", "dow_cos",
            "is_whole_gpu", "is_fractional", "is_multi_gpu", "has_workload_id", "is_genai_request",
            "cluster_pods_at_submit", "cluster_gpu_requested_at_submit", "cluster_sm_mean_prev_hr", "cluster_sm_p90_prev_hr",
            "server_alloc_gpu_at_submit", "server_gpu_occupancy_at_submit", "n_pod_hours", "n_hours_with_util"]

    for name, (rule, lab) in VARIANTS.items():
        sc, mc = LABELS[lab]
        mvf = lambda d: np.minimum(1.0, np.fmax(d[sc], d[mc]))  # noqa: E731
        pool = pool_all.assign(mvf=mvf(pool_all), sm=np.minimum(1.0, pool_all[sc]))
        pool = pool[pool["mvf"].notna()]
        h = history(pool, queries, rule)
        out = base[keep].join(h).assign(y_mvf=mvf(base))
        out["split"] = np.select([out.adm_day <= 129, out.adm_day <= 157], ["train", "val"], "test")
        d = os.path.join(root, name); os.makedirs(d, exist_ok=True)
        out.to_parquet(os.path.join(d, "ISAN3392_D1_rightsizing.parquet"), index=False)
        cold = out["wl_hist_pod_count"].isna().mean()
        print(f"{name:10s} rows {len(out):,} | cold-start {cold:.1%} | y median rec {out.loc[out.model_type_public == 'rec', 'y_mvf'].median():.3f}"
              f" genai {out.loc[out.model_type_public == 'genai', 'y_mvf'].median():.3f}")
    # The ladder is every gpu_request seen among pods admitted on days 14-183 (sql/ladder.sql, 27 sizes).
    sizes = np.array([0.01, 0.02, 0.06, 0.07, 0.1, 0.11, 0.15, 0.19, 0.2, 0.21, 0.23, 0.24, 0.25, 0.29, 0.3,
                      0.31, 0.32, 0.33, 0.46, 0.5, 0.7, 1.0, 2.0, 3.0, 4.0, 8.0, 16.0])
    for name in VARIANTS:
        pd.DataFrame({"gpu_request": sizes}).to_parquet(os.path.join(root, name, "ISAN3392_D2_sizes.parquet"), index=False)
    print(f"slice ladder: {len(sizes)} sizes: {sizes}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
