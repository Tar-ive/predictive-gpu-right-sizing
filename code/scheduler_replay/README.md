# Scheduler replay: where Model A fits in real GPU schedulers

Run on Nov 3, 2026. We reverse-engineered six open-source GPU schedulers from their release binaries, ported their sizing
rules to GPUs, and replayed them against Model A on 22 days of the ASI trace. The question was where the model adds value
inside a real scheduler, and whether it does.

- **Reverse engineering:** [`re/FINDINGS.md`](re/FINDINGS.md). It covers VPA, kube-scheduler, NVIDIA KAI, HAMi, Volcano and
  Koordinator, read with [REA](https://github.com/morluto/rea) and disassembly, with addresses and constants.
- **Data:** days 90–111 (528 trace-hours), pulled straight from the public trace ZIP with HTTP range requests. That is
  27.3M online-inference pod-hours and 316k rec/genai pods.
- **Results:** `results/replay_summary.json`, `results/replay_table.csv`.

## What the binaries say (short version)

Every scheduler sizes GPUs from **what the user declares**. None of them predicts GPU need:

| Scheduler | Sizing today | Slot for Model A |
|---|---|---|
| KAI | `gpu-fraction` annotation; good packer (`gpupack`) | Webhook sets `gpu-fraction` |
| HAMi / Volcano vGPU | `gpumem`/`gpucores`; **100% of memory if unset** | Webhook sets `gpumem` (memory part of MVF) and `gpucores` (SM part) |
| Koordinator | Usage estimator = request × 85% (cpu) / 70% (mem); **no GPU estimator** | Register a GPU estimator (pluggable by name) |
| kube-scheduler | Integer `nvidia.com/gpu`, scored on requests | Only fewer whole GPUs for multi-GPU pods |
| VPA | P90 × 1.15 of a 24 h-decayed histogram; **cpu/memory only, needs history** | Same rule family; Model A covers cold starts |

## Replay design

- **Splits by admission day:** train 91–100, calibration 101–103, test 104–109.
- **Test cohort:** 10,160 pods (≥ 24 observed hours, same filter as D1).
- **Label:** MVF, as in D1. U is the share of pods sized below their P90 need; R is the reclaimed share of reserved GPU-hours.
- **Policies,** each snapped up to the deployable slice ladder (as in the notebook):
  - *request*: what KAI, HAMi, Volcano and kube-scheduler allocate.
  - *koord_85 / koord_70*: Koordinator's fixed factors applied to GPU.
  - *vpa*: the recovered VPA algorithm (bucket 0.01 / ×1.05, half-life 24 h, P90 × 1.15) on live same-workload samples from
    the 8 days before admission. Pods with no samples keep their request.
  - *A1 / A3 / hybrid*: Model A history rule, XGBoost (τ = 0.9), and E6 hybrid, each with Mondrian conformal margins
    (α = 0.05).
  - *vpa+A3cold*: VPA where it has samples, A3 elsewhere.
- **Packing:** per cluster, pods arrive in admission order and fractional allocations go to the fullest GPU that fits (KAI
  `gpupack` / HAMi binpack). We count GPU-hours used and shared-GPU hours whose co-located pods' actual need exceeds one GPU
  ("overloaded").

## Results (test days 104–109, clusters seen in training)

| Policy | U | U vs P99 label | Hour overrun | Reclaim R | GPU-hours saved by packing | Overloaded / shared GPU-hours |
|---|---|---|---|---|---|---|
| request (KAI/HAMi/Volcano/kube as deployed) | 0 | 0 | 0 | 0 | 0 | 0 / 4,863 |
| Koordinator factor 85% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 / 4,809 |
| Koordinator factor 70% | 2.0% | 2.0% | 2.1% | 2.0% | 2.0% | 0 / 4,494 |
| VPA rule ported to GPU | 3.1% | 7.2% | 1.8% | 13.6% | 12.9% | 5,581 / 67,035 (8.3%) |
| Model A1 (history) | 1.4% | 4.1% | 1.2% | 5.3% | 4.7% | 5,292 / 43,493 (12.2%) |
| **Model A3 (learned)** | **0.95%** | 4.0% | **0.6%** | 8.3% | 7.6% | **2,205 / 70,571 (3.1%)** |
| Model hybrid (E6) | 1.8% | 4.9% | 1.4% | 8.2% | 7.4% | 4,920 / 73,509 (6.7%) |
| VPA + A3 for cold starts | 3.5% | 8.4% | 2.1% | **17.2%** | **16.2%** | 5,761 / 98,372 (5.9%) |

**Matched risk** (best reclaim with U ≤ 5%, oracle margin sweep as in notebook cell 28):

| A1 | VPA tuned | hybrid | A3 | **VPA + A3 cold** | Koordinator flat factor |
|---|---|---|---|---|---|
| 12.3% | 14.6% | 15.8% | 16.0% | **18.6%** | 2.1% |

**Unseen clusters** (leave-one-cluster-out, 10 folds, conformal margins from the other clusters): A1 6.2% (U 0.7%), A3 2.4%
(U 0.1%), hybrid 5.9% (U 0.7%).

## What this means

1. **Fixed factors don't work for GPUs.** Koordinator-style "request × 85%" reclaims nothing: 0.85 of a whole GPU snaps back
   to 1.0 on the slice ladder. Even 70% saves only 2%. A per-pod prediction is needed to get under the slice grid.
2. **Model A beats the incumbent rule at equal risk.** At U ≤ 5% the learned model reclaims 16.0% vs 14.6% for a tuned VPA rule
   and 12.3% for A1. With its default conformal margins, A3 is also the safest policy: it has the fewest under-provisioned pods
   (0.95%), the fewest overrun hours (0.6%) and less than half VPA's overload rate on shared GPUs (3.1% vs 8.3%).
3. **The biggest gain comes from combining them.** VPA can size only 34% of test pods (the rest have no workload samples).
   Filling that cold-start gap with Model A gives the largest saving: **18.6% at U ≤ 5%**, and 16.2% of GPU-hours saved
   after packing at default settings. This is the concrete integration: a VPA-style recommender for warm workloads plus Model A
   for cold ones, written into KAI's `gpu-fraction` or HAMi's `gpumem`/`gpucores` by an admission webhook.
4. **The learned part still doesn't transfer to unseen clusters.** In LOCO, A3 with borrowed conformal margins falls to 2.4%,
   below A1's 6.2%. This is consistent with the paper's NO-GO, so a deployment must calibrate per cluster (E8).
5. **The default VPA margin is not safe enough for GPUs.** 7.2% of pods are under their P99 need and 8.3% of shared GPU-hours
   are overloaded. Conformal margins, not a flat +15%, are what keep A3's risk low.

## Caveats

- This is a 22-day window, not the paper's 185 days. Train and history windows are short (warm share 30%), so absolute
  numbers are lower than the paper's 21% and A1 is weaker here than in D1. The ranking is the result, not the levels.
- Ports, not live systems. We reproduce each scheduler's sizing arithmetic as recovered from the binary. We did not run
  the schedulers against a cluster, and packing treats GPUs as independent devices (no server or NUMA constraints).
- The original trained Model A (`modelA_A3_tau0.90.json`) was not available here, so A1/A3 were retrained with the
  notebook's method on this window. The A3 feature set is a subset of D1's (no ASW features).
- Ghidra was not installable in this environment, so no decompilation. Constants come from disassembly and are cited by
  address in `re/FINDINGS.md`.

## Reproduce

```bash
pip install pyarrow pandas requests xgboost pyelftools
python fetch_trace.py data/pod_online 90 111          # ~35 min, ~2.3 GB
python build_pods.py data/pod_online build             # ~2 min, peaks ~8 GB RAM
python replay.py build results                         # ~2 min
```

Reverse engineering (binaries from `crane export`, `npm install rea-agents@6.8.0`):

```bash
rea inspect-go-binary <bin> --format json
rea inspect-with-objdump <bin> disassemble --symbol '<go function>' --format json
(cd re/gofuncs && go build -o gofuncs .) && python re/godis.py <bin> '<function regex>'
```
