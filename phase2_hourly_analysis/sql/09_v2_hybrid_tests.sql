-- Model A v2 (A1, A3v2, HYB) through the hourly replay, fallback (H11) and capacity replay (H12).
-- Same methods and the SAME decision rules as v1 (fixed 8 Nov 2026). v2 results are exploratory.
-- Needs PRED_A_V2 (uploaded from the v2 export cell) plus tables kept from the v1 runs:
-- REPLAY_PODS, REPLAY_NEED, SIM2_POD_HOURS, SIM2_BASE, SIM_PROBE, SERVER_HOURLY, POLICY_BASE (for the check in 0).
-- New tables all end in _V2, so the v1 results stay untouched. Unseen-cluster (loco) predictions only.
-- Model names: A1, A3v2, HYB = risk-budget ("alloc") margins; *_mond = 95%-coverage margins.

USE WAREHOUSE ASI_WH;
USE SCHEMA ASI_TRACE.RAW;
ALTER WAREHOUSE ASI_WH SET WAREHOUSE_SIZE = 'MEDIUM';

------------------------------------------------------------------
-- 0. Check the upload: expect 6 models, the same 43,359 unseen-cluster pods as v1
------------------------------------------------------------------
SELECT MODEL, COUNT(*) AS pods, AVG(IFF(SLICE_FRAC < Y_MVF - 1e-9, 1, 0)) AS U,
       SUM(RESERVED_GPU_HOURS * (1 - SLICE_FRAC)) / SUM(RESERVED_GPU_HOURS) AS R_pooled
FROM PRED_A_V2 WHERE SCENARIO = 'loco' GROUP BY 1 ORDER BY 1;

------------------------------------------------------------------
-- 1. HOURLY REPLAY
------------------------------------------------------------------
CREATE OR REPLACE TABLE REPLAY_RESULT_V2 AS
SELECT s.MODEL, COALESCE(s.HELDOUT_CLUSTER, s.CLUSTER_ID) AS EVAL_CLUSTER, s.POD_ID, n.t,
       s.SLICE_FRAC, s.GPU_REQUEST, n.sm_frac, n.mem_frac,
       IFF(n.sm_frac  > s.SLICE_FRAC + 1e-9, 1, 0) AS sm_over,
       IFF(n.mem_frac > s.SLICE_FRAC + 1e-9, 1, 0) AS mem_over,
       GREATEST(0, GREATEST_IGNORE_NULLS(n.sm_frac, n.mem_frac) - s.SLICE_FRAC) * s.GPU_REQUEST AS over_gpus
FROM PRED_A_V2 s
JOIN REPLAY_NEED n ON n.pod_id = s.POD_ID
WHERE s.SCENARIO = 'loco';

-- 1a. Per cluster (download as CSV: about 60 rows)
WITH pod AS (
  SELECT MODEL, EVAL_CLUSTER, POD_ID, COUNT(*) AS hours,
         SUM(GREATEST(sm_over, mem_over)) AS over_hours, SUM(mem_over) AS mem_over_hours
  FROM REPLAY_RESULT_V2 GROUP BY 1, 2, 3
)
SELECT MODEL, EVAL_CLUSTER, COUNT(*) AS pods, SUM(hours) AS pod_hours,
       SUM(over_hours) AS short_hours, SUM(mem_over_hours) AS mem_short_hours,
       COUNT_IF(over_hours > 0) AS pods_ever_short,
       COUNT_IF(over_hours > 0.1 * hours) AS pods_short_10pct_plus
FROM pod GROUP BY 1, 2 ORDER BY 1, 2;

