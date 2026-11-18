"""Reusable-capacity metrics shared by the trace placement and the simulator output.

A node's leftover is (whole free GPUs, fractional residue, free CPU cores). A job profile (g GPUs, c cores) fits
min(whole // g, floor(cpu / c)) times on a node. PROFILES is the new-job grid of ASI's fragmentation analysis
(Figure 13 of the OSDI '26 paper): 1G8C, 1G12C, 4G32C, 4G48C, 4G64C, 8G64C, 8G96C, 8G128C.
"""
import math

PROFILES = [(1, 8), (1, 12), (4, 32), (4, 48), (4, 64), (8, 64), (8, 96), (8, 128)]


def fits(whole, cpu, g, c):
    return max(0, min(int(whole) // g, int(math.floor(cpu / c + 1e-9))))


def summarize(nodes):
    """nodes: iterable of (gpu_count, whole_free, frac_residue, cpu_free). Returns a flat dict."""
    out = {"node_gpus": 0, "whole_free": 0, "frac_residue": 0.0, "cpu_free": 0.0,
           "whole_free_cpu8": 0, "whole_free_cpu16": 0}
    for g, c in PROFILES:
        out[f"fit_{g}G{c}C"] = 0
    for gpus, whole, frac, cpu in nodes:
        out["node_gpus"] += gpus
        out["whole_free"] += whole
        out["frac_residue"] += frac
        out["cpu_free"] += cpu
        # whole free GPUs that still have 8 / 16 cores each: "usable with enough CPU"
        out["whole_free_cpu8"] += min(whole, int(cpu // 8))
        out["whole_free_cpu16"] += min(whole, int(cpu // 16))
        for g, c in PROFILES:
            out[f"fit_{g}G{c}C"] += fits(whole, cpu, g, c)
    return out


CAUSES = ["usable", "fractional", "insufficient_cpu", "multi_gpu_shortfall"]


def causes(nodes, g, c):
    """Split free GPU capacity into what a (g GPUs, c cores) job can use and why the rest is lost, in GPUs.

    Per node, after packing as many jobs as fit:
      fractional           partly used GPUs (residue): no whole-GPU job can use them
      insufficient_cpu     whole GPUs left, at least g of them, but fewer than c free cores (ASI's term; FGD's
                           "stranded")
      multi_gpu_shortfall  whole GPUs left, but fewer than g on this node (ASI's "stranded")
    The four parts sum to the free GPU capacity.
    """
    out = dict.fromkeys(CAUSES, 0.0)
    for _, whole, frac, cpu in nodes:
        k = fits(whole, cpu, g, c)
        left = whole - k * g
        out["usable"] += k * g
        out["fractional"] += frac
        out["insufficient_cpu" if left >= g else "multi_gpu_shortfall"] += left
    return out


def trace_nodes(df):
    """Trace placement with ideal sharing: whole free = floor(capacity - sum of requests)."""
    for r in df.itertuples():
        free = max(0.0, r.gpu_count - r.gpu_used)
        whole = int(math.floor(free + 1e-9))
        yield r.gpu_count, whole, free - whole, max(0.0, r.cpu_capacity_cores - r.cpu_used)


def sim_nodes(df):
    """Simulator node-snapshot.csv: per-device milli left; a device is whole-free only at 1000 milli left."""
    dev = [c for c in df.columns if c.startswith("gpu_milli_left_")]
    for _, r in df.iterrows():
        n = int(r["gpu"])
        left = [r[c] for c in dev[:n]]
        whole = sum(1 for x in left if x >= 1000)
        frac = sum(x for x in left if x < 1000) / 1000.0
        yield n, whole, frac, r["cpu_milli_left"] / 1000.0
