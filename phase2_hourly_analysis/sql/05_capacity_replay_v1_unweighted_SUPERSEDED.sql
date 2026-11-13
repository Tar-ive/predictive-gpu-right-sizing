-- Capacity replay (H12): does GPU freed by right-sizing become usable whole-GPU capacity?
-- Run in Snowflake after fallback_v1.sql. Uses POD_HOURLY, SERVER_HOURLY, MODEL_A,
-- POLICY_BASE and POLICY_SWITCH.
--
-- Each hour, pods stay on the servers they actually ran on. Test pods with unseen-cluster
-- predictions are shrunk; every other pod keeps its request. For each server-hour we count
-- the whole GPUs a new 1-GPU job could use, with enough free CPU for it.
--   ideal sharing : fractional slices pack tightly onto shared GPUs  (upper bound)
--   no sharing    : every fractional slice still holds a whole GPU   (lower bound)
--
-- H12 rule (set 8 Nov 2026, before running): supported if, under ideal sharing, at least
-- 50% of the freed GPU-hours become usable whole-GPU capacity. No-sharing is reported beside it.

USE WAREHOUSE ASI_WH;
USE SCHEMA ASI_TRACE.RAW;
ALTER WAREHOUSE ASI_WH SET WAREHOUSE_SIZE = 'MEDIUM';

------------------------------------------------------------------
-- 0. Check the server table (expect 648 hours, days 158-184, no missing)
------------------------------------------------------------------
SELECT COUNT(*) AS rows_loaded, COUNT_IF(DAY_ IS NULL) AS missing_day,
       MIN(DAY_) AS first_day, MAX(DAY_) AS last_day,
       COUNT(DISTINCT DAY_ * 24 + HOUR_) AS hours,
       COUNT(DISTINCT SERVER_ID) AS servers, COUNT(DISTINCT CLUSTER_ID) AS clusters
FROM SERVER_HOURLY;

------------------------------------------------------------------
-- 1. Slices per pod-hour for each policy
------------------------------------------------------------------
CREATE OR REPLACE TABLE SIM_SLICES AS
SELECT 'A1_fallback6' AS policy, b.POD_ID, b.t,
       IFF(s.switch_t IS NOT NULL AND b.t > s.switch_t, 1.0, b.SLICE_FRAC) AS slice
FROM POLICY_BASE b
LEFT JOIN POLICY_SWITCH s ON s.MODEL = b.MODEL AND s.POD_ID = b.POD_ID AND s.k = 6
WHERE b.MODEL = 'A1'
UNION ALL
SELECT 'A3_fallback24', b.POD_ID, b.t,
       IFF(s.switch_t IS NOT NULL AND b.t > s.switch_t, 1.0, b.SLICE_FRAC)
FROM POLICY_BASE b
LEFT JOIN POLICY_SWITCH s ON s.MODEL = b.MODEL AND s.POD_ID = b.POD_ID AND s.k = 24
WHERE b.MODEL = 'A3'
UNION ALL
SELECT 'A1_no_fallback', b.POD_ID, b.t, b.SLICE_FRAC
FROM POLICY_BASE b
WHERE b.MODEL = 'A1';

------------------------------------------------------------------
-- 2. Every pod-hour on a GPU server in the 10 unseen clusters
------------------------------------------------------------------
CREATE OR REPLACE TABLE SIM_POD_HOURS AS
SELECT h.cluster_id, h.server_id, h.day * 24 + h.hour AS t, h.pod_id,
       COALESCE(h.gpu_request, 0)       AS req,
       COALESCE(h.cpu_request_cores, 0) AS cpu
FROM POD_HOURLY h
JOIN SERVER_HOURLY s
  ON s.SERVER_ID = h.server_id AND s.DAY_ = h.day AND s.HOUR_ = h.hour
WHERE h.cluster_id IN (SELECT DISTINCT EVAL_CLUSTER FROM POLICY_BASE);

------------------------------------------------------------------
-- 3. Baseline use per server-hour (whole GPUs held, fractional parts, CPU)
------------------------------------------------------------------
CREATE OR REPLACE TABLE SIM_BASE AS
SELECT cluster_id, server_id, t,
       SUM(FLOOR(req + 1e-9))                           AS whole_used,
       SUM(GREATEST(0, req - FLOOR(req + 1e-9)))        AS frac_sum,
       COUNT_IF(req - FLOOR(req + 1e-9) > 1e-9)         AS n_frac,
       SUM(req)                                         AS alloc_gpu,
       SUM(cpu)                                         AS cpu_used
FROM SIM_POD_HOURS
GROUP BY 1, 2, 3;