-- 1b. Persistent shortfalls (download as CSV: 6 rows)
WITH v AS (
  SELECT MODEL, POD_ID, t FROM REPLAY_RESULT_V2 WHERE GREATEST(sm_over, mem_over) = 1
), g AS (
  SELECT *, t - ROW_NUMBER() OVER (PARTITION BY MODEL, POD_ID ORDER BY t) AS grp FROM v
), runs AS (
  SELECT MODEL, POD_ID, grp, COUNT(*) AS run_hours FROM g GROUP BY 1, 2, 3
), pod AS (
  SELECT MODEL, POD_ID, MAX(run_hours) AS longest, SUM(run_hours) AS short_hours FROM runs GROUP BY 1, 2
)
SELECT MODEL, COUNT(*) AS pods_ever_short,
       COUNT_IF(longest >= 24) AS pods_short_24h_in_a_row,
       COUNT_IF(longest >= 168) AS pods_short_a_week_in_a_row,
       SUM(IFF(longest >= 24, short_hours, 0)) / SUM(short_hours) AS share_of_short_hours_from_those_pods,
       MEDIAN(longest) AS median_longest_run, MAX(longest) AS longest_run
FROM pod GROUP BY 1 ORDER BY 1;

------------------------------------------------------------------
-- 2. FALLBACK (H11) - rule unchanged: choose k on pods admitted days 158-170 as the setting that
--    frees the most while cutting short pod-hours >= 50% and keeping >= 80% of freed GPU-hours;
--    report it once on pods admitted days 171-183. Models: A1, A3v2, HYB (alloc margins).
------------------------------------------------------------------
CREATE OR REPLACE TABLE POLICY_BASE_V2 AS
SELECT r.MODEL, r.EVAL_CLUSTER, r.POD_ID, r.t, r.SLICE_FRAC, r.GPU_REQUEST,
       GREATEST_IGNORE_NULLS(r.sm_frac, r.mem_frac) AS need, r.mem_frac,
       IFF(p.ADM_DAY <= 170, 'select', 'report') AS half
FROM REPLAY_RESULT_V2 r
JOIN REPLAY_PODS p ON p.POD_ID = r.POD_ID
WHERE r.MODEL IN ('A1', 'A3v2', 'HYB');

CREATE OR REPLACE TABLE POLICY_SWITCH_V2 AS
WITH v AS (
  SELECT MODEL, POD_ID, t FROM POLICY_BASE_V2 WHERE need > SLICE_FRAC + 1e-9
), g AS (
  SELECT *, t - ROW_NUMBER() OVER (PARTITION BY MODEL, POD_ID ORDER BY t) AS grp FROM v
), p AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY MODEL, POD_ID, grp ORDER BY t) AS pos FROM g
)
SELECT MODEL, POD_ID, pos AS k, MIN(t) AS switch_t
FROM p WHERE pos IN (1, 3, 6, 12, 24) GROUP BY 1, 2, 3;

CREATE OR REPLACE TABLE POLICY_RESULT_V2 AS
WITH pol AS (
  SELECT 0 AS k UNION ALL SELECT column1 FROM VALUES (1), (3), (6), (12), (24)
), x AS (
  SELECT pol.k, b.MODEL, b.EVAL_CLUSTER, b.half, b.GPU_REQUEST, b.need, b.mem_frac,
         IFF(pol.k > 0 AND s.switch_t IS NOT NULL AND b.t > s.switch_t, 1.0, b.SLICE_FRAC) AS slice_used
  FROM POLICY_BASE_V2 b CROSS JOIN pol
  LEFT JOIN POLICY_SWITCH_V2 s ON s.MODEL = b.MODEL AND s.POD_ID = b.POD_ID AND s.k = pol.k
)
SELECT k, MODEL, EVAL_CLUSTER, half,
       COUNT(*)                                      AS pod_hours,
       SUM(IFF(need     > slice_used + 1e-9, 1, 0))  AS short_hours,
       SUM(IFF(mem_frac > slice_used + 1e-9, 1, 0))  AS mem_short_hours,
       SUM((1 - slice_used) * GPU_REQUEST)           AS freed_gpu_hours,
       SUM(GPU_REQUEST)                              AS reserved_gpu_hours
FROM x GROUP BY 1, 2, 3, 4;

-- 2a. Download as CSV (about 360 rows)
SELECT * FROM POLICY_RESULT_V2 ORDER BY k, MODEL, half, EVAL_CLUSTER;

