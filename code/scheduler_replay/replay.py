"""Replay the reverse-engineered scheduler sizing rules and Model A on the ASI trace window, then pack the result.

usage: python replay.py <build_dir> <out_dir>

Sizing policies (fraction s of the requested GPU, snapped up to a deployable slice, never above the request):
  request        what KAI (gpu-fraction annotation), HAMi/Volcano (gpumem default 100%) and kube-scheduler
                 (integer nvidia.com/gpu) allocate: the user's declaration
  koord_85/70    Koordinator LoadAware DefaultEstimator ported to GPU: request x 85% (its cpu factor) or 70% (memory)
  vpa            VPA recommender ported to GPU: decaying histogram (half-life 24 h, 5% buckets, first 0.01),
                 P90 x 1.15, samples = workload hourly need before admission over 8 days; no history -> request
  A1             Model A history rule: P90 of finished same-workload pods' labels (7 d), group fallback, + conformal
  A3             Model A learned: XGBoost tau=0.9 on admission features, + conformal
  hybrid         E6: A1 for warm pods, A3 for cold pods, + conformal
Splits by admission day: train 91-100, calibration 101-103, test 104-109.
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd
import xgboost as xgb

SRC, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
ALPHA, TAU, SEED, HIST_D = 0.05, 0.9, 3392, 7
TRAIN, CAL, TEST = (91, 100), (101, 103), (104, 109)
if os.environ.get("REPLAY_SPLITS"):                       # smoke tests: "a,b,c,d,e,f"
    v = [int(x) for x in os.environ["REPLAY_SPLITS"].split(",")]; TRAIN, CAL, TEST = (v[0], v[1]), (v[2], v[3]), (v[4], v[5])
rng = np.random.default_rng(SEED)

P = pd.read_parquet(f"{SRC}/pods.parquet")
NH = pd.read_parquet(f"{SRC}/need_hourly.parquet")
CH = pd.read_parquet(f"{SRC}/cluster_hour.parquet")
LADDER = np.sort(np.unique(np.round(P.gpu_request.values, 4)))
P["adm_day"] = P.t_adm // 24
P["wl"] = P.workload_id.fillna("")
P["has_wl"] = (P.wl != "").astype(int)

# ---------------- workload history (finished-before-admission rule, as in E9 clean) ----------------
P = P.sort_values("t_adm").reset_index(drop=True)
hist = {k: np.full(len(P), np.nan) for k in ("wl_n", "wl_p90", "wl_max", "wl_mean")}
for wl, g in P[P.wl != ""].groupby("wl"):
    done = g[~g.right_censored].sort_values("t_end"); te, ys = done.t_end.values, done.y.values
    for i, ta in zip(g.index, g.t_adm.values):
        lo, hi = np.searchsorted(te, ta - 24 * HIST_D, "left"), np.searchsorted(te, ta, "left")
        if hi > lo:
            v = ys[lo:hi]; v = v[~np.isnan(v)]
            if len(v):
                hist["wl_n"][i], hist["wl_p90"][i], hist["wl_max"][i], hist["wl_mean"][i] = len(v), np.quantile(v, TAU), v.max(), v.mean()
for k, v in hist.items(): P[k] = v
P["warm"] = P.wl_p90.notna()

# ---------------- VPA decaying histogram over live workload samples ----------------
FIRST, RATIO, MAXV, EPS, HALF = 0.01, 1.05, 1000.0, 1e-4, 24.0           # recovered from the vpa-recommender binary
NB = int(math.ceil(math.log(MAXV * (RATIO - 1) / FIRST + 1) / math.log(RATIO))) + 1
def buckets(v):
    v = np.asarray(v, float); b = np.floor(np.log(np.maximum(v, 0) * (RATIO - 1) / FIRST + 1) / np.log(RATIO)).astype(int)
    return np.where(v < FIRST, 0, np.minimum(NB - 1, b))
def bucket_start(b):
    return 0.0 if b == 0 else FIRST * (RATIO ** b - 1) / (RATIO - 1)
def vpa_percentile(bk, ts, now, q):
    hb = np.bincount(bk, weights=2.0 ** ((ts - now) / HALF), minlength=NB); tot = hb.sum()
    if tot < EPS: return np.nan
    b = int(np.searchsorted(np.cumsum(hb), q * tot - 1e-12, "left"))
    return bucket_start(b + 1) if b < NB - 1 else bucket_start(b)   # VPA returns the bucket's upper end
nh = NH.merge(P[["pod_id", "wl"]], on="pod_id"); nh = nh[(nh.wl != "") & nh.need.notna()].sort_values("t", kind="stable")
wl_samples = {k: (g.t.values, buckets(g.need.values)) for k, g in nh.groupby("wl")}
vpa = np.full(len(P), np.nan)
need_vpa = (P.t_adm // 24 >= TEST[0]).values                     # only the test cohort is sized by VPA
for i in np.flatnonzero(need_vpa):
    wl, ta = P.wl.values[i], P.t_adm.values[i]
    if wl and wl in wl_samples:
        ts, bk = wl_samples[wl]; lo, hi = np.searchsorted(ts, ta - 8 * 24, "left"), np.searchsorted(ts, ta, "left")
        if hi > lo: vpa[i] = vpa_percentile(bk[lo:hi], ts[lo:hi], ta, 0.90)
P["vpa_p90"] = vpa

# ---------------- admission-time features ----------------
CH = CH.copy(); CH["t"] = CH.t + 1                                              # previous-hour utilisation
P = P.merge(CH[["cluster_id", "t", "c_sm_mean", "c_sm_p90"]].rename(columns={"t": "t_adm"}), on=["cluster_id", "t_adm"], how="left")
CH["t"] = CH.t - 1                                                              # same-hour allocation counts
P = P.merge(CH[["cluster_id", "t", "c_pods", "c_gpu"]].rename(columns={"t": "t_adm"}), on=["cluster_id", "t_adm"], how="left")
hr, dow = P.t_adm % 24, (P.t_adm // 24) % 7
P = P.assign(hour_sin=np.sin(2 * np.pi * hr / 24), hour_cos=np.cos(2 * np.pi * hr / 24), dow_sin=np.sin(2 * np.pi * dow / 7),
             dow_cos=np.cos(2 * np.pi * dow / 7), is_frac=(P.gpu_request < 1).astype(int), is_multi=(P.gpu_request > 1).astype(int),
             mem_per_gpu=P.vram / P.gpu_request, cpu_per_gpu=P.cpu_request_cores / P.gpu_request)
NUM = ["gpu_request", "vram", "cpu_request_cores", "server_gpu_count", "mem_per_gpu", "cpu_per_gpu", "hour_sin", "hour_cos",
       "dow_sin", "dow_cos", "is_frac", "is_multi", "has_wl", "c_pods", "c_gpu", "c_sm_mean", "c_sm_p90",
       "wl_n", "wl_p90", "wl_max", "wl_mean"]
CAT = ["gpu_spec_public", "cluster_id", "priority_class", "model_type_public"]
for c in CAT: P[c] = P[c].astype("category")
P["stratum"] = P.model_type_public.astype(str) + "|" + np.where(P.warm, "warm", "cold")

elig = (~P.left_censored) & (P.n_hours >= 24) & P.y.notna()
def days(a, b): return elig & P.adm_day.between(a, b)
M = {"train": days(*TRAIN), "cal": days(*CAL), "test": days(*TEST)}
half = rng.random(len(P)) < 0.5
M["es"], M["cal2"] = M["cal"] & half, M["cal"] & ~half
P["res_h"] = P.gpu_request * P.n_hours
print({k: int(v.sum()) for k, v in M.items()}, "| warm share test %.2f" % P.loc[M["test"], "warm"].mean())

# ---------------- models ----------------
def a1_predict(d, tr):
    fb1 = tr.groupby(["model_type_public", "gpu_spec_public"], observed=True).y.quantile(TAU).to_dict()
    fb2 = tr.groupby("model_type_public", observed=True).y.quantile(TAU).to_dict(); fb3 = tr.y.quantile(TAU)
    fb = np.array([fb1.get((m, g), fb2.get(m, fb3)) for m, g in zip(d.model_type_public, d.gpu_spec_public)], float)
    return np.where(d.wl_p90.notna(), d.wl_p90, np.nan_to_num(fb, nan=fb3))

def a3_fit(tr, es):
    X = lambda d: d[NUM + CAT]
    dtr = xgb.DMatrix(X(tr), tr.y, enable_categorical=True); des = xgb.DMatrix(X(es), es.y, enable_categorical=True)
    prm = dict(objective="reg:quantileerror", quantile_alpha=TAU, max_depth=6, eta=0.05, subsample=0.8, colsample_bytree=0.8,
               min_child_weight=5, tree_method="hist", seed=SEED, nthread=4)
    b = xgb.train(prm, dtr, 2000, evals=[(des, "es")], early_stopping_rounds=50, verbose_eval=False)
    return lambda d: np.clip(b.predict(xgb.DMatrix(X(d), enable_categorical=True), iteration_range=(0, b.best_iteration + 1)), 0, 1), b

def conformal(y, p, a):
    r = np.sort(y - p); n = len(r)
    return float(r[min(int(math.ceil((n + 1) * (1 - a))), n) - 1]) if n else 0.0
def mondrian(yc, pc, sc, a, min_n=200):
    g = conformal(yc, pc, a); return g, {s: (conformal(yc[sc == s], pc[sc == s], a) if (sc == s).sum() >= min_n else g) for s in np.unique(sc)}
def slice_fraction(p_up, req):
    v = np.clip(p_up, 0, 1) * req; i = np.minimum(np.searchsorted(LADDER, v - 1e-9, "left"), len(LADDER) - 1)
    s = np.where(v > LADDER[-1] + 1e-9, req, LADDER[i]); return np.minimum(s, req) / req

tr, cal, te = P[M["train"]], P[M["cal2"]], P[M["test"]]
a3, booster = a3_fit(tr, P[M["es"]])
raw = {"A1": a1_predict, "A3": lambda d, _: a3(d)}
raw["hybrid"] = lambda d, t: np.where(d.warm, a1_predict(d, t), a3(d))
pred_te, up_te = {}, {}
for k, f in raw.items():
    pc, pt = f(cal, tr), f(te, tr)
    g, per = mondrian(cal.y.values, pc, cal.stratum.values, ALPHA)
    q = te.stratum.map(per).fillna(g).values
    pred_te[k], up_te[k] = pt, np.clip(pt + q, 0, 1)

REQ, Y = te.gpu_request.values, te.y.values
S = {"request": np.ones(len(te)),
     "koord_85": slice_fraction(np.full(len(te), 0.85), REQ),
     "koord_70": slice_fraction(np.full(len(te), 0.70), REQ),
     "vpa": np.where(te.vpa_p90.notna(), slice_fraction(np.minimum(1, te.vpa_p90.fillna(1).values * 1.15), REQ), 1.0)}
for k in raw: S[k] = slice_fraction(up_te[k], REQ)

# ---------------- pod-level metrics ----------------
nh_te = NH[NH.pod_id.isin(te.pod_id)].merge(te[["pod_id"]].reset_index().rename(columns={"index": "row"}), on="pod_id")
pos = pd.Series(np.arange(len(te)), index=te.index)
nh_te["i"] = pos.loc[nh_te.row].values
def metrics(s):
    hn = nh_te.dropna(subset=["need"]); over = hn.need.values > s[hn.i.values] + 1e-9
    res = te.res_h.values
    return dict(U=float(np.mean(s < Y - 1e-9)), U_p99=float(np.mean(s < te.y_p99.values - 1e-9)), U_max=float(np.mean(s < te.y_max.values - 1e-9)),
                R=float(np.sum(res * (1 - s)) / np.sum(res)), hour_overrun=float(over.mean()),
                R_warm=float(np.sum((res * (1 - s))[te.warm.values]) / np.sum(res)),
                coverage_policy=float(np.mean(s < 1 - 1e-9)))
POD = {k: metrics(v) for k, v in S.items()}

# matched risk: best reclaim with U <= 5% via a margin sweep on the raw prediction (oracle margin, as notebook cell 28)
def r_at_u(p, u=0.05):
    best = 0.0
    for m in np.linspace(-0.3, 0.7, 101):
        s = slice_fraction(np.clip(p + m, 0, 1), REQ)
        if np.mean(s < Y - 1e-9) <= u: best = max(best, float(np.sum(te.res_h.values * (1 - s)) / np.sum(te.res_h.values)))
    return best
MATCH = {k: r_at_u(pred_te[k]) for k in raw}
MATCH["vpa_tuned"] = r_at_u(np.where(te.vpa_p90.notna(), te.vpa_p90.values, 10.0))   # cold pods stay at the request
MATCH["koord_flat"] = r_at_u(np.zeros(len(te)))                                       # one flat factor for every pod

# ---------------- packing replay (KAI gpupack / HAMi binpack: most-used GPU that fits) ----------------
need_map = nh_te.groupby("i").apply(lambda g: dict(zip(g.t.values, g.need.values)), include_groups=False).to_dict()
def pack(s):
    alloc = s * REQ; tot_gpu_h = 0; overload, shared_h = 0, 0
    for c in te.cluster_id.cat.remove_unused_categories().cat.categories:
        idx = np.flatnonzero(te.cluster_id.values == c)
        ta, tend = te.t_adm.values[idx], te.t_end.values[idx]
        devs = []                                        # each shared device: {"used": float, "pods": set}
        where = {}
        for t in range(int(ta.min()), int(tend.max()) + 1):
            # departures
            for j in [j for j, d in where.items() if tend[np.searchsorted(idx, j)] < t]:
                d = where.pop(j); devs[d]["used"] -= alloc[j]; devs[d]["pods"].discard(j)
            # arrivals in admission order
            for j in idx[ta == t]:
                a = alloc[j]
                if a < 1 - 1e-9:
                    best, bu = -1, -1.0
                    for d, dv in enumerate(devs):
                        if dv["used"] + a <= 1 + 1e-9 and dv["used"] > bu: best, bu = d, dv["used"]
                    if best < 0:
                        empty = [d for d, dv in enumerate(devs) if not dv["pods"]]
                        best = empty[0] if empty else len(devs)
                        if best == len(devs): devs.append({"used": 0.0, "pods": set()})
                    devs[best]["used"] += a; devs[best]["pods"].add(j); where[j] = best
            alive = idx[(ta <= t) & (tend >= t)]
            tot_gpu_h += float(np.ceil(alloc[alive][alloc[alive] >= 1 - 1e-9] - 1e-9).sum()) + sum(1 for dv in devs if dv["pods"])
            for dv in devs:
                if len(dv["pods"]) > 1:
                    shared_h += 1
                    load = sum(need_map.get(j, {}).get(t, 0.0) * REQ[j] for j in dv["pods"])
                    overload += load > 1 + 1e-9
    return dict(gpu_hours=tot_gpu_h, shared_device_hours=shared_h, overloaded_shared_device_hours=int(overload))
PACK = {k: pack(v) for k, v in S.items()}
base = PACK["request"]["gpu_hours"]
for k in PACK: PACK[k]["saving_vs_request"] = 1 - PACK[k]["gpu_hours"] / base

# ---------------- unseen-cluster check (LOCO), as in the paper's gate ----------------
LOCO = []
for c in P.loc[M["test"], "cluster_id"].value_counts().loc[lambda v: v >= 300].index:
    oth, me = P.cluster_id != c, P.cluster_id == c
    trc, esc, calc, tec = P[M["train"] & oth], P[M["es"] & oth], P[M["cal2"] & oth], P[M["test"] & me]
    f3, _ = a3_fit(trc, esc)
    fns = {"A1": lambda d: a1_predict(d, trc), "A3": f3, "hybrid": lambda d: np.where(d.warm, a1_predict(d, trc), f3(d))}
    row = {"cluster": str(c)[:8], "n_test": len(tec), "warm": float(tec.warm.mean())}
    for k, f in fns.items():
        pc, pt = f(calc), f(tec); g, per = mondrian(calc.y.values, pc, calc.stratum.values, ALPHA)
        s_ = slice_fraction(np.clip(pt + tec.stratum.map(per).fillna(g).values, 0, 1), tec.gpu_request.values)
        row[f"{k}_U"] = float(np.mean(s_ < tec.y.values - 1e-9)); row[f"{k}_R"] = float(np.sum(tec.res_h.values * (1 - s_)) / tec.res_h.sum())
    LOCO.append(row)
LOCO = pd.DataFrame(LOCO)
print(LOCO.round(3).to_string()); print("LOCO mean:", LOCO.mean(numeric_only=True).round(4).to_dict())

summary = dict(window_days=[int(P.adm_day.min()), int(P.adm_day.max())], splits={k: int(v.sum()) for k, v in M.items()},
               warm_share_test=float(te.warm.mean()), vpa_coverage_test=float(te.vpa_p90.notna().mean()),
               ladder=[float(v) for v in LADDER], a3_trees=int(booster.best_iteration + 1),
               pod_metrics=POD, matched_R_at_U5=MATCH, packing=PACK,
               loco=LOCO.to_dict("records"), loco_mean=LOCO.mean(numeric_only=True).to_dict())
json.dump(summary, open(f"{OUT}/replay_summary.json", "w"), indent=1)
pd.DataFrame(POD).T.join(pd.DataFrame(PACK).T).to_csv(f"{OUT}/replay_table.csv")
print(pd.DataFrame(POD).T.join(pd.DataFrame(PACK).T).round(4).to_string())
print("matched R at U<=5%:", {k: round(v, 4) for k, v in MATCH.items()})
