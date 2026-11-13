-- Hour-by-hour replay of Model A v1 (A1, A2, A3) on test days 158-183.
-- Run in a Snowflake worksheet, one step at a time, top to bottom.
-- Needs: POD_HOURLY (raw trace), MODEL_A (D1), PRED_A_V1 (exported predictions).
--
-- Question: was the slice each model would have given a pod big enough in each hour it ran?
-- Y_MVF is a 90th percentile, so a slice equal to Y_MVF is exceeded in up to ~10% of hours by
-- design. ORACLE_Y_MVF (slice = Y_MVF) is that reference; FULL_REQUEST (slice = 1.0) is today's state.

USE WAREHOUSE ASI_WH;
USE SCHEMA ASI_TRACE.RAW;
ALTER WAREHOUSE ASI_WH SET WAREHOUSE_SIZE = 'SMALL';   -- set back to XSMALL at the end

------------------------------------------------------------------
-- Step 1. Test pods from D1                       (expect 45,669)
------------------------------------------------------------------
CREATE OR REPLACE TABLE REPLAY_PODS AS
SELECT POD_ID, CLUSTER_ID, ADM_DAY, ADM_HOUR, MODEL_TYPE_PUBLIC,
       GPU_REQUEST, VRAM_ENTITLED_GIB, N_POD_HOURS, N_HOURS_WITH_UTIL, IS_CENSORED, Y_MVF
FROM MODEL_A
WHERE ADM_DAY BETWEEN 158 AND 183;

SELECT COUNT(*) AS test_pods, COUNT(DISTINCT POD_ID) AS distinct_pods FROM REPLAY_PODS;

------------------------------------------------------------------
-- Step 2. Their hourly rows from the raw trace (one scan of POD_HOURLY)
------------------------------------------------------------------
CREATE OR REPLACE TABLE REPLAY_HOURS AS
SELECT h.pod_id, h.day, h.hour, h.day * 24 + h.hour AS t,
       h.avg_gpu_sm_util, h.avg_gpu_mem_gib, h.used_gpu_hours, h.state_public
FROM POD_HOURLY h
JOIN REPLAY_PODS p ON h.pod_id = p.POD_ID;

-- One hourly need per pod-hour, on the same basis as Y_MVF (fractions of the request)
CREATE OR REPLACE TABLE REPLAY_NEED AS
SELECT r.pod_id, r.t,
       AVG(r.avg_gpu_sm_util) / p.GPU_REQUEST / 100        AS sm_frac,
       AVG(r.avg_gpu_mem_gib) / NULLIF(p.VRAM_ENTITLED_GIB, 0) AS mem_frac,
       COUNT(*)                                           AS rows_in_hour
FROM REPLAY_HOURS r
JOIN REPLAY_PODS p ON r.pod_id = p.POD_ID
GROUP BY r.pod_id, r.t, p.GPU_REQUEST, p.VRAM_ENTITLED_GIB;

------------------------------------------------------------------
-- Step 3. CHECKS - stop here and send the results before Step 4
------------------------------------------------------------------
-- 3a. Did we find every pod and every hour?
--     share_cut_at_183 > 0 means some pods ran into day 184, which is not loaded yet.
WITH c AS (
  SELECT pod_id, COUNT(*) AS n_found, MAX(t) AS last_t, MAX(rows_in_hour) AS max_rows_in_hour
  FROM REPLAY_NEED GROUP BY pod_id
)
SELECT COUNT(*)                                                         AS test_pods,
       COUNT_IF(c.pod_id IS NULL)                                        AS pods_not_found,
       COUNT_IF(c.n_found = p.N_POD_HOURS) / COUNT(*)                    AS share_hours_exact,
       COUNT_IF(c.n_found < p.N_POD_HOURS) / COUNT(*)                    AS share_hours_missing,
       COUNT_IF(c.n_found > p.N_POD_HOURS) / COUNT(*)                    AS share_hours_extra,
       COUNT_IF(c.n_found < p.N_POD_HOURS AND c.last_t >= 183 * 24 + 23) / COUNT(*) AS share_cut_at_183,
       COUNT_IF(c.max_rows_in_hour > 1) / COUNT(*)                       AS share_pods_with_duplicate_hours
FROM REPLAY_PODS p
LEFT JOIN c ON c.pod_id = p.POD_ID;

