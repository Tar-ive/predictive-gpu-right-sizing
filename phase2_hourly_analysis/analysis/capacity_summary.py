"""H12 capacity replay: share of freed GPU-hours that becomes usable whole-GPU capacity.

Input: SIM2_RESULT exported from sql/07_capacity_replay_time_weighted.sql.
Rule (fixed 8 Nov 2026): H12 supported if, under ideal sharing, >= 50% of freed GPU-hours become
usable whole-GPU capacity with enough CPU.

Usage: python capacity_summary.py ../snowflake_outputs/07_capacity_time_weighted__result.csv
"""
import sys
import pandas as pd

d = pd.read_csv(sys.argv[1])
d.columns = [c.lower() for c in d.columns]
d["whole_gain"] = d.free_whole_new_ideal - d.free_whole_base_ideal
d["ideal_gain"] = d.usable_new_ideal - d.usable_base_ideal
d["noshare_gain"] = d.usable_new_noshare - d.usable_base_noshare

t = d.groupby("policy")[["gpu_hours_freed", "whole_gain", "ideal_gain", "noshare_gain"]].sum()
for c in ("whole_gain", "ideal_gain", "noshare_gain"):
    t[c + "_share"] = t[c] / t.gpu_hours_freed
print(t.round(3).to_string())
print("\nH12 supported (ideal sharing >= 50%):", (t.ideal_gain_share >= 0.5).to_dict())

a = d[d.policy == "A1_fallback6"].copy()
print("\nallocation (unweighted / time-weighted):",
      round(a.gpu_hours_alloc_unweighted.sum() / a.gpu_hours_capacity.sum(), 3),
      round(a.gpu_hours_alloc_weighted.sum() / a.gpu_hours_capacity.sum(), 3))
print("free whole GPUs with enough CPU before shrinking:",
      round(a.usable_base_ideal.sum() / a.free_whole_base_ideal.sum(), 3))
a["cluster"] = a.cluster_id.str[:4]
a["whole_share"] = a.whole_gain / a.gpu_hours_freed
a["usable_share"] = a.ideal_gain / a.gpu_hours_freed
a["cpu_ok_before"] = a.usable_base_ideal / a.free_whole_base_ideal
print(a[["cluster", "gpu_hours_freed", "whole_share", "usable_share", "cpu_ok_before"]]
      .sort_values("gpu_hours_freed", ascending=False).round(3).to_string(index=False))
