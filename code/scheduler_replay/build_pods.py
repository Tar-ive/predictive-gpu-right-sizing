"""Build the per-pod table and hourly need series for the scheduler replay.

usage: python build_pods.py <hourly_dir> <out_dir>

<hourly_dir> holds d{day}h{hour}.parquet files from fetch_trace.py (online-inference pods, gpu_request > 0).
Definitions follow code/e9/sql/01_d1_hourly.sql and 03_pod_summary.sql:
  need_sm  = avg_gpu_sm_util / gpu_request / 100
  need_mem = avg_gpu_mem_gib / (gpu_mem_request / 2^30)
  y (MVF)  = min(1, max(P90 need_sm, P90 need_mem)) over the pod's observed hours
Scope: model_type in (rec, genai). Pods first seen on the first day of the window are left-censored and are
kept only as workload history, never as admissions.
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
cols = ["pod_id", "workload_id", "cluster_id", "gpu_spec_public", "server_gpu_count", "priority_class", "model_type_public",
        "gpu_request", "gpu_mem_request", "cpu_request_cores", "avg_gpu_sm_util", "avg_gpu_mem_gib", "ready_status", "day", "hour"]
STR = ["pod_id", "workload_id", "cluster_id", "gpu_spec_public", "priority_class", "model_type_public"]


def load(f):                                                       # filter and slim each hour first: the window is ~36M rows
    d = pd.read_parquet(f, columns=cols, filters=[("model_type_public", "in", ["rec", "genai"])])
    d["t"] = (d.pop("day").astype("int32") * 24 + d.pop("hour").astype("int32")).astype("int32")
    d["vram"] = (d.pop("gpu_mem_request") / 2**30).astype("float32")
    d["need_sm"] = (d.avg_gpu_sm_util / d.gpu_request / 100.0).astype("float32")
    d["need_mem"] = np.where(d.vram > 0, d.pop("avg_gpu_mem_gib") / d.vram, np.nan).astype("float32")
    d["need"] = np.fmin(1.0, np.fmax(d.need_sm, d.need_mem)).astype("float32")   # hourly need as a fraction of the request
    for c in ["gpu_request", "cpu_request_cores", "server_gpu_count"]: d[c] = d[c].astype("float32")
    return d.drop(columns=["avg_gpu_sm_util"])


h = pd.concat([load(f) for f in sorted(glob.glob(f"{src}/*.parquet"))], ignore_index=True)
for c in STR: h[c] = h[c].astype("category")
T0, T1 = int(h.t.min()), int(h.t.max())
print(f"hours {T0}..{T1} ({T1 - T0 + 1}), rows {len(h):,}, pods {h.pod_id.nunique():,}")

# cluster-hour context (admission-time features): pods, GPUs requested, mean / P90 SM need
ch = h.groupby(["cluster_id", "t"], observed=True).agg(c_pods=("pod_id", "size"), c_gpu=("gpu_request", "sum"),
                                        c_sm_mean=("need_sm", "mean"), c_sm_p90=("need_sm", lambda s: s.quantile(0.9))).reset_index()
ch.to_parquet(f"{out}/cluster_hour.parquet")

h = h.sort_values(["pod_id", "t"])
g = h.groupby("pod_id", sort=False, observed=True)
first = g.head(1).set_index("pod_id")
p = pd.DataFrame({
    "t_adm": g.t.min(), "t_end": g.t.max(), "n_hours": g.size(), "n_util": g.need.count(),
    "y_sm": g.need_sm.quantile(0.9), "y_mem": g.need_mem.quantile(0.9),
    "y_p99": g.need.quantile(0.99), "y_max": g.need.max(), "ready": g.ready_status.max(),
})
p["y"] = np.fmin(1.0, np.fmax(p.y_sm, p.y_mem))
for c in ["workload_id", "cluster_id", "gpu_spec_public", "server_gpu_count", "priority_class", "model_type_public",
          "gpu_request", "vram", "cpu_request_cores"]:
    p[c] = first[c]
p["left_censored"] = p.t_adm == T0
p["right_censored"] = p.t_end == T1
p = p.reset_index()
p.to_parquet(f"{out}/pods.parquet")
h[["pod_id", "t", "need"]].to_parquet(f"{out}/need_hourly.parquet")
print(p.describe(include="all").T[["count", "mean"]].head(25))
