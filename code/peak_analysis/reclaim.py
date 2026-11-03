import sys, numpy as np, pandas as pd
df = pd.read_csv(sys.argv[1])
NARROW = np.array([0.01,0.06,0.07,0.1,0.11,0.15,0.2,0.23,0.25,0.3,0.31,0.46,0.5,1,2,3,4,8,16])
WIDE = np.array([0.01,0.02,0.03,0.04,0.05,0.06,0.07,0.08,0.09,0.1,0.11,0.12,0.14,0.15,0.16,0.19,0.2,0.21,0.22,0.23,0.24,0.25,0.28,0.29,0.3,0.31,0.32,0.33,0.38,0.41,0.43,0.45,0.46,0.48,0.49,0.5,0.62,0.66,0.67,0.7,0.82,1,2,3,4,8,12,16])
def sf(p, req, ladder):
    v = np.clip(p, 0, 1) * req
    i = np.minimum(np.searchsorted(ladder, v - 1e-9, side="left"), len(ladder) - 1)
    s = np.where(v > ladder[-1] + 1e-9, req, ladder[i]); return np.minimum(s, req) / req
df["res"] = df.gpu_request * df.n_hours
nopk = df.n_peak == 0
for c in ["lpk90", "lpkmax"]:
    df[c] = df[c].fillna(df.l90)          # pods never present during a cluster spike: fall back to P90
labels = {"P90 of all hours (paper's target)": "l90", "P90 of spike hours only": "lpk90", "Max of spike hours": "lpkmax",
          "P99 of all hours": "l99", "Max of all hours": "lmax"}
print(f"pods {len(df):,}  reserved GPU-h {df.res.sum():,.0f}  pods never present in a spike hour: {nopk.mean():.1%}")
for lname, ladder in [("narrow (19 sizes, 0.5 -> 1.0)", NARROW), ("wide (48 sizes, incl. 0.62-0.82)", WIDE)]:
    print(f"\nLadder: {lname}")
    print(f"{'slice sized to':36s} {'all':>7s} {'rec':>7s} {'genai':>7s}  {'kept vs P90':>11s}")
    base = None
    for name, col in labels.items():
        f = sf(df[col].values, df.gpu_request.values, ladder)
        df["_r"] = df.res * (1 - f)
        tot = df._r.sum() / df.res.sum()
        by = df.groupby("model_type").apply(lambda g: g._r.sum() / g.res.sum(), include_groups=False)
        base = tot if base is None else base
        print(f"{name:36s} {tot:7.1%} {by.get('rec',np.nan):7.1%} {by.get('genai',np.nan):7.1%}  {tot/base:11.0%}")
        if col == "l90" and ladder is NARROW:
            df[["pod_id","gpu_request"]].assign(sf90=f, sfpk=sf(df.lpkmax.values, df.gpu_request.values, ladder)).to_csv("slices.csv", index=False)
