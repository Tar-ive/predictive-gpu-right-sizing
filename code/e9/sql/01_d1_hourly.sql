-- The one large scan, part 1 of 3: slim hourly table for the D1 scope (all 185 days).
-- day=5/hour=06 stores numeric columns as INT64 and is skipped.
CREATE TABLE alibaba_trace.d1_hourly
WITH (format = 'PARQUET', write_compression = 'ZSTD',
      external_location = 's3://alibaba-cluster-data-migration-445056752928/athena-tables/d1_hourly/') AS
SELECT pod_id, workload_id, server_id, cluster_id, gpu_spec_public, priority_class,
       model_type_public AS model_type, is_genai_request, gpu_request, gpu_mem_request,
       cpu_request_cores, server_gpu_count, server_cpu_capacity_cores,
       day * 24 + CAST(hour AS integer) AS t,
       avg_gpu_sm_util / gpu_request / 100.0 AS need_sm,
       CASE WHEN gpu_mem_request > 0 THEN avg_gpu_mem_gib / (gpu_mem_request / 1073741824.0) END AS need_mem
FROM alibaba_trace.pod_hourly
WHERE day BETWEEN 0 AND 60 AND NOT (day = 5 AND hour = '06')
  AND job_type_public = 'online_inference'
  AND model_type_public IN ('rec', 'genai')
  AND gpu_request > 0
