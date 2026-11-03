-- Run once per readable day range (days 0-5 store gpu_request as INT64 and fail; ranges used: 6-29, 30-99, 100-184).
SELECT DISTINCT gpu_request FROM pod_hourly WHERE day BETWEEN 100 AND 184 AND gpu_request > 0 AND job_type_public = 'online_inference' ORDER BY 1
