CREATE TABLE alibaba_trace.cluster_hour
WITH (format = 'PARQUET', external_location = 's3://alibaba-cluster-data-migration-445056752928/athena-tables/cluster_hour/') AS
WITH d AS (
  SELECT cluster_id, t, min(hod) AS hod,
         sum(coalesce(greatest(need_sm, need_mem), need_sm, need_mem, 0) * gpu_request) AS demand_gpus,
         sum(gpu_request) AS reserved_gpus
  FROM pop_hourly WHERE t BETWEEN 158*24 AND 184*24 - 1
  GROUP BY cluster_id, t)
SELECT *, ntile(10) OVER (PARTITION BY cluster_id ORDER BY demand_gpus) AS decile FROM d
