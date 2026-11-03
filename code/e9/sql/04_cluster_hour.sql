-- Cluster-hour load over ALL pods, from server_hour (cheap). sm_p90 is the P90 across servers' mean SM.
CREATE TABLE alibaba_trace.cluster_hour_all
WITH (format = 'PARQUET', write_compression = 'ZSTD',
      external_location = 's3://alibaba-cluster-data-migration-445056752928/athena-tables/cluster_hour_all/') AS
SELECT cluster_id, t, sum(n_pods) AS pods, sum(gpu_alloc) AS gpu_alloc,
       sum(sm_sum) / nullif(sum(sm_n), 0) AS sm_mean,
       approx_percentile(sm_sum / nullif(sm_n, 0), 0.90) AS sm_p90
FROM alibaba_trace.server_hour GROUP BY cluster_id, t