------------------------------------------------------------------
-- 4. Change per server-hour when the test pods are shrunk
------------------------------------------------------------------
CREATE OR REPLACE TABLE SIM_DELTA AS
SELECT sl.policy, p.cluster_id, p.server_id, p.t,
       SUM(FLOOR(sl.slice * p.req + 1e-9) - FLOOR(p.req + 1e-9))                         AS d_whole,
       SUM(GREATEST(0, sl.slice * p.req - FLOOR(sl.slice * p.req + 1e-9))
         - GREATEST(0, p.req - FLOOR(p.req + 1e-9)))                                     AS d_frac_sum,
       SUM(IFF(sl.slice * p.req - FLOOR(sl.slice * p.req + 1e-9) > 1e-9, 1, 0)
         - IFF(p.req - FLOOR(p.req + 1e-9) > 1e-9, 1, 0))                                AS d_n_frac,
       SUM((1 - sl.slice) * p.req)                                                       AS freed_gpu
FROM SIM_SLICES sl
JOIN SIM_POD_HOURS p ON p.pod_id = sl.POD_ID AND p.t = sl.t
GROUP BY 1, 2, 3, 4;

------------------------------------------------------------------
-- 5. Usable whole GPUs per server-hour, before and after
------------------------------------------------------------------
CREATE OR REPLACE TABLE SIM_PROBE AS            -- CPU a new 1-GPU job needs: cluster median from D1
SELECT CLUSTER_ID, MEDIAN(CPU_REQUEST_CORES / NULLIF(GPU_REQUEST, 0)) AS cpu_per_gpu
FROM MODEL_A GROUP BY 1;

CREATE OR REPLACE TABLE SIM_RESULT AS
WITH pol AS (
  SELECT column1 AS policy FROM VALUES ('A1_fallback6'), ('A3_fallback24'), ('A1_no_fallback')
), srv AS (
  SELECT s.CLUSTER_ID AS cluster_id, s.SERVER_ID AS server_id, s.DAY_ * 24 + s.HOUR_ AS t,
         s.GPU_COUNT AS cap, s.CPU_CAPACITY_CORES AS cpu_cap,
         COALESCE(b.whole_used, 0) AS whole_used, COALESCE(b.frac_sum, 0) AS frac_sum,
         COALESCE(b.n_frac, 0) AS n_frac, COALESCE(b.alloc_gpu, 0) AS alloc_gpu,
         COALESCE(b.cpu_used, 0) AS cpu_used, pr.cpu_per_gpu
  FROM SERVER_HOURLY s
  LEFT JOIN SIM_BASE b ON b.server_id = s.SERVER_ID AND b.t = s.DAY_ * 24 + s.HOUR_
  JOIN SIM_PROBE pr ON pr.CLUSTER_ID = s.CLUSTER_ID
  WHERE s.CLUSTER_ID IN (SELECT DISTINCT EVAL_CLUSTER FROM POLICY_BASE)
), x AS (
  SELECT pol.policy, srv.*,
         COALESCE(d.d_whole, 0) AS d_whole, COALESCE(d.d_frac_sum, 0) AS d_frac_sum,
         COALESCE(d.d_n_frac, 0) AS d_n_frac, COALESCE(d.freed_gpu, 0) AS freed_gpu,
         FLOOR(GREATEST(0, srv.cpu_cap - srv.cpu_used) / NULLIF(srv.cpu_per_gpu, 0)) AS cpu_slots
  FROM srv CROSS JOIN pol
  LEFT JOIN SIM_DELTA d ON d.policy = pol.policy AND d.server_id = srv.server_id AND d.t = srv.t
)
SELECT policy, cluster_id,
       COUNT(*)                                                         AS server_hours,
       SUM(cap)                                                         AS gpu_hours_capacity,
       SUM(alloc_gpu)                                                   AS gpu_hours_allocated,
       COUNT_IF(alloc_gpu > cap + 1e-9)                                 AS server_hours_overallocated,
       SUM(freed_gpu)                                                   AS gpu_hours_freed,
       -- ideal sharing
       SUM(GREATEST(0, cap - whole_used - CEIL(frac_sum - 1e-9)))                                   AS free_whole_base_ideal,
       SUM(GREATEST(0, cap - whole_used - d_whole - CEIL(frac_sum + d_frac_sum - 1e-9)))            AS free_whole_new_ideal,
       SUM(GREATEST(0, LEAST(cap - whole_used - CEIL(frac_sum - 1e-9), cpu_slots)))                 AS usable_base_ideal,
       SUM(GREATEST(0, LEAST(cap - whole_used - d_whole - CEIL(frac_sum + d_frac_sum - 1e-9), cpu_slots))) AS usable_new_ideal,
       -- no sharing
       SUM(GREATEST(0, LEAST(cap - whole_used - n_frac, cpu_slots)))                                AS usable_base_noshare,
       SUM(GREATEST(0, LEAST(cap - whole_used - d_whole - n_frac - d_n_frac, cpu_slots)))           AS usable_new_noshare
FROM x
GROUP BY 1, 2;

------------------------------------------------------------------
-- 6. Download as CSV and send (30 rows: 3 policies x 10 clusters)
------------------------------------------------------------------
SELECT * FROM SIM_RESULT ORDER BY policy, cluster_id;

ALTER WAREHOUSE ASI_WH SET WAREHOUSE_SIZE = 'XSMALL';
