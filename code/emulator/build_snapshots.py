"""Turn fetched ASI trace hours into FGD-simulator inputs: one folder per (cluster, ASW, hour, variant).

usage: python build_snapshots.py <hours_dir> <hours.csv> <out_dir> [--asws-per-cluster 3] [--min-servers 8] [--seed 3392]

Snapshot definition
  * Instant = start of hour h. A pod is in the snapshot if it appears in both hour h-1 and hour h (hourly rows include
    pods that lived only part of the hour; summing all of them over-counts allocation, the 115% issue in phase2/sql/05).
  * Scope = one ASW (top-of-rack switch group) of one held-out cluster. Whole clusters (up to 7,400 servers and 350k
    pods) are too large to replay repeatedly, and repacking across ASWs would ignore network topology.
  * ASWs are sampled once per cluster (seeded), so the same servers are compared across hours.

Variants (pod requests)
  orig    trace requests
  a1      test pods in the phase2 pod table get A1's slice (A1_SLICE x GPU_REQUEST, already snapped to the ladder);
          everything else keeps its request. Slices >= 1 GPU round up to whole GPUs (the simulator only shares when
          num_gpu == 1).
  a1cpu   as a1, plus CPU co-sizing: the same pods' CPU request scaled by their slice fraction.
  oracle  CEILING, not a deployable policy: every HP online-inference GPU pod gets its own need in this hour,
          max(SM share, memory share) as in the MVF label, snapped up to the slice ladder. Pods without utilisation
          keep their request. Shows how much repacking could recover if sizing were perfect.
  oraclecpu  as oracle, plus CPU co-sizing.

The simulator caps CPU and GPU only; the server table has no memory capacity, so memory is set to a non-binding value.
Each folder gets nodes.yaml + pods.yaml (simulator format) and the parent gets trace_place.csv: the trace's own placement
(original requests) per server, used to validate the emulator.
"""
import argparse
import json
import math
import os

import numpy as np
import pandas as pd
import yaml

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
POD_TABLE = os.path.join(ROOT, "phase2_hourly_analysis/snowflake_outputs/08_h5_h7__pod_table.csv")
NODE_MEM_MIB = 1 << 24        # non-binding
MAX_PODS_PER_NODE = 5000
LADDER = np.array([1.0])  # set in main() from the trace


def node_doc(name, gpus, cpu_cores, model):
    res = {"alibabacloud.com/gpu-count": str(int(gpus)), "alibabacloud.com/gpu-milli": str(int(gpus) * 1000),
           "cpu": f"{int(cpu_cores) * 1000}m", "memory": f"{NODE_MEM_MIB}Mi", "pods": str(MAX_PODS_PER_NODE)}
    return {"apiVersion": "v1", "kind": "Node",
            "metadata": {"name": name, "labels": {"alibabacloud.com/gpu-card-model": model or "NA",
                                                   "beta.kubernetes.io/os": "linux", "kubernetes.io/hostname": name,
                                                   "kubernetes.io/os": "linux"}},
            "status": {"allocatable": res, "capacity": dict(res)}}


def gpu_ask(g):
    """(num_gpu, gpu_milli) for a GPU request in GPUs."""
    if g <= 0 or np.isnan(g):
        return 0, 0
    if g < 1:
        return 1, max(1, int(round(g * 1000)))
    return int(math.ceil(g - 1e-9)), 1000


def pod_doc(name, cpu_cores, gpus, model):
    cpu_m = max(1, int(round(cpu_cores * 1000)))
    req = {"cpu": f"{cpu_m}m", "memory": "1Mi"}
    ann = {}
    n, milli = gpu_ask(gpus)
    if n:
        ann = {"alibabacloud.com/gpu-milli": str(milli), "alibabacloud.com/gpu-count": str(n),
               "alibabacloud.com/gpu-card-model": model}   # pods stay on the GPU type they ran on
    return {"apiVersion": "v1", "kind": "Pod",
            "metadata": {"name": name, "namespace": "asi", **({"annotations": ann} if ann else {})},
            "spec": {"containers": [{"name": "main", "image": "x", "resources": {"requests": req, "limits": dict(req)}}],
                     "restartPolicy": "OnFailure", "dnsPolicy": "Default"}}


