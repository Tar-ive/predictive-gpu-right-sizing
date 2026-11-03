"""E9: run the Model A notebook's own code (setup -> LOCO -> go/no-go gate -> matched-risk reclaim) on one D1 variant.

usage: ISAN_DATA_DIR=<variant dir> ISAN_OUT_DIR=<out dir> [ISAN_NJOBS=4] python run_gate.py

The notebook cells are executed verbatim except for three small shims (no IPython display, configurable
thread count, stop after the matched-risk cell). Results are written to <out dir>/e9_summary.json.
"""
import json
import os
import pathlib

NB = pathlib.Path(__file__).resolve().parents[1] / "ISAN3392_ModelA_RightSizing.ipynb"
LAST_CELL = 28  # matched-risk table; later cells are ablations / interpretation

cells = [c for c in json.load(open(NB))["cells"]]
src = []
for i, c in enumerate(cells):
    if c["cell_type"] != "code" or i > LAST_CELL:
        continue
    s = "".join(c["source"])
    s = s.replace("from IPython.display import display",
                  "display = lambda x: print(x.to_string() if hasattr(x, 'to_string') else x)")
    s = s.replace("N_JOBS = -1", "N_JOBS = int(os.environ.get('ISAN_NJOBS', '-1'))")
    src.append(f"# ---- cell {i}\n{s}")

src.append('''
_summary = dict(
    variant=os.path.basename(DATA_DIR.rstrip("/")), n_rows=int(len(df)), folds=folds_ok, ladder=[float(v) for v in LADDER],
    a1_window=BEST_W, a3_cfg=BEST_A3,
    a1_audit=A1_TABLE.to_dict("records"),
    temporal=TEMPORAL.reset_index()[["model", "pinball", "cov_mond", "U_mond", "R_mond"]].to_dict("records"),
    loco_mean=LOCO.groupby("model")[["pinball", "cov_mond", "U_mond", "R_mond"]].mean().reset_index().to_dict("records"),
    gate=dict(wins=wins, n=n, p_pinball=t_pin["p"], p_R=t_R["p"], R_A3=r3, R_A1=r1, U_A3=u3, go=bool(c_i and c_ii and c_iii)),
    matched=dict(A1=float(MATCH[col("A1")].mean()), A2=float(MATCH[col("A2")].mean()), A3=float(MATCH[col("A3")].mean()),
                 A3_wins=int((MATCH["A3_minus_A1"] > 0).sum()), p=float(t["p"])),
    per_fold=MATCH.reset_index().to_dict("records"),
    cold_share_test=float(df.loc[masks["test"], "cold"].mean()),
)
json.dump(_summary, open(os.path.join(OUT_DIR, "e9_summary.json"), "w"), indent=1, default=float)
print("E9 summary written:", os.path.join(OUT_DIR, "e9_summary.json"))
''')
exec(compile("\n".join(src), str(NB), "exec"), {"__name__": "__main__"})
