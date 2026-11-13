# ============ 19. Export test-day predictions for the hour-by-hour replay ============
# Add this as the LAST cell of ISAN3392_ModelA_RightSizing, then Runtime > Run all.
# It saves, for every test pod, the GPU slice each model would have given it
# (after the conformal safety margin and rounding up to a real slice size).
# Nothing is retrained or changed: it reads the predictions already scored above.

assert "pod_id" in df.columns, "pod_id is not in D1 - the replay needs it to join to the hourly trace"
_parts = []

def _export(name, fold, te_m):
    s = STORE[(name, fold)]
    up = upper_bound(s["pt"], s["strata"], s["g"], s["per"])          # same margins as the U_mond / R_mond results
    sf = slice_fraction(up, s["req"], LADDER)                          # share of the request the pod would get
    d = df.loc[te_m, ["pod_id", "cluster_id", "adm_day_", "adm_hour", "obs_hours", "stratum"]].reset_index(drop=True)
    d["cluster_id"] = d["cluster_id"].astype(str)
    d = d.rename(columns={"adm_day_": "adm_day"})
    d["scenario"] = "temporal" if fold == "temporal" else "loco"     # loco = cluster never seen in training
    d["heldout_cluster"] = None if fold == "temporal" else fold
    d["model"] = name
    d["y_mvf"] = s["yt"]
    d["gpu_request"] = s["req"]
    d["reserved_gpu_hours"] = s["res"]
    d["pred_raw"] = s["pt"]                 # model output before the safety margin
    d["pred_upper"] = up                    # after the margin
    d["slice_frac"] = sf                    # final slice, as a fraction of the request
    d["slice_gpus"] = sf * s["req"]         # final slice in GPUs
    _parts.append(d)

for _name in ("A1", "A2", "A3"):
    _export(_name, "temporal", masks["test"])
    for _c in FOLDS:
        if (_name, _c) in STORE:
            _export(_name, _c, loco_masks(df, masks, _c)["test"])
PRED = pd.concat(_parts, ignore_index=True)

# --- check: the saved slices must reproduce the U and R the notebook already reported ---
def _summ(g):
    return pd.Series(dict(U=float(np.mean(g.slice_frac < g.y_mvf - 1e-9)),
                          R=float(np.sum(g.reserved_gpu_hours * (1 - g.slice_frac)) / np.sum(g.reserved_gpu_hours))))
_chk = PRED[PRED.scenario == "loco"].groupby(["model", "heldout_cluster"]).apply(_summ)
_ref = LOCO.set_index(["model", "fold"])[["U_mond", "R_mond"]]
_ref.index.names = ["model", "heldout_cluster"]
_gap = (_chk.join(_ref)).eval("dU = abs(U - U_mond)\ndR = abs(R - R_mond)")[["dU", "dR"]].max()
print("largest difference from the LOCO table:", _gap.round(6).to_dict())
assert _gap.max() < 1e-6, "saved slices do not match the reported results - do not use this file"

print("\nmean over the 10 unseen clusters (should match the LOCO table above):")
display(_chk.groupby("model").mean().round(4))
print("rows per scenario and model:"); display(PRED.groupby(["scenario", "model"]).size().unstack())
print("pods predicted more than once within one scenario and model:",
      int(PRED.duplicated(["scenario", "model", "pod_id"]).sum()))

_out = os.path.join(OUT_DIR, "PRED_A_V1.parquet")
PRED.to_parquet(_out, index=False)
print(f"\nsaved {len(PRED):,} rows to {_out}")
