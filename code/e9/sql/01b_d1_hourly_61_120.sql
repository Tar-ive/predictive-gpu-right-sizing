INSERT INTO alibaba_trace.d1_hourly
SELECT pod_id, workload_id, server_id, cluster_id, gpu_spec_public, priority_class,
       model_type_public, is_genai_request, gpu_request, gpu_mem_request,
       cpu_request_cores, server_gpu_count, server_cpu_capacity_cores,
       day * 24 + CAST(hour AS integer),
       avg_gpu_sm_util / gpu_request / 100.0,
       CASE WHEN gpu_mem_request > 0 THEN avg_gpu_mem_gib / (gpu_mem_request / 1073741824.0) END
FROM alibaba_trace.pod_hourly
WHERE day BETWEEN 61 AND 120
  AND job_type_public = 'online_inference'
  AND model_type_public IN ('rec', 'genai')
  AND gpu_request > 0
