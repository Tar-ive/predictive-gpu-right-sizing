# Theme: GPU sharing, fractional allocation, fragmentation-aware placement, multi-resource allocation, capacity harvesting

Annotated bibliography for "Reclaimable Is Not Reusable: Evaluating GPU Right-Sizing Under Cluster Shift".
Compiled 2026-11-21. Every number below was read from the opened page or PDF (abstract or body text). Anything not read directly is marked UNVERIFIED.

Organization: (A) fragmentation-aware placement and the ASI context; (B) GPU sharing mechanisms (temporal/spatial/MIG); (C) multi-resource fairness and packing; (D) CPU-aware DL scheduling; (E) harvesting idle reserved capacity; (F) briefer supporting sources.

---

## A. Fragmentation-aware placement and the ASI context

### weng2023fgd (existing key)
**Citation.** Qizhen Weng, Lingyun Yang, Yinghao Yu, Wei Wang, Xiaochuan Tang, Guodong Yang, Liping Zhang. "Beware of Fragmentation: Scheduling GPU-Sharing Workloads with Fragmentation Gradient Descent." USENIX ATC 2023.
**URL opened.** https://www.usenix.org/conference/atc23/presentation/weng
**Key findings.**
- On Alibaba production traces, partial-GPU allocation causes severe fragmentation that leaves hundreds of GPUs unallocatable.
- Defines a statistical fragmentation measure and schedules along its steepest descent (FGD), implemented as a Kubernetes scheduler.
- On an emulated cluster of more than 6,200 GPUs, FGD reduces unallocated GPUs by up to 49% compared with packing-based schedulers, which frees 290 GPUs.
**Strengths.** Production-trace driven, open simulator, and a clear metric for fractional fragmentation.
**Limitations.** Takes pod GPU/CPU requests as given. Its gains are measured on a workload where fractional sharing is common, which no longer holds in ASI (see li2026asi).
**Relation to our paper.** We reuse its simulator and compare FGD against BestFit, GpuPacking, GpuClustering, and DotProd. The policies differ by under 0.6 points of usable capacity, while changing the requests themselves (right-sizing, CPU co-sizing) moves usable capacity by 8–18 points.

### li2026asi (existing key)
**Citation.** Suyi Li, Lingyun Yang, Haoxuan Yu, Sheng Yao, Tianyuan Wu, Xiaoxiao Jiang, Hanfeng Lu, Kangjin Wang, Chenhao Wang, Shenglin Xu, Lun Wang, Qingyang Duan, Shenghao Liang, Xiu Lin, Meng Zhang, Wenchao Wu, Yinghao Yu, Guodong Yang, Liping Zhang, Wei Wang. "Heterogeneity at Hyperscale: Characterization and Scheduling of Large Production AI Clusters at Alibaba." USENIX OSDI 2026 (Operational Systems track).
**URLs opened.** https://www.usenix.org/conference/osdi26/presentation/li-suyi and the PDF https://www.usenix.org/system/files/osdi26-li-suyi.pdf (text extracted locally).
**Key findings.**
- A six-month trace covering 155,410 GPUs from 81 departments. High GPU demand does not yield high effective utilization: idle GPUs are stranded across nodes, blocked by CPU mismatch and network locality, or held as headroom. In the authors' words, fractional-GPU fragmentation "is now negligible, as GPU sharing is rarely used." Fractional requests come almost entirely from classical CV and recommendation models that use MPS.
- A GPU defragmentation algorithm reduces the number of nodes with slack resources by 20.2%.
- **SpotGPU** splits jobs into High-Priority (HP) and Low-Priority (LP) spot classes and adds a "Standby" API, through which HP users release reserved-but-idle tasks for a rebate. Standby GPU hours peak near 10,000 at midnight, and on average 90% of Standby GPU hours are harvested. The average GPU allocation ratio rises from 68% (HP only) to 93% (HP and LP). Eviction averages 13 s (P95 48 s) within a 60 s grace window, with fewer than 5% of evictions SIGKILLed. The preemption-cost-aware scheduler cuts LP task completion time by 24% versus random victim selection.
- Online inference has a median SM utilization of 6%. Co-locating CPU-only jobs to harvest idle CPU reduces the P90 SM utilization of GPU training by 18%.
**Strengths.** The largest and most recent public GPU-cluster characterization. It includes priority metadata and measured results from deployed harvesting.
**Limitations.** Operational paper: harvesting is evaluated by the allocation ratio, not by whether a freed slice can host a given pod shape. It does not study request right-sizing.
**Relation to our paper.** This is our trace. Its finding that fractional fragmentation is negligible under current requests sets up our question: what happens once right-sizing creates fractional residue? SpotGPU harvests at job granularity, but our analysis shows that sub-GPU slices freed by right-sizing rarely become usable.

