# ISAN 3392 — Training Dataset Dictionary

Exported 2026-09-28 11:09 from Snowflake `ALIBABA_CLUSTER_DATA.PUBLIC`,
derived from the Alibaba ASI six-month GPU trace (`cluster-trace-gpu-v2026`, OSDI 26).

## Scope

`job_type_public='online_inference'` AND `model_type_public IN ('rec','genai')` AND `gpu_request > 0`

## Splits (by admission day = pod first observed hour)

| split | days | purpose |
|---|---|---|
| warmup | 0–13 | history only, excluded from datasets |
| train | 14–129 | fitting |
| val | 130–157 | tuning, early stopping, conformal calibration |
| test | 158–183 | touched once |
| tail | 184 | label completion only, excluded |

## Targets

**D1 `Y_MVF`** — minimum viable GPU fraction, clipped to 1.0:

```
MVF = max( P90(avg_gpu_sm_util / gpu_request) / 100 ,
          P90(avg_gpu_mem_gib / (gpu_mem_request/1024^3)) )
```

Validated against the pre-existing `MIN_VIABLE_FRACTION`: correlation 1.0000 (rec), 0.9999 (genai), mean abs diff 0.

**D2 `Y_READY`** — pod became ready at admission, from `POD_HOURLY_T` (~99.9% populated across all 185 days).

> `JOB_EXECUTION_SUMMARY` was deliberately NOT used as the D2 label source: it covers only 0.3–7% of days 0–99 and 100% of days 120+, which made the train split an 11% biased sample. Its label is retained as `Y_READY_JES_CROSSCHECK` where available.

## Leakage rules

- Every feature is computable at admission time.
- All `WL_HIST_*` features use **strictly earlier days** (expanding window, current day excluded).
- Utilisation-based cluster load uses the **previous** hour; allocation counts use the admission hour.
- Target-derived columns (`avg_gpu_sm_util`, `sm_p90_norm`, `mem_frac_p90`, `waste_tier`, …) are absent by assertion.

## Loading (important)

Snowflake `NUMBER` columns arrive as Python `Decimal` objects. Naively loaded, D2 occupies **6,214 MB**; coerced it occupies **456 MB** (13.6x). Use `isan3392_loader.py`.

## `ISAN3392_D1_rightsizing.parquet`  —  294,465 rows

| column | type | role |
|---|---|---|
| `POD_ID` | TEXT | identifier / grouping key — not a feature |
| `WORKLOAD_ID` | TEXT | identifier / grouping key — not a feature |
| `ADM_DAY` | NUMBER | diagnostic — not a feature |
| `SPLIT` | TEXT | split label — not a feature |
| `GPU_REQUEST` | FLOAT | numeric feature (admission-time) |
| `VRAM_ENTITLED_GIB` | FLOAT | numeric feature (admission-time) |
| `CPU_REQUEST_CORES` | FLOAT | numeric feature (admission-time) |
| `SERVER_GPU_COUNT` | FLOAT | numeric feature (admission-time) |
| `SERVER_CPU_CAPACITY_CORES` | FLOAT | numeric feature (admission-time) |
| `GPU_MEM_PER_GPU` | FLOAT | numeric feature (admission-time) |
| `CPU_PER_GPU` | FLOAT | numeric feature (admission-time) |
| `ADM_HOUR` | NUMBER | numeric feature (admission-time) |
| `ADM_DOW_IDX` | NUMBER | numeric feature (admission-time) |
| `HOUR_SIN` | FLOAT | numeric feature (admission-time) |
| `HOUR_COS` | FLOAT | numeric feature (admission-time) |
| `DOW_SIN` | FLOAT | numeric feature (admission-time) |
| `DOW_COS` | FLOAT | numeric feature (admission-time) |
| `IS_WHOLE_GPU` | NUMBER | numeric feature (admission-time) |
| `IS_FRACTIONAL` | NUMBER | numeric feature (admission-time) |
| `IS_MULTI_GPU` | NUMBER | numeric feature (admission-time) |
| `HAS_WORKLOAD_ID` | NUMBER | numeric feature (admission-time) |
| `CLUSTER_PODS_AT_SUBMIT` | NUMBER | numeric feature (admission-time) |
| `CLUSTER_GPU_REQUESTED_AT_SUBMIT` | FLOAT | numeric feature (admission-time) |
| `CLUSTER_SM_MEAN_PREV_HR` | FLOAT | numeric feature (admission-time) |
| `CLUSTER_SM_P90_PREV_HR` | FLOAT | numeric feature (admission-time) |
| `SERVER_ALLOC_GPU_AT_SUBMIT` | FLOAT | numeric feature (admission-time) |
| `SERVER_GPU_OCCUPANCY_AT_SUBMIT` | FLOAT | numeric feature (admission-time) |
| `ASW_PODS_AT_SUBMIT` | NUMBER | numeric feature (admission-time) |
| `ASW_ALLOC_GPU_AT_SUBMIT` | FLOAT | numeric feature (admission-time) |
| `WL_HIST_POD_COUNT` | NUMBER | feature — workload history (prior days only) |
| `WL_HIST_DAYS_OBSERVED` | NUMBER | feature — workload history (prior days only) |
| `WL_HIST_MVF_P90` | FLOAT | feature — workload history (prior days only) |
| `WL_HIST_MVF_MAX` | FLOAT | feature — workload history (prior days only) |
| `WL_HIST_MVF_MEAN` | FLOAT | feature — workload history (prior days only) |
| `WL_HIST_SM_P90` | FLOAT | feature — workload history (prior days only) |
| `WL_HIST_DUR_MEAN` | NUMBER | feature — workload history (prior days only) |
| `GPU_SPEC_PUBLIC` | TEXT | categorical feature |
| `CLUSTER_ID` | TEXT | categorical feature |
| `PRIORITY_CLASS` | TEXT | categorical feature |
| `MODEL_TYPE_PUBLIC` | TEXT | categorical feature |
| `IS_GENAI_REQUEST` | BOOLEAN | categorical feature |
| `ASW_ID` | TEXT | categorical feature |
| `N_POD_HOURS` | NUMBER | diagnostic — not a feature |
| `N_HOURS_WITH_UTIL` | NUMBER | diagnostic — not a feature |
| `IS_CENSORED` | NUMBER | diagnostic — not a feature |
| `Y_MVF` | FLOAT | **TARGET** |