-- 3b. Does the hourly need rebuild Y_MVF? (correlation near 1 and most pods within 0.01)
WITH pod AS (
  SELECT pod_id,
         PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY sm_frac)  AS sm_cont,
         PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY mem_frac) AS mem_cont,
         PERCENTILE_DISC(0.9) WITHIN GROUP (ORDER BY sm_frac)  AS sm_disc,
         PERCENTILE_DISC(0.9) WITHIN GROUP (ORDER BY mem_frac) AS mem_disc
  FROM REPLAY_NEED GROUP BY pod_id
), y AS (
  SELECT p.Y_MVF,
         LEAST(1, GREATEST_IGNORE_NULLS(sm_cont, mem_cont)) AS y_cont,
         LEAST(1, GREATEST_IGNORE_NULLS(sm_disc, mem_disc)) AS y_disc
  FROM pod JOIN REPLAY_PODS p ON p.POD_ID = pod.pod_id
)
SELECT COUNT(*)                                             AS pods,
       CORR(Y_MVF, y_cont)                                  AS corr_cont,
       AVG(ABS(Y_MVF - y_cont))                             AS mean_abs_diff_cont,
       COUNT_IF(ABS(Y_MVF - y_cont) <= 0.01) / COUNT(*)     AS share_within_001_cont,
       CORR(Y_MVF, y_disc)                                  AS corr_disc,
       AVG(ABS(Y_MVF - y_disc))                             AS mean_abs_diff_disc,
       COUNT_IF(ABS(Y_MVF - y_disc) <= 0.01) / COUNT(*)     AS share_within_001_disc
FROM y;

------------------------------------------------------------------
-- Step 4. The replay (run only after the Step 3 checks look right)
------------------------------------------------------------------
-- 4a. Slices to test: the three models plus the two reference slices
CREATE OR REPLACE TABLE REPLAY_SLICES AS
SELECT SCENARIO, MODEL, COALESCE(HELDOUT_CLUSTER, CLUSTER_ID) AS EVAL_CLUSTER,
       POD_ID, SLICE_FRAC, GPU_REQUEST
FROM PRED_A_V1
UNION ALL
SELECT SCENARIO, 'ORACLE_Y_MVF', COALESCE(HELDOUT_CLUSTER, CLUSTER_ID), POD_ID, LEAST(Y_MVF, 1), GPU_REQUEST
FROM PRED_A_V1 WHERE MODEL = 'A1'
UNION ALL
SELECT SCENARIO, 'FULL_REQUEST', COALESCE(HELDOUT_CLUSTER, CLUSTER_ID), POD_ID, 1.0, GPU_REQUEST
FROM PRED_A_V1 WHERE MODEL = 'A1';

-- 4b. Every pod-hour against its slice
CREATE OR REPLACE TABLE REPLAY_RESULT AS
SELECT s.SCENARIO, s.MODEL, s.EVAL_CLUSTER, s.POD_ID, n.t,
       s.SLICE_FRAC, s.GPU_REQUEST, n.sm_frac, n.mem_frac,
       IFF(n.sm_frac  > s.SLICE_FRAC + 1e-9, 1, 0) AS sm_over,
       IFF(n.mem_frac > s.SLICE_FRAC + 1e-9, 1, 0) AS mem_over,
       GREATEST(0, GREATEST_IGNORE_NULLS(n.sm_frac, n.mem_frac) - s.SLICE_FRAC) * s.GPU_REQUEST AS over_gpus
FROM REPLAY_SLICES s
JOIN REPLAY_NEED n ON n.pod_id = s.POD_ID;

-- 4c. Main result, all pods pooled
WITH pod AS (
  SELECT SCENARIO, MODEL, EVAL_CLUSTER, POD_ID,
         COUNT(*) AS hours,
         SUM(GREATEST(sm_over, mem_over)) AS over_hours,
         SUM(mem_over) AS mem_over_hours,
         SUM(sm_over)  AS sm_over_hours
  FROM REPLAY_RESULT GROUP BY 1, 2, 3, 4
)
SELECT SCENARIO, MODEL,
       COUNT(*)                                        AS pods,
       SUM(hours)                                      AS pod_hours,
       SUM(over_hours)     / SUM(hours)                AS share_hours_over,
       SUM(mem_over_hours) / SUM(hours)                AS share_hours_mem_over,
       SUM(sm_over_hours)  / SUM(hours)                AS share_hours_sm_over,
       COUNT_IF(over_hours > 0) / COUNT(*)             AS share_pods_ever_over,
       COUNT_IF(over_hours > 0.1 * hours) / COUNT(*)   AS share_pods_over_in_10pct_plus_hours
FROM pod GROUP BY 1, 2 ORDER BY 1, 2;