### yang2025prism (existing key)
**Citation.** Lingyun Yang, Yongchen Wang, Yinghao Yu, Qizhen Weng, Jianbo Dong, Kan Liu, Chi Zhang, Yanyi Zi, Hao Li, Zechao Zhang, Nan Wang, Yu Dong, Menglei Zheng, Lanlan Xi, Xiaowei Lu, Liang Ye, Guodong Yang, Binzhang Fu, Tao Lan, Liping Zhang, Lin Qu, Wei Wang. "GPU-Disaggregated Serving for Deep Learning Recommendation Models at Scale." USENIX NSDI 2025.
**URL opened.** https://www.usenix.org/conference/nsdi25/presentation/yang
**Key findings.**
- DLRMs need many CPU cores and much memory but few GPUs. On multi-GPU servers, CPU and memory run out first and strand the GPUs.
- Prism disaggregates CPU nodes from heterogeneous GPU nodes over RDMA and splits each model into CPU-intensive and GPU-intensive subgraphs.
- In a crowded cluster, it reduces CPU fragmentation by 53% and GPU fragmentation by 27%. During promotions it saves over 90% of GPUs by loaning capacity from training clusters. It has run in production for over two years on more than 10k GPUs.
**Strengths.** Production evidence, from the same organization as our trace, that CPU exhaustion strands GPUs.
**Limitations.** Its fix is architectural (RDMA disaggregation), so it does not carry over to clusters with co-located CPU and GPU. It is specific to DLRMs.
**Relation to our paper.** Independent confirmation of our second blocker (insufficient CPU on the same server). Our CPU co-sizing result (~18 points) is a request-level alternative that needs no change to the hardware topology.

---

## B. GPU sharing mechanisms

### xiao2018gandiva (existing key)
**Citation.** Wencong Xiao, Romil Bhardwaj, Ramachandran Ramjee, Muthian Sivathanu, Nipun Kwatra, Zhenhua Han, Pratyush Patel, Xuan Peng, Hanyu Zhao, Quanlu Zhang, Fan Yang, Lidong Zhou. "Gandiva: Introspective Cluster Scheduling for Deep Learning." USENIX OSDI 2018, pp. 595–610.
**URL opened.** https://www.usenix.org/conference/osdi18/presentation/xiao
**Key findings.**
- Exploits the iteration-level predictability of training to time-slice GPUs, migrate jobs, and pack them.
- Speeds up hyper-parameter search by "up to an order of magnitude."
- Improves aggregate cluster utilization by 26% on a 180-GPU cluster.
**Strengths.** Established time-slicing and packing as cluster-scheduler primitives.
**Limitations.** Training-only, with small-scale evaluation. Assumes jobs tolerate suspend and migration.
**Relation to our paper.** An early form of reclaiming capacity by sharing. Our serving pods cannot be time-sliced freely, so residue has to be usable through placement.

### xiao2020antman (existing key)
**Citation.** Wencong Xiao, Shiru Ren, Yong Li, Yang Zhang, Pengyang Hou, Zhi Li, Yihui Feng, Wei Lin, Yangqing Jia. "AntMan: Dynamic Scaling on GPU Clusters for Deep Learning." USENIX OSDI 2020.
**URL opened.** https://www.usenix.org/conference/osdi20/presentation/xiao
**Key findings.**
- Co-designs the cluster scheduler and the DL framework, dynamically scaling GPU memory and compute so jobs can share a GPU's spare resources.
- Deployed at Alibaba across thousands of GPUs and tens of thousands of daily jobs.
- Raises GPU memory utilization by 42% and compute-unit utilization by 34% without compromising fairness.
**Strengths.** Production-proven opportunistic sharing with interference control.
**Limitations.** Needs framework modification and targets training. Its utilization gains do not show whether the leftover capacity is placeable for new pods.
**Relation to our paper.** Shows that Alibaba already harvests intra-GPU spare capacity for training. We ask the complementary question for serving pods at the request level.

