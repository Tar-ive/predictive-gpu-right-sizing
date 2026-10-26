# Predictive GPU Right-Sizing for Production Online Inference

A research proposal built on the Alibaba Serverless Infrastructure (ASI) GPU trace (`cluster-trace-gpu-v2026`, released with Li et al., OSDI '26).

**Authors:** Saksham Adhikari, Sudip Bhandari
**Advisor:** Dr. Fred Zhao
**Course:** ISAN 3392, Texas State University, Fall 2026

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

The follow-up experiments cover workload mixing, workload–GPU compatibility, production versus non-production pods, runtime patterns, and safety constraints. **They have been designed but not yet run.**

## Layout

| Path | Contents |
|---|---|
| `main.tex`, `sections/*.tex` | Proposal source |
| `refs.bib` | Bibliography |
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
