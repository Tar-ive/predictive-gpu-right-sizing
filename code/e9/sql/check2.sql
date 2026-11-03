SELECT count_if(n_hours_with_util >= 24) AS util24,
       count_if(n_pod_hours >= 24 AND t_last < 184*24+23) AS done24,
       count_if(n_hours_with_util >= 24 AND t_last < 184*24+23) AS util24_done,
       count_if(n_pod_hours >= 24 AND t_first > 13*24) AS h24,
       count_if(n_pod_hours >= 24 AND gpu_mem_request > 0) AS mem24,
       count_if(n_pod_hours >= 24 AND sm_p90 IS NOT NULL AND mem_p90 IS NOT NULL) AS both24,
       count_if(n_pod_hours > 24) AS gt24,
       count_if(n_pod_hours >= 24 AND t_last - t_first + 1 = n_pod_hours) AS contiguous24
FROM alibaba_trace.d1_pods WHERE t_first/24 BETWEEN 14 AND 183