### yu2020salus (NEW)
**Citation.** Peifeng Yu, Mosharaf Chowdhury. "Fine-Grained GPU Sharing Primitives for Deep Learning Applications" (Salus). Proceedings of Machine Learning and Systems 2 (MLSys 2020).
**URL opened.** https://proceedings.mlsys.org/paper_files/paper/2020/hash/d9cd83bc91b8c36a0c7c0fcca59228f2-Abstract.html
**Key findings.**
- Adds two primitives, fast job switching and memory sharing, implemented in TensorFlow.
- Improves average training completion time by 3.19× and hyper-parameter-tuning GPU utilization by 2.38×.
- Improves inference GPU utilization by 42× over no sharing and 7× over NVIDIA MPS.
**Strengths.** Quantifies how much of a GPU small DL jobs leave idle and compares directly against MPS.
**Limitations.** Tied to a single framework and evaluated on a single GPU, with no cluster placement.
**Relation to our paper.** Motivates fractional allocation for small inference models. Our results show that the cluster-level payoff depends on whether fractional residue lines up with demand and with CPU.

```bibtex
@inproceedings{yu2020salus,
  author    = {Yu, Peifeng and Chowdhury, Mosharaf},
  title     = {Fine-Grained {GPU} Sharing Primitives for Deep Learning Applications},
  booktitle = {Proceedings of Machine Learning and Systems (MLSys)},
  volume    = {2},
  year      = {2020},
  url       = {https://proceedings.mlsys.org/paper_files/paper/2020/hash/d9cd83bc91b8c36a0c7c0fcca59228f2-Abstract.html}
}
```

### han2022reef (existing key)
**Citation.** Mingcong Han, Hanze Zhang, Rong Chen, Haibo Chen. "Microsecond-scale Preemption for Concurrent GPU-accelerated DNN Inferences." USENIX OSDI 2022.
**URL opened.** https://www.usenix.org/conference/osdi22/presentation/han
**Key findings.**
- Reset-based kernel preemption (exploiting idempotent inference kernels) and dynamic kernel padding let best-effort kernels fill around real-time ones.
- Adds less than 2% end-to-end latency for real-time tasks and improves throughput by up to 7.7× compared with dedicating the GPU to real-time tasks (AMD GPU).
- A restricted port to NVIDIA hardware reduces preemption latency by up to 12.3× (the page says "from 6.3×"; the exact baseline wording is ambiguous).
**Strengths.** Shows that latency-critical and best-effort inference can share one GPU safely.
**Limitations.** The full system needs an open GPU stack (AMD), and it is a single-GPU mechanism with no cluster placement.
**Relation to our paper.** A device-level way to use idle GPU time. It is orthogonal to our finding that freed capacity is blocked at the server level (CPU, fractional shape) before any device-level mechanism applies.

### strati2024orion (existing key)
**Citation.** Foteini Strati, Xianzhe Ma, Ana Klimovic. "Orion: Interference-aware, Fine-grained GPU Sharing for ML Applications." EuroSys 2024. DOI 10.1145/3627703.3629578.
**URLs opened.** https://fotstrt.github.io/publication/2024-orion and the PDF https://fotstrt.github.io/files/2024-orion.pdf (the ACM DL page returned 403).
**Key findings.**
- Intercepts kernel launches and schedules at operator granularity using each operator's compute and memory profile. Integrated in PyTorch.
- Collocating best-effort inference with a high-priority inference job raises per-GPU request throughput by up to 7.3× while improving tail latency over state-of-the-art baselines.
- Collocating training saves up to 1.49× in training cost versus dedicated GPUs.
**Strengths.** Fine-grained (tens of µs) and interference-aware, with no application changes.
**Limitations.** Needs offline per-operator profiling and works within a single GPU.
**Relation to our paper.** Another sign that devices are underused. Our results show that the binding constraint for reuse is often outside the GPU.

### shubha2024usher (existing key)
**Citation.** Sudipta Saha Shubha, Haiying Shen, Anand Iyer. "USHER: Holistic Interference Avoidance for Resource Optimized ML Inference." USENIX OSDI 2024, pp. 947–964.
**URL opened.** https://www.usenix.org/conference/osdi24/presentation/shubha
**Key findings.**
- Combines a kernel-based estimator of resource needs, an interference-aware scheduler that chooses batch size, replication, and placement, and an operator-graph merger that reduces cache interference.
- Achieves up to 2.6× higher goodput and 3.5× better cost-efficiency than existing methods using production workloads, and scales to thousands of GPUs.
**Strengths.** Jointly sizes and places inference models and considers both compute and memory utilization.
**Limitations.** GPU-centric: CPU and host memory are not part of the placement decision. Evaluated on its own serving stack rather than a multi-tenant Kubernetes cluster.
**Relation to our paper.** The closest serving-side work that sizes as well as places. Our results add that CPU must be co-sized, or freed GPU capacity stays stranded.

