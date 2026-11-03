WITH h AS (
  SELECT p.cluster_id, p.t, coalesce(c.decile, 0) AS decile, s.gpu_request AS req, s.sf90,
         greatest(p.need_sm, p.need_mem) AS need
  FROM pop_hourly p JOIN pod_slice s ON s.pod_id = p.pod_id
  LEFT JOIN cluster_hour c ON c.cluster_id = p.cluster_id AND c.t = p.t
  WHERE p.t BETWEEN 158*24 AND 184*24 - 1 AND p.need_sm IS NOT NULL AND p.need_mem IS NOT NULL),
ch AS (
  SELECT cluster_id, t, decile, sum(greatest(need - sf90, 0) * req) AS short_gpus, sum((1 - sf90) * req) AS freed_gpus,
         count(*) AS pods
  FROM h GROUP BY 1,2,3)
SELECT decile, count(*) AS cluster_hours,
       approx_percentile(short_gpus / nullif(freed_gpus,0), 0.5) AS med_short_share,
       approx_percentile(short_gpus / nullif(freed_gpus,0), 0.99) AS p99_short_share,
       max(short_gpus / nullif(freed_gpus,0)) AS worst_short_share
FROM ch WHERE pods >= 20 GROUP BY 1 ORDER BY 1
