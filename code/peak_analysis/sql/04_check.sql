SELECT count(*) AS rows, count(DISTINCT pod_id) AS pods, min(t)/24 AS d0, max(t)/24 AS d1,
       approx_percentile(greatest(need_sm, need_mem), 0.5) AS med_need, count_if(need_sm IS NULL OR need_mem IS NULL) AS null_needs
FROM pop_hourly
