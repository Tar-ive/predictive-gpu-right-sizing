SELECT gpu_request, count(*) n FROM alibaba_trace.d1_pods WHERE t_first/24 BETWEEN 14 AND 183 GROUP BY 1 ORDER BY 1
