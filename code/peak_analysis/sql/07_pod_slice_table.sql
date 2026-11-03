CREATE EXTERNAL TABLE IF NOT EXISTS alibaba_trace.pod_slice (pod_id string, gpu_request double, sf90 double, sfpk double)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
LOCATION 's3://alibaba-cluster-data-migration-445056752928/athena-tables/pod_slice/'
TBLPROPERTIES ('skip.header.line.count'='1')
