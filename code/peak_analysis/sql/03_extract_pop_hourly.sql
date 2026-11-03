CREATE TABLE alibaba_trace.pop_hourly
WITH (format = 'PARQUET', write_compression = 'ZSTD',
      external_location = 's3://alibaba-cluster-data-migration-445056752928/athena-tables/pop_hourly/') AS
SELECT pod_id, cluster_id, model_type_public AS model_type, priority_class, gpu_request,
       day * 24 + CAST(hour AS integer) AS t,
       CAST(hour AS integer) AS hod,
       avg_gpu_sm_util / gpu_request / 100.0                         AS need_sm,
       avg_gpu_mem_gib / (gpu_mem_request / 1073741824.0)           AS need_mem
FROM pod_hourly
WHERE day BETWEEN 157 AND 184
  AND job_type_public = 'online_inference'
  AND model_type_public IN ('rec','genai')
  AND gpu_request >= 1 AND gpu_request = floor(gpu_request)
  AND gpu_mem_request > 0