-- 4d. Unseen clusters: mean and WORST cluster (the safety claim is per cluster)
WITH pod AS (
  SELECT MODEL, EVAL_CLUSTER, POD_ID, COUNT(*) AS hours,
         SUM(GREATEST(sm_over, mem_over)) AS over_hours, SUM(mem_over) AS mem_over_hours
  FROM REPLAY_RESULT WHERE SCENARIO = 'loco' GROUP BY 1, 2, 3
), cl AS (
  SELECT MODEL, EVAL_CLUSTER,
         SUM(over_hours) / SUM(hours)     AS hours_over,
         SUM(mem_over_hours) / SUM(hours) AS hours_mem_over,
         COUNT_IF(over_hours > 0) / COUNT(*) AS pods_ever_over
  FROM pod GROUP BY 1, 2
)
SELECT MODEL,
       AVG(hours_over)     AS mean_hours_over,     MAX(hours_over)     AS worst_hours_over,
       AVG(hours_mem_over) AS mean_hours_mem_over, MAX(hours_mem_over) AS worst_hours_mem_over,
       AVG(pods_ever_over) AS mean_pods_ever_over
FROM cl GROUP BY 1 ORDER BY 1;

-- 4e. Per-cluster detail for the unseen clusters (download as CSV)
WITH pod AS (
  SELECT MODEL, EVAL_CLUSTER, POD_ID, COUNT(*) AS hours,
         SUM(GREATEST(sm_over, mem_over)) AS over_hours, SUM(mem_over) AS mem_over_hours
  FROM REPLAY_RESULT WHERE SCENARIO = 'loco' GROUP BY 1, 2, 3
)
SELECT EVAL_CLUSTER, MODEL, COUNT(*) AS pods,
       SUM(over_hours) / SUM(hours)     AS hours_over,
       SUM(mem_over_hours) / SUM(hours) AS hours_mem_over
FROM pod GROUP BY 1, 2 ORDER BY 1, 2;

-- 4f. How long and how large the shortfalls are
WITH v AS (
  SELECT SCENARIO, MODEL, POD_ID, t, over_gpus, mem_over
  FROM REPLAY_RESULT WHERE GREATEST(sm_over, mem_over) = 1
), g AS (
  SELECT *, t - ROW_NUMBER() OVER (PARTITION BY SCENARIO, MODEL, POD_ID ORDER BY t) AS grp FROM v
), runs AS (
  SELECT SCENARIO, MODEL, POD_ID, grp, COUNT(*) AS run_hours FROM g GROUP BY 1, 2, 3, 4
)
SELECT r.SCENARIO, r.MODEL,
       COUNT(*)                            AS shortfall_runs,
       APPROX_PERCENTILE(run_hours, 0.5)   AS median_run_hours,
       APPROX_PERCENTILE(run_hours, 0.95)  AS p95_run_hours,
       MAX(run_hours)                      AS longest_run_hours,
       ANY_VALUE(s.median_over_gpus)       AS median_shortfall_gpus,
       ANY_VALUE(s.p95_over_gpus)          AS p95_shortfall_gpus
FROM runs r
JOIN (SELECT SCENARIO, MODEL,
             APPROX_PERCENTILE(over_gpus, 0.5)  AS median_over_gpus,
             APPROX_PERCENTILE(over_gpus, 0.95) AS p95_over_gpus
      FROM v GROUP BY 1, 2) s
  ON s.SCENARIO = r.SCENARIO AND s.MODEL = r.MODEL
GROUP BY 1, 2 ORDER BY 1, 2;

ALTER WAREHOUSE ASI_WH SET WAREHOUSE_SIZE = 'XSMALL';

-- 4g. Persistent shortfalls: pods short for 24 h or a week in a row (run after 4b)
WITH v AS (
  SELECT MODEL, POD_ID, t FROM REPLAY_RESULT
  WHERE SCENARIO = 'loco' AND GREATEST(sm_over, mem_over) = 1
), g AS (
  SELECT *, t - ROW_NUMBER() OVER (PARTITION BY MODEL, POD_ID ORDER BY t) AS grp FROM v
), runs AS (
  SELECT MODEL, POD_ID, grp, COUNT(*) AS run_hours FROM g GROUP BY 1, 2, 3
), pod AS (
  SELECT MODEL, POD_ID, MAX(run_hours) AS longest, SUM(run_hours) AS short_hours FROM runs GROUP BY 1, 2
)
SELECT MODEL,
       COUNT(*)                     AS pods_ever_short,
       COUNT_IF(longest >= 24)      AS pods_short_24h_in_a_row,
       COUNT_IF(longest >= 168)     AS pods_short_a_week_in_a_row,
       SUM(IFF(longest >= 24, short_hours, 0)) / SUM(short_hours) AS share_of_short_hours_from_those_pods
FROM pod GROUP BY 1 ORDER BY 1;