### duan2024muxserve (existing key; venue confirmed)
**Citation.** Jiangfei Duan, Runyu Lu, Haojie Duanmu, Xiuhong Li, Xingcheng Zhang, Dahua Lin, Ion Stoica, Hao Zhang. "MuxServe: Flexible Spatial-Temporal Multiplexing for Multiple LLM Serving." ICML 2024, PMLR 235:11905–11917.
**URLs opened.** https://arxiv.org/abs/2404.02015 and https://proceedings.mlr.press/v235/duan24a.html
**Key findings.**
- Colocates LLMs by popularity to share memory, and separates prefill from decode to share compute.
- Achieves up to 1.8× higher throughput, or processes 2.9× more requests while keeping 99% SLO attainment.
**Strengths.** Formulates multi-LLM multiplexing jointly over placement, batching, and resource management.
**Limitations.** Assumes a dedicated LLM serving cluster under its own control rather than general multi-tenant pods.
**Relation to our paper.** Spatial-temporal sharing raises density inside a serving system, whereas our work is about cluster-level request sizing for heterogeneous pods.

### xiang2025aegaeon (existing key)
**Citation.** Yuxing Xiang, Xue Li, Kun Qian, Yufan Yang, Diwen Zhu, Wenyuan Yu, Ennan Zhai, Xuanzhe Liu, Xin Jin, Jingren Zhou. "Aegaeon: Effective GPU Pooling for Concurrent LLM Serving on the Market." ACM SOSP 2025. DOI 10.1145/3731569.3764815.
**URL opened.** https://ennanzhai.github.io/pub/sosp25-aegaeon.pdf (text extracted locally; the ACM DL page returned 403).
**Key findings.**
- In Alibaba Model Studio, more than 90% of models are infrequently invoked. Reserving full GPUs for them allocates 17.7% of GPUs to 1.35% of requests.
- Token-level auto-scaling cuts auto-scaling overhead by 97%. Existing pooling supports at most two or three models per GPU.
- Sustains 2–2.5× higher request rates or 1.5–9× more goodput. In beta deployment it reduces the GPUs needed for tens of models from 1,192 to 213, an 82% saving.
**Strengths.** Large measured production saving from consolidating over-reserved capacity.
**Limitations.** LLM-specific and needs a custom serving engine. Savings are self-reported. (The page range 1030–1045 in the existing bib entry is UNVERIFIED.)
**Relation to our paper.** Evidence from the same company that reserved GPU capacity is massively over-provisioned. Aegaeon reclaims it by rebuilding the serving layer; we evaluate whether reclaiming by right-sizing requests actually yields usable capacity.

### nvidia2026mig (existing key) + li2022miso (NEW)
**Citation (doc).** NVIDIA. "MIG User Guide: Supported MIG Profiles." 2026.
**URL opened.** https://docs.nvidia.com/datacenter/tesla/mig-user-guide/latest/supported-mig-profiles.html
**Citation (paper).** Baolin Li, Tirthak Patel, Siddharth Samsi, Vijay Gadepally, Devesh Tiwari. "MISO: Exploiting Multi-Instance GPU Capability on Multi-Tenant GPU Clusters." ACM SoCC 2022, pp. 173–189. DOI 10.1145/3542929.3563510.
**URL opened.** https://arxiv.org/abs/2207.11428 (venue, pages, and DOI from the search result linking DSpace and Crossref; the arXiv page lists only the DOI).
**Key findings.**
- A100-80GB and H100-80GB have 7 compute slices and 8 memory slices. Profiles run from 1g.10gb (up to 7 instances) through 2g.20gb (3), 3g.40gb (2), and 4g.40gb (1) to 7g.80gb. A 1g.20gb instance takes 2/8 of memory but only 1/7 of SMs, so memory can cap instance count.
- MISO uses cheap MPS profiling to predict the best MIG partition per job, yielding 49% and 16% lower average JCT than unpartitioned and optimal static partitioning, respectively.
**Strengths.** Hardware ground truth for spatial partition granularity, plus a scheduler that reconfigures partitions dynamically.
**Limitations.** MIG profiles are coarse and discrete. MISO evaluates JCT, not the usable residual capacity left after partitioning.
**Relation to our paper.** MIG's quantization (7ths and 8ths) is a hardware analogue of our fractional residue: freed fractions are only reusable if they match an available profile and demand.

