-- Fallback and early-resize policies on top of Model A v1 (unseen-cluster predictions).
-- Run in Snowflake, after replay_v1.sql. Uses REPLAY_RESULT and REPLAY_PODS.
--
-- Policies (each applied to A1, A2 and A3):
--   none           slice as predicted (the replay result)
--   fallback k     after k consecutive short hours, the pod gets its full request for the rest of its life (H11)
--   early_raise h  after the pod's first h hours, slice = max(predicted slice, peak need seen so far)   (H8)
--   early_resize h after the pod's first h hours, slice = peak need seen so far, up or down          (H8)
--
-- Selection rule (set 8 Nov 2026, before running):
--   pods admitted days 158-170 = "select" half, days 171-183 = "report" half.
--   For each model, on the select half, keep the settings that cut short pod-hours by >= 50%
--   and keep >= 80% of the freed GPU-hours, both versus "none"; of those, pick the one freeing the most.
--   Report that one setting on the report half. H8 results are exploratory.

USE WAREHOUSE ASI_WH;
USE SCHEMA ASI_TRACE.RAW;
ALTER WAREHOUSE ASI_WH SET WAREHOUSE_SIZE = 'MEDIUM';   -- step 4 is large; set back at the end

------------------------------------------------------------------
-- 1. One row per pod-hour, unseen-cluster scenario, models A1-A3
------------------------------------------------------------------
CREATE OR REPLACE TABLE POLICY_BASE AS
SELECT r.MODEL, r.EVAL_CLUSTER, r.POD_ID, r.t, r.SLICE_FRAC, r.GPU_REQUEST,
       GREATEST_IGNORE_NULLS(r.sm_frac, r.mem_frac)          AS need,
       r.mem_frac,
       IFF(p.ADM_DAY <= 170, 'select', 'report')              AS half,
       r.t - MIN(r.t) OVER (PARTITION BY r.MODEL, r.POD_ID)   AS age_h
FROM REPLAY_RESULT r
JOIN REPLAY_PODS p ON p.POD_ID = r.POD_ID
WHERE r.SCENARIO = 'loco' AND r.MODEL IN ('A1', 'A2', 'A3');

-- check: rows should be 3 x 8,999,272 = 26,997,816
SELECT MODEL, half, COUNT(*) AS pod_hours, COUNT(DISTINCT POD_ID) AS pods
FROM POLICY_BASE GROUP BY 1, 2 ORDER BY 1, 2;

------------------------------------------------------------------
-- 2. Fallback switch: the hour a pod reaches k short hours in a row
------------------------------------------------------------------
CREATE OR REPLACE TABLE POLICY_SWITCH AS
WITH v AS (
  SELECT MODEL, POD_ID, t FROM POLICY_BASE WHERE need > SLICE_FRAC + 1e-9
), g AS (
  SELECT *, t - ROW_NUMBER() OVER (PARTITION BY MODEL, POD_ID ORDER BY t) AS grp FROM v
), p AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY MODEL, POD_ID, grp ORDER BY t) AS pos FROM g
)
SELECT MODEL, POD_ID, pos AS k, MIN(t) AS switch_t
FROM p WHERE pos IN (1, 3, 6, 12, 24)
GROUP BY 1, 2, 3;

------------------------------------------------------------------
-- 3. Early peak: highest hourly need in each pod's first h hours
------------------------------------------------------------------
CREATE OR REPLACE TABLE POLICY_EARLY AS
SELECT b.MODEL, b.POD_ID, h.h, MAX(b.need) AS early_peak
FROM POLICY_BASE b
JOIN (SELECT column1 AS h FROM VALUES (6), (24)) h ON b.age_h < h.h
GROUP BY 1, 2, 3;

------------------------------------------------------------------
-- 4. Apply every policy and total per model x cluster x half
------------------------------------------------------------------
CREATE OR REPLACE TABLE POLICY_RESULT AS
WITH pol AS (
  SELECT 'none' AS policy, 0 AS param
  UNION ALL SELECT 'fallback',     column1 FROM VALUES (1), (3), (6), (12), (24)
  UNION ALL SELECT 'early_raise',  column1 FROM VALUES (6), (24)
  UNION ALL SELECT 'early_resize', column1 FROM VALUES (6), (24)
), x AS (
  SELECT pol.policy, pol.param, b.MODEL, b.EVAL_CLUSTER, b.half, b.POD_ID, b.GPU_REQUEST, b.need, b.mem_frac,
         CASE
           WHEN pol.policy = 'fallback' AND s.switch_t IS NOT NULL AND b.t > s.switch_t
             THEN 1.0
           WHEN pol.policy = 'early_raise' AND b.age_h >= pol.param AND e.early_peak IS NOT NULL
             THEN GREATEST(b.SLICE_FRAC, LEAST(1, e.early_peak))
           WHEN pol.policy = 'early_resize' AND b.age_h >= pol.param AND e.early_peak IS NOT NULL
             THEN GREATEST(0.01, LEAST(1, e.early_peak))       -- 0.01 = smallest real slice size
           ELSE b.SLICE_FRAC
         END AS slice_used
  FROM POLICY_BASE b
  CROSS JOIN pol
  LEFT JOIN POLICY_SWITCH s
         ON pol.policy = 'fallback' AND s.MODEL = b.MODEL AND s.POD_ID = b.POD_ID AND s.k = pol.param
  LEFT JOIN POLICY_EARLY e
         ON pol.policy IN ('early_raise', 'early_resize') AND e.MODEL = b.MODEL AND e.POD_ID = b.POD_ID AND e.h = pol.param
)
SELECT policy, param, MODEL, EVAL_CLUSTER, half,
       COUNT(*)                                        AS pod_hours,
       COUNT(DISTINCT POD_ID)                          AS pods,
       SUM(IFF(need     > slice_used + 1e-9, 1, 0))    AS short_hours,
       SUM(IFF(mem_frac > slice_used + 1e-9, 1, 0))    AS mem_short_hours,
       SUM((1 - slice_used) * GPU_REQUEST)             AS freed_gpu_hours,
       SUM(GPU_REQUEST)                                AS reserved_gpu_hours
FROM x
GROUP BY 1, 2, 3, 4, 5;

------------------------------------------------------------------
-- 5. Download this result as a CSV and send it (about 600 rows)
------------------------------------------------------------------
SELECT * FROM POLICY_RESULT ORDER BY policy, param, MODEL, half, EVAL_CLUSTER;

ALTER WAREHOUSE ASI_WH SET WAREHOUSE_SIZE = 'XSMALL';
