-- Per-pod table + admission-time context (pods with a workload id, plus every D1 pod).
CREATE TABLE alibaba_trace.d1_export
WITH (format = 'PARQUET', write_compression = 'ZSTD',
      external_location = 's3://alibaba-cluster-data-migration-445056752928/athena-tables/d1_export/') AS
SELECT p.*,
       s.gpu_alloc AS server_alloc_gpu_at_submit, s.server_gpus,
       c0.pods AS cluster_pods_at_submit, c0.gpu_alloc AS cluster_gpu_requested_at_submit,
       c1.sm_mean AS cluster_sm_mean_prev_hr, c1.sm_p90 AS cluster_sm_p90_prev_hr
FROM alibaba_trace.d1_pods p
LEFT JOIN alibaba_trace.server_hour s ON s.server_id = p.server_id AND s.t = p.t_first
LEFT JOIN alibaba_trace.cluster_hour_all c0 ON c0.cluster_id = p.cluster_id AND c0.t = p.t_first
LEFT JOIN alibaba_trace.cluster_hour_all c1 ON c1.cluster_id = p.cluster_id AND c1.t = p.t_first - 1
WHERE p.workload_id IS NOT NULL
   OR (p.n_pod_hours >= 24 AND p.sm_p90 IS NOT NULL AND p.mem_p90 IS NOT NULL)