```bibtex
@inproceedings{li2022miso,
  author    = {Li, Baolin and Patel, Tirthak and Samsi, Siddharth and Gadepally, Vijay and Tiwari, Devesh},
  title     = {{MISO}: Exploiting Multi-Instance {GPU} Capability on Multi-Tenant {GPU} Clusters},
  booktitle = {ACM Symposium on Cloud Computing (SoCC)},
  year      = {2022},
  pages     = {173--189},
  doi       = {10.1145/3542929.3563510}
}
```

---

## C. Multi-resource fairness and packing

### ghodsi2011drf (NEW)
**Citation.** Ali Ghodsi, Matei Zaharia, Benjamin Hindman, Andy Konwinski, Scott Shenker, Ion Stoica. "Dominant Resource Fairness: Fair Allocation of Multiple Resource Types." USENIX NSDI 2011.
**URLs opened.** https://www.usenix.org/conference/nsdi11/dominant-resource-fairness-fair-allocation-multiple-resource-types and the full paper https://www.usenix.org/legacy/events/nsdi11/tech/full_papers/Ghodsi.pdf (text extracted locally).
**Key findings.**
- DRF equalizes each user's dominant share (their largest share of any resource). It is sharing-incentive, strategy-proof, envy-free, and Pareto-efficient.
- On a 2000-node Facebook Hadoop trace, slot-based schedulers mismatch task demand to fixed slots. DRF reduces completion time of large jobs by up to 66% versus the Hadoop fair scheduler.
- In a Mesos prototype, slot-based scheduling at 3–6 slots per machine either undersubscribes or oversubscribes nodes, so DRF gives higher throughput and lower response times.
**Strengths.** The foundational multi-resource allocation result. It shows that fixed proportional slots waste resources.
**Limitations.** Concerns fairness across users, not packing efficiency or fractional devices, and predates GPUs.
**Relation to our paper.** GPU clusters that tie CPU to GPU in fixed ratios recreate the slot problem DRF identified. Our CPU co-sizing result is the GPU-era version of that lesson.

```bibtex
@inproceedings{ghodsi2011drf,
  author    = {Ghodsi, Ali and Zaharia, Matei and Hindman, Benjamin and Konwinski, Andy and Shenker, Scott and Stoica, Ion},
  title     = {Dominant Resource Fairness: Fair Allocation of Multiple Resource Types},
  booktitle = {USENIX Symposium on Networked Systems Design and Implementation (NSDI)},
  year      = {2011},
  url       = {https://www.usenix.org/conference/nsdi11/dominant-resource-fairness-fair-allocation-multiple-resource-types}
}
```

### grandl2014tetris (NEW)
**Citation.** Robert Grandl, Ganesh Ananthanarayanan, Srikanth Kandula, Sriram Rao, Aditya Akella. "Multi-Resource Packing for Cluster Schedulers" (Tetris). ACM SIGCOMM 2014. DOI 10.1145/2619239.2626334.
**URL opened.** https://home.cse.ust.hk/~weiwa/teaching/Fall15-COMP6611B/reading_list/Tetris.pdf (text extracted locally; the ACM DL page returned 403).
**Key findings.**
- Slot-based, CPU-and-memory-only schedulers cause fragmentation and over-allocation. In Facebook and Bing clusters these delay job completion and increase makespan by over 45%.
- Packs tasks by an **alignment score: the weighted dot product** of task demands and machine availability. This is the origin of the DotProd heuristic in the FGD simulator.
- Trace-driven simulation and a 250-node YARN deployment show gains of over 30% in makespan and job completion time with near-perfect fairness.
**Strengths.** Defines multi-dimensional packing heuristics that later GPU schedulers inherit.
**Limitations.** Designed for data-analytics tasks, with no fractional accelerators. Task demands are taken as given.
**Relation to our paper.** DotProd is one of our five policies. Like the others, it changes usable capacity by under 0.6 points, which suggests that packing heuristics have reached diminishing returns once requests are fixed.

