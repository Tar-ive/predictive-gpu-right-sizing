"""Fetch online-inference pod-hours straight from the public ASI trace ZIP (351 GB) with HTTP range requests.

usage: python fetch_trace.py <out_dir> <first_day> <last_day>

Each hourly parquet is stored uncompressed inside the ZIP, so one hour (~79 MB) is pulled in 16 parallel
5 MB ranges (~4 s at ~40 MB/s), filtered to job_type_public='online_inference' and gpu_request > 0, and saved.
No cloud account is needed. 22 days (days 90-111) take ~35 min and ~1.4 GB on disk.
"""
import rzip, pyarrow.parquet as pq, pyarrow.compute as pc, pyarrow as pa, io, os, sys, time, concurrent.futures as cf
OUT=sys.argv[1]; d0,d1=int(sys.argv[2]),int(sys.argv[3]); os.makedirs(OUT,exist_ok=True)
U='https://tre-clusterdata.oss-cn-hangzhou.aliyuncs.com/cluster-trace-gpu-v2026/data/asi_opensource_pod_hourly.zip'
COLS=['pod_id','workload_id','server_id','cluster_id','state_public','gpu_spec_public','server_gpu_count','priority_class',
      'job_type_public','model_type_public','gpu_request','gpu_mem_request','cpu_request_cores','used_gpu_hours',
      'avg_gpu_sm_util','avg_gpu_mem_gib','ready_status']
M={m['name']:m for m in rzip.members(U)}; POOL=cf.ThreadPoolExecutor(16); CH=5<<20
def get(m):
    off=rzip.data_offset(U,m); n=m['usize']
    parts=list(POOL.map(lambda a:(a,rzip.rng(U,off+a,off+min(a+CH,n))),range(0,n,CH)))
    buf=bytearray(n)
    for a,b in parts: buf[a:a+len(b)]=b
    return bytes(buf)
for d in range(d0,d1+1):
    for h in range(24):
        p=f'{OUT}/d{d:03d}h{h:02d}.parquet'
        if os.path.exists(p): continue
        t0=time.time()
        for a in range(4):
            try:
                raw=get(M[f'asi_opensource_pod_hourly/day={d}/hour={h:02d}/part-000.parquet']); break
            except Exception as e: print('retry',d,h,e,flush=True); time.sleep(5*2**a)
        f=pq.ParquetFile(io.BytesIO(raw)); t=f.read(columns=[c for c in COLS if c in f.schema_arrow.names])
        t=t.filter(pc.and_(pc.equal(t['job_type_public'],'online_inference'),pc.greater(t['gpu_request'],0)))
        t=t.append_column('day',pa.array([d]*len(t),pa.int16())).append_column('hour',pa.array([h]*len(t),pa.int8()))
        pq.write_table(t,p+'.tmp'); os.rename(p+'.tmp',p); print(d,h,len(t),round(time.time()-t0,1),flush=True)
