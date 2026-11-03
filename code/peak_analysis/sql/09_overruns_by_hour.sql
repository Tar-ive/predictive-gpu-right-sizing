WITH h AS (
  SELECT p.hod, coalesce(c.decile, 0) AS decile, s.gpu_request AS req, s.sf90, s.sfpk,
         greatest(p.need_sm, p.need_mem) AS need
  FROM pop_hourly p JOIN pod_slice s ON s.pod_id = p.pod_id
  LEFT JOIN cluster_hour c ON c.cluster_id = p.cluster_id AND c.t = p.t
  WHERE p.t BETWEEN 158*24 AND 184*24 - 1 AND p.need_sm IS NOT NULL AND p.need_mem IS NOT NULL)
SELECT 'hour' AS dim, hod AS bucket, count(*) AS pod_hours,
       avg(IF(need > sf90 + 1e-9, 1.0, 0.0)) AS over_p90_slice,
       avg(IF(need > sfpk + 1e-9, 1.0, 0.0)) AS over_peak_slice,
       sum(greatest(need - sf90, 0) * req) / sum((1 - sf90) * req) AS shortfall_vs_reclaimed_p90
FROM h GROUP BY 2 ORDER BY 2