```bibtex
@inproceedings{grandl2014tetris,
  author    = {Grandl, Robert and Ananthanarayanan, Ganesh and Kandula, Srikanth and Rao, Sriram and Akella, Aditya},
  title     = {Multi-Resource Packing for Cluster Schedulers},
  booktitle = {ACM SIGCOMM},
  year      = {2014},
  doi       = {10.1145/2619239.2626334}
}
```

---

## D. CPU-aware DL scheduling

### mohan2022synergy (existing key)
**Citation.** Jayashree Mohan, Amar Phanishayee, Janardhan Kulkarni, Vijay Chidambaram. "Looking Beyond GPUs for DNN Scheduling on Multi-Tenant Clusters" (Synergy). USENIX OSDI 2022, pp. 579–596.
**URL opened.** https://www.usenix.org/conference/osdi22/presentation/mohan
**Key findings.**
- Existing schedulers allocate CPU and memory in proportion to GPU count, which ignores how sensitive each job is to CPU and memory.
- Optimistic profiling estimates that sensitivity, and a near-optimal online algorithm allocates CPU and memory across jobs.
- Workload-aware CPU and memory allocation improves average JCT by up to 3.4× over GPU-proportional allocation.
**Strengths.** Shows directly that fixed GPU:CPU proportionality wastes resources.
**Limitations.** Training-only, optimizes JCT, and does not consider fractional GPUs or serving pods.
**Relation to our paper.** Closest in spirit to our CPU co-sizing. We show that the same insight matters for serving: right-sizing the GPU without the CPU leaves freed GPU capacity unusable (~18-point gain from co-sizing).

### zhao2020coda (existing key)
**Citation.** Han Zhao, Weihao Cui, Quan Chen, Jingwen Leng, Kai Yu, Deze Zeng, Chao Li, Minyi Guo. "CODA: Improving Resource Utilization by Slimming and Co-locating DNN and CPU Jobs." IEEE ICDCS 2020.
**URL opened.** https://www.cs.sjtu.edu.cn/~leng-jw/resources/Files/zhao20icdcs-coda.pdf (text extracted locally).
**Key findings.**
- The number of CPU cores allocated to a training job significantly affects its performance (preprocessing, gradient synchronization).
- Combines an adaptive CPU allocator, a real-time contention eliminator, and a multi-array job scheduler.
- Improves GPU utilization by 20.8% on average without increasing CPU-job queuing time.
**Strengths.** An early characterization of CPU needs per DL model in shared GPU clusters.
**Limitations.** Training-only, small-scale, parameter-server era.
**Relation to our paper.** Supports treating CPU as a first-class co-resource of GPU allocation.

### zhao2022muri (NEW)
**Citation.** Yihao Zhao, Yuanqiang Liu, Yanghua Peng, Yibo Zhu, Xuanzhe Liu, Xin Jin. "Multi-Resource Interleaving for Deep Learning Training" (Muri). ACM SIGCOMM 2022.
**URL opened.** https://xinjin.github.io/files/SIGCOMM22_Muri.pdf (text extracted locally).
**Key findings.**
- Existing DL schedulers allocate only GPUs, but training also uses CPU, storage I/O, and network I/O in stages.
- Interleaves jobs on the same resources in time, using Blossom-based grouping, instead of packing in space.
- On a 64-GPU cluster, improves average JCT by up to 3.6× and makespan by up to 1.6×.
**Strengths.** Exploits the iterative, staged pattern of training for multi-resource packing.
**Limitations.** Depends on training's iteration structure and so does not apply to latency-bound serving. Pages and DOI not verified.
**Relation to our paper.** Another training-side multi-resource scheduler. Our gap is serving pods, where interleaving is not available and request sizing is the main lever.

```bibtex
@inproceedings{zhao2022muri,
  author    = {Zhao, Yihao and Liu, Yuanqiang and Peng, Yanghua and Zhu, Yibo and Liu, Xuanzhe and Jin, Xin},
  title     = {Multi-Resource Interleaving for Deep Learning Training},
  booktitle = {ACM SIGCOMM},
  year      = {2022},
  url       = {https://xinjin.github.io/files/SIGCOMM22_Muri.pdf}
}
```

---

## E. Harvesting idle reserved capacity

