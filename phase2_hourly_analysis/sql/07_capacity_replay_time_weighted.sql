-- Capacity replay v2 (H12): every pod-hour is weighted by the share of the hour the pod was present.
-- Why: the hourly table lists a pod for a whole hour even if it ran for 20 seconds, so short-lived
-- batch pods made servers look up to 24x over-allocated. used_gpu_hours = request x share of hour present.
--
-- Rule unchanged (set 8 Nov 2026): H12 supported if, under ideal sharing, at least 50% of the freed
-- GPU-hours become usable whole-GPU capacity with enough CPU. No-sharing is reported beside it.
-- Reuses SIM_SLICES and SIM_PROBE from v1. Run in Snowflake, top to bottom.

USE WAREHOUSE ASI_WH;
USE SCHEMA ASI_TRACE.RAW;
ALTER WAREHOUSE ASI_WH SET WAREHOUSE_SIZE = 'MEDIUM';

------------------------------------------------------------------
-- 1. Pod-hours with presence weight w (0-1). Pods with no GPU have no weight; their CPU counts in full.
------------------------------------------------------------------
CREATE OR REPLACE TABLE SIM2_POD_HOURS AS
SELECT h.cluster_id, h.server_id, h.day * 24 + h.hour AS t, h.pod_id,
       COALESCE(h.gpu_request, 0) AS req,
       COALESCE(h.cpu_request_cores, 0) AS cpu,
       IFF(COALESCE(h.gpu_request, 0) > 0,
           LEAST(1, GREATEST(0, COALESCE(h.used_gpu_hours, 0) / h.gpu_request)), 1) AS w
FROM POD_HOURLY h
JOIN SERVER_HOURLY s
  ON s.SERVER_ID = h.server_id AND s.DAY_ = h.day AND s.HOUR_ = h.hour
WHERE h.cluster_id IN (SELECT DISTINCT EVAL_CLUSTER FROM POLICY_BASE);

------------------------------------------------------------------
-- 2. Baseline per server-hour, time-weighted
--    alloc_ideal: GPUs held if fractional requests share GPUs perfectly
--    alloc_noshare: GPUs held if every fractional request takes a whole GPU
------------------------------------------------------------------
CREATE OR REPLACE TABLE SIM2_BASE AS
SELECT server_id, t,
       SUM(w * req)                      AS alloc_ideal,
       SUM(w * CEIL(req - 1e-9))         AS alloc_noshare,
       SUM(w * cpu)                      AS cpu_used,
       SUM(req)                          AS alloc_unweighted
FROM SIM2_POD_HOURS
GROUP BY 1, 2;

------------------------------------------------------------------
-- 3. Change per server-hour when test pods are shrunk
------------------------------------------------------------------
CREATE OR REPLACE TABLE SIM2_DELTA AS
SELECT sl.policy, p.server_id, p.t,
       SUM(p.w * (sl.slice * p.req - p.req))                                   AS d_ideal,
       SUM(p.w * (CEIL(sl.slice * p.req - 1e-9) - CEIL(p.req - 1e-9)))         AS d_noshare,
       SUM(p.w * (1 - sl.slice) * p.req)                                       AS freed_gpu
FROM SIM_SLICES sl
JOIN SIM2_POD_HOURS p ON p.pod_id = sl.POD_ID AND p.t = sl.t
GROUP BY 1, 2, 3;

------------------------------------------------------------------
-- 4. Usable whole GPUs per server-hour, before and after
------------------------------------------------------------------
CREATE OR REPLACE TABLE SIM2_RESULT AS
WITH pol AS (
  SELECT column1 AS policy FROM VALUES ('A1_fallback6'), ('A3_fallback24'), ('A1_no_fallback')
), srv AS (
  SELECT s.CLUSTER_ID AS cluster_id, s.SERVER_ID AS server_id, s.DAY_ * 24 + s.HOUR_ AS t,
         s.GPU_COUNT AS cap,
         COALESCE(b.alloc_ideal, 0) AS alloc_ideal, COALESCE(b.alloc_noshare, 0) AS alloc_noshare,
         COALESCE(b.alloc_unweighted, 0) AS alloc_unweighted,
         FLOOR(GREATEST(0, s.CPU_CAPACITY_CORES - COALESCE(b.cpu_used, 0)) / NULLIF(pr.cpu_per_gpu, 0)) AS cpu_slots
  FROM SERVER_HOURLY s
  LEFT JOIN SIM2_BASE b ON b.server_id = s.SERVER_ID AND b.t = s.DAY_ * 24 + s.HOUR_
  JOIN SIM_PROBE pr ON pr.CLUSTER_ID = s.CLUSTER_ID
  WHERE s.CLUSTER_ID IN (SELECT DISTINCT EVAL_CLUSTER FROM POLICY_BASE)
), x AS (
  SELECT pol.policy, srv.*,
         COALESCE(d.d_ideal, 0) AS d_ideal, COALESCE(d.d_noshare, 0) AS d_noshare,
         COALESCE(d.freed_gpu, 0) AS freed_gpu
  FROM srv CROSS JOIN pol
  LEFT JOIN SIM2_DELTA d ON d.policy = pol.policy AND d.server_id = srv.server_id AND d.t = srv.t
)
SELECT policy, cluster_id,
       COUNT(*)                                            AS server_hours,
       SUM(cap)                                            AS gpu_hours_capacity,
       SUM(alloc_unweighted)                               AS gpu_hours_alloc_unweighted,
       SUM(alloc_ideal)                                    AS gpu_hours_alloc_weighted,
       COUNT_IF(alloc_ideal > cap + 1e-6)                  AS server_hours_overallocated,
       SUM(freed_gpu)                                      AS gpu_hours_freed,
       SUM(GREATEST(0, FLOOR(cap - alloc_ideal + 1e-6)))                                       AS free_whole_base_ideal,
       SUM(GREATEST(0, FLOOR(cap - alloc_ideal - d_ideal + 1e-6)))                             AS free_whole_new_ideal,
       SUM(GREATEST(0, LEAST(FLOOR(cap - alloc_ideal + 1e-6), cpu_slots)))                     AS usable_base_ideal,
       SUM(GREATEST(0, LEAST(FLOOR(cap - alloc_ideal - d_ideal + 1e-6), cpu_slots)))           AS usable_new_ideal,
       SUM(GREATEST(0, LEAST(FLOOR(cap - alloc_noshare + 1e-6), cpu_slots)))                   AS usable_base_noshare,
       SUM(GREATEST(0, LEAST(FLOOR(cap - alloc_noshare - d_noshare + 1e-6), cpu_slots)))       AS usable_new_noshare
FROM x
GROUP BY 1, 2;

------------------------------------------------------------------
-- 5. Download as CSV and send (30 rows)
------------------------------------------------------------------
SELECT * FROM SIM2_RESULT ORDER BY policy, cluster_id;

ALTER WAREHOUSE ASI_WH SET WAREHOUSE_SIZE = 'XSMALL';
