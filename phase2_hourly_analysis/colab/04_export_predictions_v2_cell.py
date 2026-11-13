# ============ 24. Export v2 test-day slices for the hourly replay, fallback and capacity tests ============
# Add as the LAST cell of ISAN3392_ModelA_v2_Improvements, then Runtime > Run all (or "Run before" on
# section 20 and then this cell - sections 20-23 are not needed).
# For A1, A3v2 and HYB it saves each test pod's final slice under BOTH margin sets:
#   alloc = per-group risk-budget margins (the v2 deployable setting; HYB R about 18.8%)
#   mond  = 95%-coverage Mondrian margins (as in v1)
# Nothing is retrained: it reads the predictions already scored in sections 16-18.

assert "pod_id" in df.columns, "pod_id is not in D1"
_parts = []

def _export_v2(name, fold):
    s = STORE2[(name, fold)]; it = s["it"]
    for tag, q in (("alloc", s["alloc"]), ("mond", s["per"])):
        up = upper_bound(s["pt"], STRATA2[it], s["g"], q)
        sf = slice_fraction(up, REQ[it], LADDER)
        d = df.iloc[it][["pod_id", "cluster_id", "adm_day_", "adm_hour", "obs_hours"]].reset_index(drop=True)
        d["cluster_id"] = d["cluster_id"].astype(str)
        d = d.rename(columns={"adm_day_": "adm_day"})
        d["stratum"] = STRATA2[it]
        d["scenario"] = "temporal" if fold == "temporal" else "loco"
        d["heldout_cluster"] = None if fold == "temporal" else fold
        d["model"] = name if tag == "alloc" else f"{name}_mond"
        d["y_mvf"] = Y[it]
        d["gpu_request"] = REQ[it]
        d["reserved_gpu_hours"] = RES[it]
        d["pred_raw"] = s["pt"]
        d["pred_upper"] = up
        d["slice_frac"] = sf
        d["slice_gpus"] = sf * REQ[it]
        _parts.append(d)

for _name in ("A1", "A3v2", "HYB"):
    _export_v2(_name, "temporal")
    for _c in FOLDS:
        if (_name, _c) in STORE2:
            _export_v2(_name, _c)
PRED2 = pd.concat(_parts, ignore_index=True)

# --- check: saved slices must reproduce the notebook's own U and R for every model, fold and margin set ---
def _summ(g):
    return pd.Series(dict(U=float(np.mean(g.slice_frac < g.y_mvf - 1e-9)),
                          R=float(np.sum(g.reserved_gpu_hours * (1 - g.slice_frac)) / np.sum(g.reserved_gpu_hours))))
_chk = PRED2[PRED2.scenario == "loco"].groupby(["model", "heldout_cluster"]).apply(_summ)
_gaps = []
for tag in ("alloc", "mond"):
    ref = V2_LOCO[V2_LOCO.model.isin(["A1", "A3v2", "HYB"])].set_index(["model", "fold"])[[f"U_{tag}", f"R_{tag}"]]
    ref.index = pd.MultiIndex.from_tuples([(m if tag == "alloc" else f"{m}_mond", f) for m, f in ref.index], names=["model", "heldout_cluster"])
    j = _chk.join(ref, how="inner")
    _gaps.append(float(max((j.U - j[f"U_{tag}"]).abs().max(), (j.R - j[f"R_{tag}"]).abs().max())))
print("largest difference from V2_LOCO (alloc, mond):", [round(x, 8) for x in _gaps])
assert max(_gaps) < 1e-6, "saved slices do not match the notebook's results - do not use this file"

print("\nmean over unseen clusters (should match the v2 summary: HYB alloc R about 0.188):")
display(_chk.groupby("model").mean().round(4))
print("rows:"); display(PRED2.groupby(["scenario", "model"]).size().unstack())
print("pods predicted twice within one scenario and model:", int(PRED2.duplicated(["scenario", "model", "pod_id"]).sum()))

_out = os.path.join(OUT_DIR, "PRED_A_V2.parquet")
PRED2.to_parquet(_out, index=False)
print(f"\nsaved {len(PRED2):,} rows to {_out}")
