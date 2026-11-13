"""H5 (workload mixing) and H7 on D1 (neighbour priority): descriptive tests on the test days.

Input: H57_PODS exported from sql/08_h5_h7_pod_table.sql (one row per test pod).
Comparisons were fixed before the data were seen: recommendation pods only, server mix in the hour
before admission (rec-dominated >= 80% rec GPU use; GenAI-mixed >= 20% GenAI), fixed effects for
cluster x GPU type, and a within-workload comparison.

Usage: python h5_h7_analysis.py ../snowflake_outputs/08_h5_h7__pod_table.csv
"""
import sys
import warnings
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

warnings.filterwarnings("ignore")
d = pd.read_csv(sys.argv[1])
d.columns = [c.lower() for c in d.columns]
print(pd.crosstab(d.model_type_public, d.priority_class, margins=True))

d = d[d.rec_share.notna()].copy()
d["mix"] = np.select([d.rec_share >= 0.8, d.genai_share >= 0.2], ["rec_homog", "genai_mixed"], "other_mixed")
d["cg"] = d.cluster_id.str[:4] + "|" + d.gpu_spec_public.astype(str)
r = d[d.model_type_public == "rec"].copy()

print("\nH5 need level, rec pods, by mix:")
print(r.groupby("mix").y_mvf.agg(["size", "median", lambda s: s.quantile(.25), lambda s: s.quantile(.75)]).round(4))
m = smf.ols("y_mvf ~ C(mix, Treatment('rec_homog')) + C(cg)", data=r).fit(cov_type="cluster", cov_kwds={"groups": r.cluster_id})
print("cluster x GPU FE:", m.params.filter(like="genai").round(4).to_dict(), m.pvalues.filter(like="genai").round(3).to_dict())
w = r.dropna(subset=["workload_id"])
w = w[w.groupby("workload_id").mix.transform("nunique") > 1]
m = smf.ols("y_mvf ~ C(mix, Treatment('rec_homog')) + C(workload_id)", data=w).fit(cov_type="cluster", cov_kwds={"groups": w.workload_id})
print("within workload:", m.params.filter(like="genai").round(4).to_dict(), m.pvalues.filter(like="genai").round(3).to_dict())

l = r.dropna(subset=["a1_slice"]).copy()
for k in ("a1", "a3"):
    e = l.y_mvf - l[k + "_raw"]
    l[k + "_pin"] = np.maximum(.9 * e, -.1 * e)
    l[k + "_shortsh"] = l[k + "_short_h"] / l.hours
l["a1_U"] = (l.a1_slice < l.y_mvf - 1e-9).astype(float)
print("\nH5 accuracy and safety, GenAI-mixed minus rec-dominated, cluster x GPU FE:")
for v in ("a1_pin", "a3_pin", "a1_U", "a1_shortsh", "a3_shortsh"):
    m = smf.ols(f"{v} ~ C(mix, Treatment('rec_homog')) + C(cg)", data=l).fit(cov_type="cluster", cov_kwds={"groups": l.cluster_id})
    print(f"  {v:10s} {m.params.filter(like='genai').iloc[0]:+.4f} (p={m.pvalues.filter(like='genai').iloc[0]:.3f})")

v = r.dropna(subset=["workload_id"]).groupby(["mix", "workload_id"]).y_mvf.agg(["std", "count"])
v = v[v["count"] >= 5]
a, b = v.loc["rec_homog", "std"], v.loc["genai_mixed", "std"]
both = sorted(set(a.index) & set(b.index))
print(f"\nwithin-workload SD: all workloads Mann-Whitney p={stats.mannwhitneyu(a, b).pvalue:.3f}; "
      f"{len(both)} workloads in both: median {a.loc[both].median():.3f} vs {b.loc[both].median():.3f}, "
      f"Wilcoxon p={stats.wilcoxon(a.loc[both], b.loc[both]).pvalue:.4f}")

print("\nH7 on D1 (neighbour priority), cluster x GPU FE:")
dd = d.dropna(subset=["a1_slice"]).copy()
dd["a1_shortsh"] = dd.a1_short_h / dd.hours
for mt in ("rec", "genai"):
    x = dd[dd.model_type_public == mt]
    for v in ("y_mvf", "a1_shortsh"):
        m = smf.ols(f"{v} ~ hp_share + C(cg)", data=x).fit(cov_type="cluster", cov_kwds={"groups": x.cluster_id})
        print(f"  {mt:5s} {v:10s} slope {m.params['hp_share']:+.4f} p={m.pvalues['hp_share']:.3f}")
