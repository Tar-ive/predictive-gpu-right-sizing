-- H5 (workload mixing) and H7 (production vs non-production): one pod-level table for analysis.
-- Run in Snowflake top to bottom, then download the final SELECT as CSV (about 45,700 rows).
-- Uses MODEL_A (D1), REPLAY_PODS, PRED_A_V1, REPLAY_RESULT, POD_HOURLY.
--
-- Server mix is measured in the hour BEFORE each pod's admission (so the pod itself and anything
-- admitted later in that hour cannot leak in), weighted by time present (used_gpu_hours).

USE WAREHOUSE ASI_WH;
USE SCHEMA ASI_TRACE.RAW;
ALTER WAREHOUSE ASI_WH SET WAREHOUSE_SIZE = 'MEDIUM';

------------------------------------------------------------------
-- 1. Admission time (from D1) and the server each test pod first ran on
------------------------------------------------------------------
CREATE OR REPLACE TABLE ADM_SERVER AS
SELECT h.pod_id, h.server_id,
       p.ADM_DAY * 24 + CAST(d.ADM_HOUR AS INT) AS t_adm
FROM POD_HOURLY h
JOIN REPLAY_PODS p ON p.POD_ID = h.pod_id
JOIN MODEL_A d     ON d.POD_ID = h.pod_id
QUALIFY ROW_NUMBER() OVER (PARTITION BY h.pod_id ORDER BY h.day, h.hour) = 1;

SELECT COUNT(*) AS pods, COUNT_IF(server_id IS NULL) AS no_server FROM ADM_SERVER;   -- expect 45,669 and 0

------------------------------------------------------------------
-- 2. Mix of GPU use on that server in the hour before admission
------------------------------------------------------------------
CREATE OR REPLACE TABLE SERVER_MIX AS
WITH need AS (
  SELECT DISTINCT server_id, t_adm - 1 AS t FROM ADM_SERVER
), occ AS (
  SELECT h.server_id, h.day * 24 + h.hour AS t,
         h.model_type_public AS mt, h.job_type_public AS jt, h.priority_class AS pc,
         COALESCE(h.used_gpu_hours, 0) AS gpu_h
  FROM POD_HOURLY h
  JOIN need n ON n.server_id = h.server_id AND n.t = h.day * 24 + h.hour
  WHERE h.gpu_request > 0
)
SELECT server_id, t,
       SUM(gpu_h)                                                       AS mix_gpu_h,
       SUM(IFF(mt = 'rec',   gpu_h, 0)) / NULLIF(SUM(gpu_h), 0)         AS rec_share,
       SUM(IFF(mt = 'genai', gpu_h, 0)) / NULLIF(SUM(gpu_h), 0)         AS genai_share,
       SUM(IFF(jt = 'training',          gpu_h, 0)) / NULLIF(SUM(gpu_h), 0) AS training_share,
       SUM(IFF(jt = 'offline_inference', gpu_h, 0)) / NULLIF(SUM(gpu_h), 0) AS offline_share,
       SUM(IFF(jt = 'online_inference',  gpu_h, 0)) / NULLIF(SUM(gpu_h), 0) AS online_share,
       SUM(IFF(pc = 'HP', gpu_h, 0)) / NULLIF(SUM(gpu_h), 0)            AS hp_share,
       COUNT(DISTINCT jt)                                               AS n_job_types
FROM occ
GROUP BY 1, 2;

-- Which priority classes and model types exist (send this small result too)
SELECT priority_class, model_type_public, job_type_public, COUNT(*) AS pod_hours
FROM POD_HOURLY WHERE day = 170 AND gpu_request > 0
GROUP BY 1, 2, 3 ORDER BY 4 DESC;

------------------------------------------------------------------
-- 3. One row per test pod: features, mix, predictions (unseen clusters), hourly shortfalls
------------------------------------------------------------------
CREATE OR REPLACE TABLE H57_PODS AS
WITH pr AS (
  SELECT POD_ID,
         MAX(IFF(MODEL = 'A1', PRED_RAW,   NULL)) AS a1_raw,
         MAX(IFF(MODEL = 'A1', SLICE_FRAC, NULL)) AS a1_slice,
         MAX(IFF(MODEL = 'A3', PRED_RAW,   NULL)) AS a3_raw,
         MAX(IFF(MODEL = 'A3', SLICE_FRAC, NULL)) AS a3_slice,
         MAX(STRATUM)            AS stratum,
         MAX(RESERVED_GPU_HOURS) AS reserved_gpu_hours,
         MAX(HELDOUT_CLUSTER)    AS heldout_cluster
  FROM PRED_A_V1 WHERE SCENARIO = 'loco'
  GROUP BY 1
), rp AS (
  SELECT POD_ID,
         SUM(IFF(MODEL = 'A1', 1, 0))                          AS hours,
         SUM(IFF(MODEL = 'A1', GREATEST(sm_over, mem_over), 0)) AS a1_short_h,
         SUM(IFF(MODEL = 'A1', mem_over, 0))                    AS a1_mem_short_h,
         SUM(IFF(MODEL = 'A3', GREATEST(sm_over, mem_over), 0)) AS a3_short_h,
         SUM(IFF(MODEL = 'A3', mem_over, 0))                    AS a3_mem_short_h,
         STDDEV(IFF(MODEL = 'A1', GREATEST_IGNORE_NULLS(sm_frac, mem_frac), NULL)) AS hourly_need_sd
  FROM REPLAY_RESULT
  WHERE SCENARIO = 'loco' AND MODEL IN ('A1', 'A3')
  GROUP BY 1
)
SELECT d.POD_ID, d.CLUSTER_ID, d.WORKLOAD_ID, d.MODEL_TYPE_PUBLIC, d.PRIORITY_CLASS, d.GPU_SPEC_PUBLIC,
       d.GPU_REQUEST, d.WL_HIST_POD_COUNT, d.N_POD_HOURS, d.ADM_DAY, d.Y_MVF,
       m.mix_gpu_h, m.rec_share, m.genai_share, m.training_share, m.offline_share,
       m.online_share, m.hp_share, m.n_job_types,
       pr.heldout_cluster, pr.stratum, pr.reserved_gpu_hours,
       pr.a1_raw, pr.a1_slice, pr.a3_raw, pr.a3_slice,
       rp.hours, rp.a1_short_h, rp.a1_mem_short_h, rp.a3_short_h, rp.a3_mem_short_h, rp.hourly_need_sd
FROM MODEL_A d
JOIN REPLAY_PODS p      ON p.POD_ID = d.POD_ID
JOIN ADM_SERVER a       ON a.pod_id = d.POD_ID
LEFT JOIN SERVER_MIX m  ON m.server_id = a.server_id AND m.t = a.t_adm - 1
LEFT JOIN pr            ON pr.POD_ID = d.POD_ID
LEFT JOIN rp            ON rp.POD_ID = d.POD_ID;

SELECT COUNT(*) AS rows_, COUNT_IF(rec_share IS NULL) AS no_mix, COUNT_IF(a1_slice IS NULL) AS not_in_loco
FROM H57_PODS;

------------------------------------------------------------------
-- 4. Download as CSV and send
------------------------------------------------------------------
SELECT * FROM H57_PODS;

ALTER WAREHOUSE ASI_WH SET WAREHOUSE_SIZE = 'XSMALL';
