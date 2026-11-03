WITH first_seen AS (
  SELECT pod_id, min(t) AS t0 FROM pop_hourly GROUP BY pod_id),
pop AS (
  SELECT pod_id FROM first_seen WHERE t0 BETWEEN 158*24 AND 184*24 - 1),
h AS (
  SELECT p.pod_id, p.cluster_id, p.model_type, p.priority_class, p.gpu_request, p.t, p.need_sm, p.need_mem,
         coalesce(c.decile, 0) AS decile
  FROM pop_hourly p JOIN pop q ON q.pod_id = p.pod_id
  LEFT JOIN cluster_hour c ON c.cluster_id = p.cluster_id AND c.t = p.t)
SELECT pod_id, arbitrary(cluster_id) AS cluster_id, arbitrary(model_type) AS model_type, arbitrary(priority_class) AS priority_class,
       max(gpu_request) AS gpu_request, count(*) AS n_hours,
       count_if(need_sm IS NOT NULL AND need_mem IS NOT NULL) AS n_util,
       count_if(decile = 10 AND need_sm IS NOT NULL AND need_mem IS NOT NULL) AS n_peak,
       greatest(approx_percentile(need_sm, 0.90), approx_percentile(need_mem, 0.90)) AS l90,
       greatest(approx_percentile(need_sm, 0.99), approx_percentile(need_mem, 0.99)) AS l99,
       greatest(max(need_sm), max(need_mem)) AS lmax,
       greatest(approx_percentile(need_sm, 0.90) FILTER (WHERE decile = 10), approx_percentile(need_mem, 0.90) FILTER (WHERE decile = 10)) AS lpk90,
       greatest(max(need_sm) FILTER (WHERE decile = 10), max(need_mem) FILTER (WHERE decile = 10)) AS lpkmax
FROM h GROUP BY pod_id
HAVING count(*) >= 24 AND count_if(need_sm IS NOT NULL AND need_mem IS NOT NULL) >= 1