def dump(docs, path):
    with open(path, "w") as f:
        yaml.safe_dump_all(docs, f, default_flow_style=False, sort_keys=False)


def snapshot_pods(hours_dir, tag):
    pods = pd.read_parquet(f"{hours_dir}/pods_{tag}.parquet")
    prev = pd.read_parquet(f"{hours_dir}/prev_{tag}.parquet", columns=["pod_id"])
    pods = pods[pods.server_id.notna() & pods.pod_id.isin(set(prev.pod_id))]
    return pods.drop_duplicates("pod_id", keep="last")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hours_dir")
    ap.add_argument("hours_csv")
    ap.add_argument("out")
    ap.add_argument("--asws-per-cluster", type=int, default=3)
    ap.add_argument("--min-servers", type=int, default=8)
    ap.add_argument("--seed", type=int, default=3392)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rng = np.random.default_rng(a.seed)

    pt = pd.read_csv(POD_TABLE, usecols=["POD_ID", "A1_SLICE", "A3_SLICE", "GPU_REQUEST"]).set_index("POD_ID")
    hrs = pd.read_csv(a.hours_csv)
    tags = [f"d{int(r.day):03d}h{int(r.hour):02d}" for r in hrs.itertuples()]

    # Slice ladder = fractional GPU sizes that pods actually request (as in scheduler_replay/replay.py), plus 1.0.
    global LADDER
    g0 = pd.read_parquet(f"{a.hours_dir}/pods_{tags[0]}.parquet", columns=["gpu_request"]).gpu_request
    LADDER = np.unique(np.round(np.append(g0[(g0 > 0) & (g0 < 1)].values, 1.0), 4))
    print("slice ladder:", LADDER.tolist())

    # Fix the ASW sample from the first hour's inventory: ASWs with >= min_servers servers, per cluster.
    s0 = pd.read_parquet(f"{a.hours_dir}/srv_{tags[0]}.parquet")
    size = s0.groupby(["cluster_id", "asw_id"]).server_id.nunique().reset_index(name="n")
    size = size[size.n >= a.min_servers]
    pick = {}
    for cl, g in size.groupby("cluster_id"):
        k = min(a.asws_per_cluster, len(g))
        pick[cl] = sorted(rng.choice(g.asw_id.values, size=k, replace=False).tolist())
    json.dump(pick, open(f"{a.out}/asw_sample.json", "w"), indent=1)

    trace_rows, meta_rows = [], []
    for tag in tags:
        srv = pd.read_parquet(f"{a.hours_dir}/srv_{tag}.parquet")
        pods = snapshot_pods(a.hours_dir, tag)
        for cl, asws in pick.items():
            for asw in asws:
                S = srv[(srv.cluster_id == cl) & (srv.asw_id == asw)].drop_duplicates("server_id")
                P = pods[pods.server_id.isin(set(S.server_id))].copy()
                if S.empty:
                    continue
                P["a1"] = P.pod_id.map(pt.A1_SLICE)
                P["covered"] = P.a1.notna() & (P.gpu_request > 0)
                P["g_a1"] = np.where(P.covered, P.a1 * P.gpu_request, P.gpu_request)
                P["c_a1"] = np.where(P.covered & (P.a1 < 1), P.cpu_request_cores * P.a1, P.cpu_request_cores)
                # oracle ceiling: this hour's own need, snapped up to the ladder (fractions of the request)
                if "avg_gpu_sm_util" in P:
                    vram = P.gpu_mem_request / 2 ** 30
                    need = np.fmin(1.0, np.fmax(P.avg_gpu_sm_util / P.gpu_request / 100.0,
                                                np.where(vram > 0, P.avg_gpu_mem_gib / vram, np.nan)))
                    ok = (P.gpu_request > 0) & (P.job_type_public == "online_inference") & np.isfinite(need)
                    idx = np.searchsorted(LADDER, np.where(ok, need, 1.0) - 1e-9)
                    frac = np.where(ok, LADDER[np.minimum(idx, len(LADDER) - 1)], 1.0)
                else:
                    ok, frac = np.zeros(len(P), bool), np.ones(len(P))
                P["o_frac"] = frac
                P["oracle_ok"] = ok
                P["g_or"] = P.gpu_request * P.o_frac
                P["c_or"] = np.where(P.o_frac < 1, P.cpu_request_cores * P.o_frac, P.cpu_request_cores)
                P = P.sample(frac=1.0, random_state=a.seed)   # order is reshuffled per run by the simulator seed anyway

                # Trace's own placement, original requests, two scopes. Only HP pods hold guaranteed resources:
                # with HP pods alone no server exceeds its CPU or GPU capacity, while LP pods (preemptible) push GPU
                # and "Other" pods (best-effort, CPU-only) push CPU past capacity. The simulator enforces HP pods.
                for scope, Q in (("all", P), ("hp", P[P.priority_class == "HP"])):
                    tp = Q.groupby("server_id").agg(gpu_used=("gpu_request", "sum"),
                                                     cpu_used=("cpu_request_cores", "sum"), n_pods=("pod_id", "size"))
                    tp = S.set_index("server_id")[["gpu_count", "cpu_capacity_cores", "gpu_spec_public"]].join(tp)
                    tp[["gpu_used", "cpu_used", "n_pods"]] = tp[["gpu_used", "cpu_used", "n_pods"]].fillna(0)
                    trace_rows.append(tp.assign(tag=tag, cluster_id=cl, asw_id=asw, scope=scope).reset_index())
                    if scope == "all":
                        over_gpu = int((tp.gpu_used > tp.gpu_count + 1e-6).sum())
                        over_cpu = int((tp.cpu_used > tp.cpu_capacity_cores + 1e-6).sum())
                    else:
                        over_gpu_hp = int((tp.gpu_used > tp.gpu_count + 1e-6).sum())
                        over_cpu_hp = int((tp.cpu_used > tp.cpu_capacity_cores + 1e-6).sum())
                n_all = len(P)
                P = P[P.priority_class == "HP"]

                snap = f"{cl[:8]}_{asw[:8]}_{tag}"
                nodes = [node_doc(f"{i:04d}-{r.server_id[:12]}", r.gpu_count, r.cpu_capacity_cores, r.gpu_spec_public)
                         for i, r in enumerate(S.itertuples())]
                for var, gcol, ccol in (("orig", "gpu_request", "cpu_request_cores"), ("a1", "g_a1", "cpu_request_cores"),
                                        ("a1cpu", "g_a1", "c_a1"), ("oracle", "g_or", "cpu_request_cores"),
                                        ("oraclecpu", "g_or", "c_or")):
                    d = f"{a.out}/{snap}/{var}"
                    os.makedirs(d, exist_ok=True)
                    dump(nodes, f"{d}/nodes.yaml")
                    dump([pod_doc(f"p{j:06d}", r[ccol], r[gcol], r["gpu_spec_public"])
                          for j, (_, r) in enumerate(P.iterrows())], f"{d}/pods.yaml")
                meta_rows.append(dict(snap=snap, tag=tag, cluster_id=cl, asw_id=asw, servers=len(S),
                                      gpus=int(S.gpu_count.sum()), cpu=int(S.cpu_capacity_cores.sum()), pods_all=n_all,
                                      pods=len(P),
                                      gpu_pods=int((P.gpu_request > 0).sum()), covered_pods=int(P.covered.sum()),
                                      gpu_req_orig=float(P.gpu_request.sum()), gpu_req_a1=float(P.g_a1.sum()),
                                      cpu_req_orig=float(P.cpu_request_cores.sum()), cpu_req_a1cpu=float(P.c_a1.sum()),
                                      oracle_pods=int(P.oracle_ok.sum()), gpu_req_oracle=float(P.g_or.sum()),
                                      cpu_req_oraclecpu=float(P.c_or.sum()),
                                      servers_over_gpu_all=over_gpu, servers_over_cpu_all=over_cpu,
                                      servers_over_gpu_hp=over_gpu_hp, servers_over_cpu_hp=over_cpu_hp))
        print(tag, "done", flush=True)

    pd.concat(trace_rows).to_csv(f"{a.out}/trace_place.csv", index=False)
    m = pd.DataFrame(meta_rows)
    m.to_csv(f"{a.out}/snapshots.csv", index=False)
    print(m.describe().T[["mean", "min", "max"]].to_string())


if __name__ == "__main__":
    main()
