-- Per-pod summary from the slim table (cheap): admission attributes and P90 / P99 / max labels.
CREATE TABLE alibaba_trace.d1_pods
WITH (format = 'PARQUET', write_compression = 'ZSTD',
      external_location = 's3://alibaba-cluster-data-migration-445056752928/athena-tables/d1_pods/') AS
SELECT pod_id,
       min_by(workload_id, t) AS workload_id, min_by(server_id, t) AS server_id, min_by(cluster_id, t) AS cluster_id,
       min_by(gpu_spec_public, t) AS gpu_spec_public, min_by(priority_class, t) AS priority_class,
       min_by(model_type, t) AS model_type_public, min_by(is_genai_request, t) AS is_genai_request,
       min_by(gpu_request, t) AS gpu_request, min_by(gpu_mem_request, t) AS gpu_mem_request,
       min_by(cpu_request_cores, t) AS cpu_request_cores, min_by(server_gpu_count, t) AS server_gpu_count,
       min_by(server_cpu_capacity_cores, t) AS server_cpu_capacity_cores,
       min(t) AS t_first, max(t) AS t_last, count(*) AS n_pod_hours, count(need_sm) AS n_hours_with_util,
       approx_percentile(need_sm, 0.90) AS sm_p90, approx_percentile(need_mem, 0.90) AS mem_p90,
       approx_percentile(need_sm, 0.99) AS sm_p99, approx_percentile(need_mem, 0.99) AS mem_p99,
       max(need_sm) AS sm_max, max(need_mem) AS mem_max
FROM alibaba_trace.d1_hourly
GROUP BY pod_id