### ambati2020harvest (NEW)
**Citation.** Pradeep Ambati, Íñigo Goiri, Felipe Frujeri, Alper Gun, Ke Wang, Brian Dolan, Brian Corell, Sekhar Pasupuleti, Thomas Moscibroda, Sameh Elnikety, Marcus Fontoura, Ricardo Bianchini. "Providing SLOs for Resource-Harvesting VMs in Cloud Platforms." USENIX OSDI 2020.
**URL opened.** https://www.usenix.org/conference/osdi20/presentation/ambati
**Key findings.**
- Unallocated capacity in Azure is abundant but fluctuates over time and across servers.
- Harvest VMs grow and shrink with spare host resources and are evicted only when the minimum is needed. Prediction models support survival SLOs, for example 65% surviving longer than one week.
- Short-term prediction error averages under 2% and longer-term under 6%. With harvested cores, Harvest VMs match regular-VM compute at 91% lower cost.
**Strengths.** A principled, SLO-backed harvesting design proven at cloud scale.
**Limitations.** CPU VMs only. Harvested capacity is assumed fungible (cores), which does not hold for fractional GPUs paired with CPU.
**Relation to our paper.** The CPU-cloud precedent for SpotGPU. Our results show that GPU harvesting faces a shape-matching problem (fractional residue plus co-located CPU) that the fungible-cores model hides.

```bibtex
@inproceedings{ambati2020harvest,
  author    = {Ambati, Pradeep and Goiri, {\'I}{\~n}igo and Frujeri, Felipe and Gun, Alper and Wang, Ke and Dolan, Brian and Corell, Brian and Pasupuleti, Sekhar and Moscibroda, Thomas and Elnikety, Sameh and Fontoura, Marcus and Bianchini, Ricardo},
  title     = {Providing {SLOs} for Resource-Harvesting {VMs} in Cloud Platforms},
  booktitle = {USENIX Symposium on Operating Systems Design and Implementation (OSDI)},
  year      = {2020},
  url       = {https://www.usenix.org/conference/osdi20/presentation/ambati}
}
```

(SpotGPU is covered under li2026asi above.)

---

## F. Briefer supporting sources

### xu2022igniter (existing key; venue now verified)
Fei Xu, Jianian Xu, Jiabin Chen, Li Chen, Ruitao Shang, Zhi Zhou, Fangming Liu. "iGniter: Interference-Aware GPU Resource Provisioning for Predictable DNN Inference in the Cloud." IEEE TPDS vol. 34, no. 3, pp. 812–827 (OpenAlex lists publication date 2022-12-28). DOI 10.1109/TPDS.2022.3232715.
**URLs opened.** https://arxiv.org/abs/2211.01713 and https://api.openalex.org/works/doi:10.1109/TPDS.2022.3232715
**Findings.** An empirical study on EC2 shows significant interference among co-located inference workloads. A lightweight performance model plus joint GPU-allocation and batching provisioning meets SLOs and cuts cost by up to 25% versus state-of-the-art strategies (Triton prototype, four DNNs).
**Strength / limitation.** Sizes GPU shares explicitly for inference, but is small-scale and GPU-only.
**Relation.** Supports sizing to need. Note: the existing entry is `@misc`, and could become `@article{..., journal={IEEE Transactions on Parallel and Distributed Systems}, volume={34}, number={3}, pages={812--827}, doi={10.1109/TPDS.2022.3232715}}`. The print year (2022 vs 2023) is UNVERIFIED; OpenAlex says 2022.

### narayanan2020gavel (existing key)
Deepak Narayanan, Keshav Santhanam, Fiodar Kazhamiaka, Amar Phanishayee, Matei Zaharia. "Heterogeneity-Aware Cluster Scheduling Policies for Deep Learning Workloads." USENIX OSDI 2020, pp. 481–498.
**URL opened.** https://www.usenix.org/conference/osdi20/presentation/narayanan-deepak
**Findings.** Expresses scheduling policies as optimization problems over "effective throughput" across accelerator types, with round-based scheduling. Improves makespan and average JCT by 1.4× and 3.5× over heterogeneity-agnostic policies.
**Relation.** Heterogeneity-aware placement still takes requests as given. It is relevant to "cluster shift" across GPU generations.

