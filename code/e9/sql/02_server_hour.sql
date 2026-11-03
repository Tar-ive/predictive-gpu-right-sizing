-- The one large scan, part 2: per server-hour allocation over ALL pods (any job type).
CREATE TABLE alibaba_trace.server_hour
WITH (format = 'PARQUET', write_compression = 'ZSTD',
      external_location = 's3://alibaba-cluster-data-migration-445056752928/athena-tables/server_hour/') AS
SELECT server_id, cluster_id, day * 24 + CAST(hour AS integer) AS t,
       count(*) AS n_pods, sum(gpu_request) AS gpu_alloc, max(server_gpu_count) AS server_gpus,
       sum(avg_gpu_sm_util) AS sm_sum, count(avg_gpu_sm_util) AS sm_n
FROM alibaba_trace.pod_hourly
WHERE NOT (day = 5 AND hour = '06')
GROUP BY server_id, cluster_id, day * 24 + CAST(hour AS integer)
