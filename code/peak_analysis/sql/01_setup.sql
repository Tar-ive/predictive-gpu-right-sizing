CREATE DATABASE IF NOT EXISTS alibaba_trace;
CREATE EXTERNAL TABLE IF NOT EXISTS alibaba_trace.pod_hourly (
  pod_id string, workload_id string, server_id string, cluster_id string, state_public string,
  gpu_spec_public string, server_gpu_count bigint, server_cpu_capacity_cores bigint, priority_class string,
  job_type_public string, model_type_public string, is_genai_request boolean, gpu_request double,
  gpu_mem_request bigint, cpu_request_cores double, used_gpu_hours double, avg_gpu_sm_util double,
  avg_gpu_mem_gib double, avg_cpu_request_util double, avg_memory_util double, ready_status boolean,
  schedule_delay_sec bigint, ready_delay_sec bigint)
PARTITIONED BY (day int, hour string)
STORED AS PARQUET
LOCATION 's3://alibaba-cluster-data-migration-445056752928/alibaba_v2026/pod_hourly/asi_opensource_pod_hourly/'
TBLPROPERTIES (
  'projection.enabled'='true',
  'projection.day.type'='integer', 'projection.day.range'='0,184',
  'projection.hour.type'='integer', 'projection.hour.range'='0,23', 'projection.hour.digits'='2',
  'storage.location.template'='s3://alibaba-cluster-data-migration-445056752928/alibaba_v2026/pod_hourly/asi_opensource_pod_hourly/day=${day}/hour=${hour}/');
