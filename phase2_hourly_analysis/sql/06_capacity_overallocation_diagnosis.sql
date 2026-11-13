-- Why do pods' GPU requests add up to more than servers' GPUs?
-- Run in Snowflake. Uses one cluster (6d5f) on one day (170) to stay fast.

USE WAREHOUSE ASI_WH;
USE SCHEMA ASI_TRACE.RAW;

-- D1. Request totals vs. time-weighted totals per server-hour
WITH s AS (
  SELECT h.server_id, h.day, h.hour,
         SUM(h.gpu_request)    AS req,
         SUM(h.used_gpu_hours) AS used_h,
         COUNT(*)              AS n_pods,
         COUNT_IF(h.gpu_request > 0) AS n_gpu_pods
  FROM POD_HOURLY h
  WHERE h.cluster_id = '6d5f55ee85c1bb785b2cba94ef7545b3' AND h.day = 170
  GROUP BY 1, 2, 3
)
SELECT COUNT(*)                                       AS server_hours,
       COUNT_IF(s.req    > v.GPU_COUNT + 1e-9)        AS over_by_request,
       COUNT_IF(s.used_h > v.GPU_COUNT + 1e-9)        AS over_by_used_gpu_hours,
       SUM(s.req)    / SUM(v.GPU_COUNT)               AS ratio_request,
       SUM(s.used_h) / SUM(v.GPU_COUNT)               AS ratio_used_gpu_hours,
       AVG(s.n_gpu_pods)                              AS avg_gpu_pods_per_server_hour
FROM s
JOIN SERVER_HOURLY v ON v.SERVER_ID = s.server_id AND v.DAY_ = s.day AND v.HOUR_ = s.hour;

-- D2. What is used_gpu_hours? Its ratio to the request, for GPU pods
SELECT APPROX_PERCENTILE(used_gpu_hours / gpu_request, 0.05) AS p05,
       APPROX_PERCENTILE(used_gpu_hours / gpu_request, 0.25) AS p25,
       APPROX_PERCENTILE(used_gpu_hours / gpu_request, 0.50) AS p50,
       APPROX_PERCENTILE(used_gpu_hours / gpu_request, 0.95) AS p95,
       COUNT_IF(ABS(used_gpu_hours / gpu_request - 1) < 1e-6) / COUNT(*) AS share_exactly_full_hour,
       COUNT_IF(used_gpu_hours IS NULL) / COUNT(*)                     AS share_null
FROM POD_HOURLY
WHERE cluster_id = '6d5f55ee85c1bb785b2cba94ef7545b3' AND day = 170 AND gpu_request > 0;

-- D3. The pods on the 3 most over-allocated server-hours (send all rows)
WITH s AS (
  SELECT h.server_id, h.day, h.hour, SUM(h.gpu_request) AS req
  FROM POD_HOURLY h
  WHERE h.cluster_id = '6d5f55ee85c1bb785b2cba94ef7545b3' AND h.day = 170
  GROUP BY 1, 2, 3
), worst AS (
  SELECT s.server_id, s.day, s.hour, s.req, v.GPU_COUNT
  FROM s JOIN SERVER_HOURLY v ON v.SERVER_ID = s.server_id AND v.DAY_ = s.day AND v.HOUR_ = s.hour
  ORDER BY s.req - v.GPU_COUNT DESC LIMIT 3
)
SELECT w.server_id, w.hour, w.GPU_COUNT, w.req AS server_req_total,
       h.pod_id, h.job_type_public, h.model_type_public, h.priority_class, h.state_public,
       h.gpu_request, h.used_gpu_hours, h.cpu_request_cores, h.ready_status, h.avg_gpu_sm_util
FROM worst w
JOIN POD_HOURLY h ON h.server_id = w.server_id AND h.day = w.day AND h.hour = w.hour
ORDER BY w.server_id, h.gpu_request DESC;