------------------------------------------------------------------
-- 3. CAPACITY REPLAY (H12) - rule unchanged: supported if, under ideal sharing, >= 50% of freed
--    GPU-hours become usable whole-GPU capacity with enough CPU. Time-weighted, as in v1's second run.
--    All k are computed; the k chosen in step 2 is the one reported.
------------------------------------------------------------------
CREATE OR REPLACE TABLE SIM_SLICES_V2 AS
SELECT b.MODEL || '_k' || pol.k AS policy, b.POD_ID, b.t,
       IFF(pol.k > 0 AND s.switch_t IS NOT NULL AND b.t > s.switch_t, 1.0, b.SLICE_FRAC) AS slice
FROM POLICY_BASE_V2 b
CROSS JOIN (SELECT 0 AS k UNION ALL SELECT column1 FROM VALUES (1), (3), (6), (12), (24)) pol
LEFT JOIN POLICY_SWITCH_V2 s ON s.MODEL = b.MODEL AND s.POD_ID = b.POD_ID AND s.k = pol.k;

CREATE OR REPLACE TABLE SIM_DELTA_V2 AS
SELECT sl.policy, p.server_id, p.t,
       SUM(p.w * (sl.slice * p.req - p.req))                               AS d_ideal,
       SUM(p.w * (CEIL(sl.slice * p.req - 1e-9) - CEIL(p.req - 1e-9)))     AS d_noshare,
       SUM(p.w * (1 - sl.slice) * p.req)                                   AS freed_gpu
FROM SIM_SLICES_V2 sl
JOIN SIM2_POD_HOURS p ON p.pod_id = sl.POD_ID AND p.t = sl.t
GROUP BY 1, 2, 3;

CREATE OR REPLACE TABLE SIM_RESULT_V2 AS
WITH srv AS (
  SELECT s.CLUSTER_ID AS cluster_id, s.SERVER_ID AS server_id, s.DAY_ * 24 + s.HOUR_ AS t,
         s.GPU_COUNT AS cap,
         COALESCE(b.alloc_ideal, 0) AS alloc_ideal, COALESCE(b.alloc_noshare, 0) AS alloc_noshare,
         FLOOR(GREATEST(0, s.CPU_CAPACITY_CORES - COALESCE(b.cpu_used, 0)) / NULLIF(pr.cpu_per_gpu, 0)) AS cpu_slots
  FROM SERVER_HOURLY s
  LEFT JOIN SIM2_BASE b ON b.server_id = s.SERVER_ID AND b.t = s.DAY_ * 24 + s.HOUR_
  JOIN SIM_PROBE pr ON pr.CLUSTER_ID = s.CLUSTER_ID
  WHERE s.CLUSTER_ID IN (SELECT DISTINCT EVAL_CLUSTER FROM POLICY_BASE_V2)
), x AS (
  SELECT d.policy, srv.*, d.d_ideal, d.d_noshare, d.freed_gpu
  FROM SIM_DELTA_V2 d
  JOIN srv ON srv.server_id = d.server_id AND srv.t = d.t
)
SELECT policy, cluster_id,
       SUM(freed_gpu)                                                                    AS gpu_hours_freed,
       SUM(GREATEST(0, FLOOR(cap - alloc_ideal - d_ideal + 1e-6))
         - GREATEST(0, FLOOR(cap - alloc_ideal + 1e-6)))                                 AS whole_gain_ideal,
       SUM(GREATEST(0, LEAST(FLOOR(cap - alloc_ideal - d_ideal + 1e-6), cpu_slots))
         - GREATEST(0, LEAST(FLOOR(cap - alloc_ideal + 1e-6), cpu_slots)))               AS usable_gain_ideal,
       SUM(GREATEST(0, LEAST(FLOOR(cap - alloc_noshare - d_noshare + 1e-6), cpu_slots))
         - GREATEST(0, LEAST(FLOOR(cap - alloc_noshare + 1e-6), cpu_slots)))             AS usable_gain_noshare
FROM x
GROUP BY 1, 2;

-- 3a. Download as CSV (about 180 rows)
SELECT * FROM SIM_RESULT_V2 ORDER BY policy, cluster_id;

ALTER WAREHOUSE ASI_WH SET WAREHOUSE_SIZE = 'XSMALL';