## `ISAN3392_D2_placement.parquet`  —  2,826,036 rows

| column | type | role |
|---|---|---|
| `POD_ID` | TEXT | identifier / grouping key — not a feature |
| `WORKLOAD_ID` | TEXT | identifier / grouping key — not a feature |
| `ADM_DAY` | NUMBER | diagnostic — not a feature |
| `SPLIT` | TEXT | split label — not a feature |
| `GPU_REQUEST` | FLOAT | numeric feature (admission-time) |
| `VRAM_ENTITLED_GIB` | FLOAT | numeric feature (admission-time) |
| `CPU_REQUEST_CORES` | FLOAT | numeric feature (admission-time) |
| `SERVER_GPU_COUNT` | FLOAT | numeric feature (admission-time) |
| `SERVER_CPU_CAPACITY_CORES` | FLOAT | numeric feature (admission-time) |
| `GPU_MEM_PER_GPU` | FLOAT | numeric feature (admission-time) |
| `CPU_PER_GPU` | FLOAT | numeric feature (admission-time) |
| `ADM_HOUR` | NUMBER | numeric feature (admission-time) |
| `ADM_DOW_IDX` | NUMBER | numeric feature (admission-time) |
| `HOUR_SIN` | FLOAT | numeric feature (admission-time) |
| `HOUR_COS` | FLOAT | numeric feature (admission-time) |
| `DOW_SIN` | FLOAT | numeric feature (admission-time) |
| `DOW_COS` | FLOAT | numeric feature (admission-time) |
| `IS_WHOLE_GPU` | NUMBER | numeric feature (admission-time) |
| `IS_FRACTIONAL` | NUMBER | numeric feature (admission-time) |
| `IS_MULTI_GPU` | NUMBER | numeric feature (admission-time) |
| `HAS_WORKLOAD_ID` | NUMBER | numeric feature (admission-time) |
| `CLUSTER_PODS_AT_SUBMIT` | NUMBER | numeric feature (admission-time) |
| `CLUSTER_GPU_REQUESTED_AT_SUBMIT` | FLOAT | numeric feature (admission-time) |
| `CLUSTER_SM_MEAN_PREV_HR` | FLOAT | numeric feature (admission-time) |
| `CLUSTER_SM_P90_PREV_HR` | FLOAT | numeric feature (admission-time) |
| `SERVER_ALLOC_GPU_AT_SUBMIT` | FLOAT | numeric feature (admission-time) |
| `SERVER_GPU_OCCUPANCY_AT_SUBMIT` | FLOAT | numeric feature (admission-time) |
| `ASW_PODS_AT_SUBMIT` | NUMBER | numeric feature (admission-time) |
| `ASW_ALLOC_GPU_AT_SUBMIT` | FLOAT | numeric feature (admission-time) |
| `WL_HIST_POD_COUNT` | NUMBER | feature — workload history (prior days only) |
| `WL_HIST_DAYS_OBSERVED` | NUMBER | feature — workload history (prior days only) |
| `WL_HIST_MVF_P90` | FLOAT | feature — workload history (prior days only) |
| `WL_HIST_MVF_MAX` | FLOAT | feature — workload history (prior days only) |
| `WL_HIST_MVF_MEAN` | FLOAT | feature — workload history (prior days only) |
| `WL_HIST_SM_P90` | FLOAT | feature — workload history (prior days only) |
| `WL_HIST_DUR_MEAN` | NUMBER | feature — workload history (prior days only) |
| `GPU_SPEC_PUBLIC` | TEXT | categorical feature |
| `CLUSTER_ID` | TEXT | categorical feature |
| `PRIORITY_CLASS` | TEXT | categorical feature |
| `MODEL_TYPE_PUBLIC` | TEXT | categorical feature |
| `IS_GENAI_REQUEST` | BOOLEAN | categorical feature |
| `ASW_ID` | TEXT | categorical feature |
| `N_POD_HOURS` | NUMBER | diagnostic — not a feature |
| `N_HOURS_WITH_UTIL` | NUMBER | diagnostic — not a feature |
| `IS_CENSORED` | NUMBER | diagnostic — not a feature |
| `Y_READY` | BOOLEAN | **TARGET** |
| `SCHEDULE_DELAY_SEC` | NUMBER | diagnostic — not a feature |
| `READY_DELAY_SEC` | NUMBER | diagnostic — not a feature |
| `Y_READY_JES_CROSSCHECK` | BOOLEAN | alternative label (partial coverage) |
