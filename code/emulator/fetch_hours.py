"""Pull ASI trace hours for the emulator straight from the public ZIP (no cloud account), via HTTP range reads.

usage:
  python fetch_hours.py load  <out.parquet> <first_day> <last_day> [--procs 8]
      Light scan: per cluster-hour, time-weighted GPUs allocated (sum used_gpu_hours) and pod count, held-out
      clusters only. Used to pick spike hours.
  python fetch_hours.py hours <out_dir> <hours.csv> [--procs 8]
      Full fetch for the (day, hour) pairs in hours.csv (columns: day, hour). For each pair it also fetches the
      previous hour's pod ids, because a snapshot at the start of hour h is the pods seen in both h-1 and h.
      Writes pods_d{day}h{hour}.parquet (pod rows, held-out clusters), prev_d{day}h{hour}.parquet (pod_id, server_id of
      h-1) and srv_d{day}h{hour}.parquet (server inventory).

Only the 10 held-out clusters of the LOCO evaluation are kept (read from phase2 outputs).
"""
import argparse
import functools
import os
import sys
import time
from multiprocessing import Pool

import pandas as pd
import pyarrow.compute as pc
import pyarrow.parquet as pq

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scheduler_replay"))
import rzip  # noqa: E402

BASE = "https://tre-clusterdata.oss-cn-hangzhou.aliyuncs.com/cluster-trace-gpu-v2026/data/"
POD_Z, SRV_Z = BASE + "asi_opensource_pod_hourly.zip", BASE + "asi_opensource_server_hourly.zip"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
HELDOUT = sorted(set(pd.read_csv(os.path.join(
    ROOT, "phase2_hourly_analysis/snowflake_outputs/07_capacity_time_weighted__result.csv")).CLUSTER_ID))
POD_COLS = ["pod_id", "workload_id", "server_id", "cluster_id", "gpu_spec_public", "priority_class", "job_type_public",
            "model_type_public", "gpu_request", "cpu_request_cores", "used_gpu_hours", "state_public",
            "gpu_mem_request", "avg_gpu_sm_util", "avg_gpu_mem_gib"]


@functools.lru_cache(None)
def members(url):
    return {m["name"]: m for m in rzip.members(url)}


def read(url, table, day, hour, cols, retries=4):
    name = f"{table}/day={day}/hour={hour:02d}/part-000.parquet"
    for a in range(retries):
        try:
            f = pq.ParquetFile(rzip.open_member(url, members(url)[name]))
            t = f.read(columns=cols)
            return t.filter(pc.is_in(t["cluster_id"], value_set=__import__("pyarrow").array(HELDOUT)))
        except Exception as e:  # network hiccups on a 330 GB remote file are routine
            if a == retries - 1:
                raise
            print(f"retry {table} d{day}h{hour}: {e}", flush=True)
            time.sleep(5 * 2 ** a)


def load_one(dh):
    d, h = dh
    t = read(POD_Z, "asi_opensource_pod_hourly", d, h, ["cluster_id", "used_gpu_hours", "gpu_request"]).to_pandas()
    g = t.groupby("cluster_id").agg(gpu_hours=("used_gpu_hours", "sum"), gpu_req=("gpu_request", "sum"),
                                     pods=("gpu_request", "size")).reset_index()
    g["day"], g["hour"] = d, h
    print(d, h, len(t), flush=True)
    return g


def hours_one(args):
    out, d, h = args
    tag = f"d{d:03d}h{h:02d}"
    if os.path.exists(f"{out}/srv_{tag}.parquet"):
        return tag
    pd_, ph = (d, h - 1) if h > 0 else (d - 1, 23)
    pods = read(POD_Z, "asi_opensource_pod_hourly", d, h, POD_COLS).to_pandas()
    prev = read(POD_Z, "asi_opensource_pod_hourly", pd_, ph, ["pod_id", "server_id", "cluster_id"]).to_pandas()
    srv = read(SRV_Z, "asi_opensource_server_hourly", d, h, None).to_pandas()
    pods.to_parquet(f"{out}/pods_{tag}.parquet")
    prev.to_parquet(f"{out}/prev_{tag}.parquet")
    srv.to_parquet(f"{out}/srv_{tag}.parquet.tmp")
    os.rename(f"{out}/srv_{tag}.parquet.tmp", f"{out}/srv_{tag}.parquet")  # written last: marks the hour complete
    print(tag, len(pods), len(prev), len(srv), flush=True)
    return tag


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["load", "hours"])
    ap.add_argument("out")
    ap.add_argument("a")
    ap.add_argument("b", nargs="?")
    ap.add_argument("--procs", type=int, default=8)
    x = ap.parse_args()
    with Pool(x.procs) as pool:
        if x.mode == "load":
            dhs = [(d, h) for d in range(int(x.a), int(x.b) + 1) for h in range(24)]
            os.makedirs(os.path.dirname(os.path.abspath(x.out)), exist_ok=True)
            parts = pool.map(load_one, dhs, chunksize=1)
            pd.concat(parts, ignore_index=True).to_parquet(x.out)
        else:
            os.makedirs(x.out, exist_ok=True)
            hrs = pd.read_csv(x.a)
            done = pool.map(hours_one, [(x.out, int(r.day), int(r.hour)) for r in hrs.itertuples()], chunksize=1)
            print(f"{len(done)} hours fetched")


if __name__ == "__main__":
    main()
