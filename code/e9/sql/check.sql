SELECT count(*) AS pods, count_if(n_pod_hours >= 24 AND t_first/24 BETWEEN 14 AND 183) AS d1_like,
       count_if(t_first/24 BETWEEN 14 AND 183) AS adm_14_183, count(DISTINCT gpu_request) AS sizes,
       count_if(workload_id IS NOT NULL) AS with_wl
FROM alibaba_trace.d1_pods
