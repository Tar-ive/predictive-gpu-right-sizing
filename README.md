# Predictive GPU Right-Sizing for Production Online Inference

A research proposal built on the Alibaba Serverless Infrastructure (ASI) GPU trace (`cluster-trace-gpu-v2026`, released with Li et al., OSDI '26).

**Authors:** Saksham Adhikari, Sudip Bhandari
**Advisor:** Dr. Fred Zhao
**Course:** ISAN 3392, Texas State University, Fall 2026

## Preprint

- **PDF (v1, Nov 2026):** [GitHub release `preprint-v1`](https://github.com/Tar-ive/predictive-gpu-right-sizing/releases/tag/preprint-v1) · [Google Drive](https://drive.google.com/file/d/174ukA7JwGUImqec95lizQ4ObaArbujNE/view)
- **Cite as:** Adhikari, S., & Bhandari, S. (2026). *Predictive GPU Right-Sizing for Production Online Inference* [Preprint]. Texas State University.

## Summary

We predict two things at admission:

- **Model A (allocation):** the smallest safe GPU slice an online-inference pod needs.
- **Model B (readiness/failure):** the risk that the pod fails to become ready.

At a 5% under-provisioning budget, about 21–25% of reserved online-inference GPU-hours could be reclaimed on clusters never seen in training. Almost all of that comes from recommendation pods that have workload history.

A per-workload history rule captures nearly all of the savings: 20.8% versus 21.9% for XGBoost. As a result, the learned model failed its pre-registered accuracy gate (NO-GO).

Model B separates pods that become ready from those that fail with ROC-AUC 0.75 on known clusters, falling to 0.65 on unseen ones.

The proposal also:

- compares this setting with commercial GPU schedulers;
- separates gaps that modelling or feature engineering can close from gaps the trace imposes;
- quantifies business value;
- designs ten follow-up experiments (E1–E10).

A follow-up round (Oct 15) ran three of them:

- **E6, hybrid policy:** the history rule for warm pods plus the learned model for cold-start pods reclaims 22.6% vs. 20.7% at matched risk (p = 0.014).
- **E7, finer slice sizes:** a what-if that adds about 5 points.
- **E8, per-cluster recalibration:** helps reclaim but does not restore calibration or coverage on unseen clusters.

The remaining experiments cover workload mixing, workload–GPU compatibility, production versus non-production pods, runtime patterns, and safety constraints. **They have been designed but not yet run.**

## Layout

| Path | Contents |
|---|---|
| `main.tex`, `sections/*.tex` | Proposal source |
| `refs.bib` | Bibliography |
| `code/ISAN3392_ModelA_RightSizing.ipynb` | Model A (right-sizing) notebook: A1/A2/A3, LOCO, conformal margins, gate |
| `code/ISAN3392_ModelB_Readiness.ipynb` | Model B (readiness/failure) notebook: B1/B2/B3, calibration, A+B composition |
| `code/isan3392_loader.py` | Memory-safe Parquet loader and feature/split helpers |
| `code/ISAN3392_data_dictionary.md` | Column dictionary for the D1/D2 datasets |
| `scripts/make_figures.py` | Regenerates every figure from the reported numbers |
| `figures/` | Generated figure PDFs |
| `main.pdf` | Compiled proposal |

## Build

```bash
pip install matplotlib numpy
python scripts/make_figures.py
tectonic main.tex        # or: latexmk -pdf main.tex
```

## Data

This repository contains no trace data. Get the trace from the [Alibaba Cluster Trace Program](https://github.com/alibaba/clusterdata).
