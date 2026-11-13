"""H11 fallback: apply the pre-set selection rule to POLICY_RESULT (sql/04_fallback_v1.sql).

Rule (fixed 8 Nov 2026): for each model, on the 'select' half (pods admitted days 158-170), keep the
settings that cut short pod-hours by >= 50% and keep >= 80% of freed GPU-hours versus 'none'; pick the
one freeing the most; report it once on the 'report' half (days 171-183).

Usage: python fallback_selection.py ../snowflake_outputs/04_fallback__policy_result.csv
"""
import sys
import pandas as pd

S = ["pod_hours", "short_hours", "mem_short_hours", "freed_gpu_hours", "reserved_gpu_hours"]


def rates(x):
    x = x.copy()
    x["short"] = x.short_hours / x.pod_hours
    x["mem"] = x.mem_short_hours / x.pod_hours
    x["freed"] = x.freed_gpu_hours / x.reserved_gpu_hours
    return x


d = pd.read_csv(sys.argv[1])
d.columns = [c.lower() for c in d.columns]
d["pol"] = d.policy + "_" + d.param.astype(str)
g = rates(d.groupby(["half", "model", "pol"])[S].sum())
base = g.xs("none_0", level="pol")[["short", "freed"]]
g = g.join(base, on=["half", "model"], rsuffix="_none")
g["cut"] = 1 - g.short / g.short_none
g["kept"] = g.freed / g.freed_none
g["ok"] = (g.cut >= 0.5) & (g.kept >= 0.8)

for m in sorted(d.model.unique()):
    s = g.loc[("select", m)]
    fb = s[s.index.str.startswith("fallback") & s.ok]
    pick = fb.freed.idxmax() if len(fb) else None
    print(f"{m}: chosen on select half -> {pick}")
    if pick:
        r = g.loc[("report", m, pick)]
        print(f"   report half: short {r.short_none:.4f} -> {r.short:.4f} (cut {r.cut:.0%}), "
              f"freed {r.freed_none:.4f} -> {r.freed:.4f} (kept {r.kept:.0%}), rule met: {bool(r.ok)}")

c = rates(d.groupby(["half", "model", "pol", "eval_cluster"])[S].sum())
print("\nreport half, per-cluster mean / worst short pod-hours:")
print(c.loc["report"].groupby(["model", "pol"]).short.agg(["mean", "max"]).round(4).to_string())