### yeo2024preba (NEW; arXiv preprint, not peer-reviewed as far as verified)
Gwangoo Yeo, Jiin Kim, Yujeong Choi, Minsoo Rhu. "PREBA: A Hardware/Software Co-Design for Multi-Instance GPU based AI Inference Servers." arXiv:2411.19114, 2024.
**URL opened.** https://arxiv.org/abs/2411.19114
**Findings.** Evaluating MIG for inference servers, the authors find that CPU-side data preprocessing becomes a major bottleneck once a GPU is split into slices. An FPGA preprocessing accelerator plus dynamic batching gives 3.7× throughput, a 3.4× tail-latency reduction, 3.5× energy efficiency, and 3.0× cost efficiency.
**Relation.** Device-level evidence that slicing a GPU shifts the bottleneck to host CPU, which matches our finding at cluster level. Peer-reviewed venue UNVERIFIED.

```bibtex
@misc{yeo2024preba,
  author       = {Yeo, Gwangoo and Kim, Jiin and Choi, Yujeong and Rhu, Minsoo},
  title        = {{PREBA}: A Hardware/Software Co-Design for Multi-Instance {GPU} based {AI} Inference Servers},
  year         = {2024},
  howpublished = {arXiv:2411.19114}
}
```

### qiao2025conserve (NEW; venue UNVERIFIED)
Yifan Qiao, Shu Anzai, Shan Yu, Haoran Ma, Shuo Yang, Yang Wang, Miryung Kim, Yongji Wu, Yang Zhou, Jiarong Xing, Joseph E. Gonzalez, Ion Stoica, Harry Xu. "ConServe: Fine-Grained GPU Harvesting for LLM Online and Offline Co-Serving." arXiv:2410.01228 (v2, Sept 2025).
**URL opened.** https://arxiv.org/abs/2410.01228v2
**Findings.** Token-level scheduling, layer-wise preemption, and incremental KV-cache management let offline LLM jobs harvest idle GPU time behind online serving. Averages 2.2× higher throughput and 2.9× lower online tail latency than state-of-the-art systems.
**Relation.** Intra-GPU harvesting for LLMs. A search result says an ICML 2026 version exists; this is UNVERIFIED (page not opened).

```bibtex
@misc{qiao2025conserve,
  author       = {Qiao, Yifan and Anzai, Shu and Yu, Shan and Ma, Haoran and Yang, Shuo and Wang, Yang and Kim, Miryung and Wu, Yongji and Zhou, Yang and Xing, Jiarong and Gonzalez, Joseph E. and Stoica, Ion and Xu, Harry},
  title        = {{ConServe}: Fine-Grained {GPU} Harvesting for {LLM} Online and Offline Co-Serving},
  year         = {2025},
  howpublished = {arXiv:2410.01228}
}
```

### Not covered (not opened; no claims made)
Sia (SOSP'23) and Lucid (ASPLOS'23) are heterogeneity- and interpretability-aware training schedulers named in the brief. Their pages were not opened, so no claims are made about them. If cited, they belong with Gavel as further evidence that placement work holds requests fixed.

---

## Cross-cutting pattern and the gap our paper fills

Across three decades of work, from DRF and Tetris through Gandiva, AntMan, and FGD, the lever has been **how to place or multiplex a fixed set of requests**: fair shares across resource types, dot-product packing, time-slicing, operator-level co-scheduling, and fragmentation gradients. Device-level sharing systems (Salus, REEF, Orion, USHER, MuxServe, Aegaeon, MIG/MISO) show that individual GPUs are badly underused. Harvesting systems (Harvest VMs, SpotGPU, ConServe) show that reserved-but-idle capacity is large: ASI's Standby hours reach 10,000 GPU hours at peak, and Aegaeon reports an 82% GPU saving. Two blind spots recur.

1. **Placement work takes pod requests as given.** FGD and Tetris-style heuristics optimize where a request lands, never whether the request is the right size. Our simulator results show that the placement policies differ by under 0.6 points of usable capacity, while sizing requests to need adds 8–10 points and co-sizing CPU adds about 18.
2. **CPU-aware scheduling (Synergy, CODA, Muri) targets training JCT**, and harvesting work measures allocation ratio or throughput rather than whether a freed slice can host a real pod shape. Prism and PREBA hint that CPU, not GPU, binds for serving, but they answer with hardware disaggregation or accelerators.

Our paper sits at this intersection. On the ASI trace, where fractional fragmentation is currently negligible only because sharing is rare, we evaluate what right-sizing actually returns. We find that **reclaimable is not reusable**: freed GPU slices are blocked by fractional residue and by insufficient CPU on the same server. The benefit comes from co-sizing requests across GPU and CPU, not from a better placement heuristic.
