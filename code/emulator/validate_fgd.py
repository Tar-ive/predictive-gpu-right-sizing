"""Check that our build of the FGD simulator reproduces the authors' published results.

Compares our merged `analysis_allo_discrete.csv` (GPU allocation ratio vs. arrived GPU
demand, 0-130% of capacity) against the authors' cached `expected_results` copy, for every
(workload, policy, seed) row we ran. The yardstick for "close enough" is the authors' own
seed-to-seed spread: with the same seed the run should be near-identical, and any gap should
be far smaller than the spread across seeds 42-51.

usage:
  python validate_fgd.py OURS.csv EXPECTED.csv [--tol 0.5] [--out report.csv]

Exit code 0 if every row's worst gap is <= tol percentage points and the policy ranking at
130% demand matches; 1 otherwise.
"""
import argparse
import os
import sys

import pandas as pd

KEYS = ["workload", "sc_policy", "tune", "seed"]


def load(path):
    df = pd.read_csv(path)
    if "tag" in df.columns:  # merged files may carry a tag column; keep the initial schedule
        df = df[df["tag"].isin(["init_schedule", "schedule_inflation"]) | df["tag"].isna()]
    df["seed"] = df["seed"].astype(int)
    df["tune"] = df["tune"].astype(float)
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ours")
    ap.add_argument("expected")
    ap.add_argument("--tol", type=float, default=0.5, help="max abs gap, percentage points")
    ap.add_argument("--out")
    a = ap.parse_args()

    ours, exp = load(a.ours), load(a.expected)
    points = [c for c in ours.columns if c.isdigit() and c in exp.columns]
    if not points:
        sys.exit("no shared demand columns (0..130) between the two files")
    last = max(points, key=int)

    m = ours.merge(exp, on=KEYS, suffixes=("_ours", "_exp"))
    if m.empty:
        sys.exit("no (workload, policy, tune, seed) rows in common")

    # Seed-to-seed spread in the authors' results, per workload x policy, at full demand.
    spread = (exp.groupby(["workload", "sc_policy"])[last].agg(["std", "min", "max"])
              .rename(columns={"std": "seed_sd", "min": "seed_min", "max": "seed_max"}))

    rows = []
    for _, r in m.iterrows():
        gaps = [abs(r[f"{p}_ours"] - r[f"{p}_exp"]) for p in points]
        s = spread.loc[(r["workload"], r["sc_policy"])]
        rows.append({
            "workload": r["workload"], "policy": r["sc_policy"], "seed": r["seed"],
            f"alloc_{last}_ours": r[f"{last}_ours"], f"alloc_{last}_exp": r[f"{last}_exp"],
            "gap_final_pp": r[f"{last}_ours"] - r[f"{last}_exp"],
            "rel_err_final": (r[f"{last}_ours"] - r[f"{last}_exp"]) / r[f"{last}_exp"],
            "max_gap_pp": max(gaps), "mean_gap_pp": sum(gaps) / len(gaps),
            "seed_sd_pp": s["seed_sd"], "seed_range_pp": s["seed_max"] - s["seed_min"],
        })
    rep = pd.DataFrame(rows).sort_values(["workload", "policy", "seed"])
    pd.set_option("display.width", 200)
    print(rep.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    ok = True
    bad = rep[rep["max_gap_pp"] > a.tol]
    if len(bad):
        ok = False
        print(f"\nFAIL: {len(bad)} row(s) exceed tol={a.tol} pp", file=sys.stderr)

    for (wl, seed), g in rep.groupby(["workload", "seed"]):
        r_ours = list(g.sort_values(f"alloc_{last}_ours", ascending=False)["policy"])
        r_exp = list(g.sort_values(f"alloc_{last}_exp", ascending=False)["policy"])
        same = r_ours == r_exp
        print(f"\nranking at {last}% demand, {wl} seed {seed}: {'MATCH' if same else 'DIFFERENT'}")
        print("  ours:     " + " > ".join(r_ours))
        if not same:
            print("  expected: " + " > ".join(r_exp))
            ok = False

    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        rep.to_csv(a.out, index=False)
    print("\nPASS" if ok else "\nFAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
