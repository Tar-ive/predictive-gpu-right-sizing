-- Load the Alibaba ASI pod-hourly trace into Snowflake.
-- Run Part A before the Python upload script, and Parts B-D after it finishes.

---------------------------------------------------------------
-- Part A: setup (run once, before uploading)
---------------------------------------------------------------
CREATE WAREHOUSE IF NOT EXISTS ASI_WH
  WAREHOUSE_SIZE = 'XSMALL' AUTO_SUSPEND = 60 AUTO_RESUME = TRUE;
CREATE DATABASE IF NOT EXISTS ASI_TRACE;
CREATE SCHEMA IF NOT EXISTS ASI_TRACE.RAW;
USE SCHEMA ASI_TRACE.RAW;

CREATE STAGE IF NOT EXISTS ASI_STAGE FILE_FORMAT = (TYPE = PARQUET);

CREATE TABLE IF NOT EXISTS POD_HOURLY (
  pod_id STRING, workload_id STRING, server_id STRING, cluster_id STRING,
  state_public STRING, gpu_spec_public STRING,
  server_gpu_count DOUBLE, server_cpu_capacity_cores DOUBLE,
  priority_class STRING, job_type_public STRING, model_type_public STRING,
  is_genai_request BOOLEAN,
  gpu_request DOUBLE, gpu_mem_request DOUBLE, cpu_request_cores DOUBLE,
  used_gpu_hours DOUBLE, avg_gpu_sm_util DOUBLE, avg_gpu_mem_gib DOUBLE,
  avg_cpu_request_util DOUBLE, avg_memory_util DOUBLE,
  ready_status BOOLEAN, schedule_delay_sec NUMBER, ready_delay_sec NUMBER,
  day INT, hour INT,
  source_file STRING
);

---------------------------------------------------------------
-- Part B: check the uploaded files (after the Python script)
---------------------------------------------------------------
LIST @ASI_STAGE/asi_opensource_pod_hourly/;   -- expect 24 files per day

-- Look at one file's column names before loading
SELECT $1 FROM @ASI_STAGE/asi_opensource_pod_hourly/ LIMIT 3;

---------------------------------------------------------------
-- Part C: load. Day and hour come from the folder names, which is
-- the step that went missing in the first load.
---------------------------------------------------------------
ALTER WAREHOUSE ASI_WH SET WAREHOUSE_SIZE = 'MEDIUM';  -- faster load; set back after

COPY INTO POD_HOURLY
FROM (
  SELECT
    $1:pod_id::STRING, $1:workload_id::STRING, $1:server_id::STRING, $1:cluster_id::STRING,
    $1:state_public::STRING, $1:gpu_spec_public::STRING,
    $1:server_gpu_count::DOUBLE, $1:server_cpu_capacity_cores::DOUBLE,
    $1:priority_class::STRING, $1:job_type_public::STRING, $1:model_type_public::STRING,
    $1:is_genai_request::BOOLEAN,
    $1:gpu_request::DOUBLE, $1:gpu_mem_request::DOUBLE, $1:cpu_request_cores::DOUBLE,
    $1:used_gpu_hours::DOUBLE, $1:avg_gpu_sm_util::DOUBLE, $1:avg_gpu_mem_gib::DOUBLE,
    $1:avg_cpu_request_util::DOUBLE, $1:avg_memory_util::DOUBLE,
    $1:ready_status::BOOLEAN, $1:schedule_delay_sec::NUMBER, $1:ready_delay_sec::NUMBER,
    REGEXP_SUBSTR(METADATA$FILENAME, 'day=([0-9]+)', 1, 1, 'e', 1)::INT,
    REGEXP_SUBSTR(METADATA$FILENAME, 'hour=([0-9]+)', 1, 1, 'e', 1)::INT,
    METADATA$FILENAME
  FROM @ASI_STAGE/asi_opensource_pod_hourly/
)
PATTERN = '.*[.]parquet'
ON_ERROR = 'ABORT_STATEMENT';

ALTER WAREHOUSE ASI_WH SET WAREHOUSE_SIZE = 'XSMALL';

---------------------------------------------------------------
-- Part D: checks
---------------------------------------------------------------
-- 1. Day and hour filled in every row (both counts should be 0)
SELECT COUNT_IF(day IS NULL) AS missing_day, COUNT_IF(hour IS NULL) AS missing_hour
FROM POD_HOURLY;

-- 2. Every day has 24 hours
SELECT day, COUNT(DISTINCT hour) AS hours, COUNT(*) AS rows_loaded
FROM POD_HOURLY GROUP BY day ORDER BY day;

-- 3. Pod IDs match your project data. Replace the D1 table name with yours.
--    A low match share means the IDs changed between releases; stop and check before analysis.
SELECT COUNT(*) AS d1_test_pods,
       COUNT_IF(h.pod_id IS NOT NULL) AS found_in_new_load
FROM (SELECT DISTINCT pod_id FROM YOUR_DB.YOUR_SCHEMA.D1_RIGHTSIZING
      WHERE admission_day BETWEEN 158 AND 183) d
LEFT JOIN (SELECT DISTINCT pod_id FROM POD_HOURLY) h USING (pod_id);
