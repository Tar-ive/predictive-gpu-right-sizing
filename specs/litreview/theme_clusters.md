# Theme: Characterization studies of production GPU clusters

Annotated bibliography for "Reclaimable Is Not Reusable: Evaluating GPU Right-Sizing Under Cluster Shift".

How this was verified: every number below was read from the paper's full text (PDF downloaded from the URL listed and extracted with `pdftotext`) or from the official abstract page. A claim is marked UNVERIFIED wherever that was not possible. Existing refs.bib keys are reused where they match. BibTeX is given only for new keys.

Note on metrics: these studies use "utilization" in at least three different senses: (a) the **allocation ratio** (allocated GPUs / total GPUs), (b) **NVML "GPU utilization"** (the share of time a kernel is running), and (c) **SM activity/occupancy** (DCGM). The literature review should keep them apart. For example, Helios's "cluster utilization" is (a), while Philly's 52% is (b).

---

## 1. `jeon2019philly`: Microsoft Philly (ATC '19)

**Citation.** Myeongjae Jeon, Shivaram Venkataraman, Amar Phanishayee, Junjie Qian, Wencong Xiao, Fan Yang. "Analysis of Large-Scale Multi-Tenant GPU Clusters for DNN Training Workloads." USENIX ATC 2019.

**URL opened.** https://www.usenix.org/conference/atc19/presentation/jeon (and the PDF https://www.usenix.org/system/files/atc19-jeon.pdf)

**Key findings.**
- The study covers two months and about 100,000 jobs from hundreds of users. It joins YARN scheduler logs with Ganglia utilization data and per-job logs (Sec. 1).
- High allocation hides low use. "Most GPUs within a cluster are allocated", yet the hardware utilization of in-use GPUs averages only **about 52%**. Around **47.7% of in-use GPU cycles are wasted**, and 16-GPU jobs are lowest at **40.39%** mean (Sec. 1, Sec. 3.2, Table 3).
- Locality and interference matter. 8-GPU jobs average **56.9%** utilization against **34.3%** for 16-GPU jobs. A 16-GPU job spread over 8 servers averages **28.56%** (Table 5). Fragmentation accounts for **74.2%** of queueing-delay occurrences (Table 2).
- **30.7%** of jobs end killed or unsuccessful, and they use about **55%** of the GPU time (Table 6). The paper also notes that "many servers underutilize CPU cycles yet highly utilize memory", with CPU/memory allocated in proportion to GPUs (Sec. 3.3, Fig. 7).

**Strengths.** This was the first large public production DL trace. It separates allocation from actual use and ties low utilization to placement.

**Limitations.** Training only. One operator. P100/2017-era hardware. Whole-GPU allocation only. Host CPU is analysed only coarsely, as server-level CDFs.

**Relation to our paper.** Philly is the origin of the "allocated is not utilized" observation that motivates right-sizing. It has no inference or fractional-GPU data, so it cannot address whether freed capacity can be reused.

---

## 2. `hu2021helios`: SenseTime Helios (SC '21)

**Citation.** Qinghao Hu, Peng Sun, Shengen Yan, Yonggang Wen, Tianwei Zhang. "Characterization and Prediction of Deep Learning Workloads in Large-Scale GPU Datacenters." SC 2021 (arXiv:2109.01313).

**URL opened.** https://arxiv.org/abs/2109.01313 (and the PDF)

**Key findings.**
- The trace covers four clusters (Venus, Earth, Saturn, Uranus) with **6,416 GPUs** and **3.36 million jobs** on 802 nodes, from April to September 2020 (Sec. 2, Table 1).
- "Cluster utilization", defined as the ratio of active GPUs to total GPUs, averages **65% to 90%** across clusters. Some virtual clusters are underutilized all the time (Sec. 3.1, Sec. 5).
- More than 50% of GPU jobs are single-GPU, but they contribute **less than 6%** of cluster utilization, except on Earth. Over one-third of GPU time went to failed jobs in Philly, against **9.3%** in Helios (Sec. 3).
- History-based prediction works. The QSSF scheduler cuts average JCT by up to **6.5x**. The Cluster Energy Saving service powers down idle nodes and lifts node utilization from **69% to 90%** on one cluster, and by up to **13%** overall (Abstract, Table 5).

**Strengths.** Multi-cluster scale. The paper shows that job-history features predict resource behaviour, which is a precedent for history-based prediction.

**Limitations.** Training/research only, with no inference. One operator. The utilization metric is allocation-based, not SM-level. There is no per-job CPU usage analysis.

**Relation to our paper.** Helios supports our finding that simple history-based predictors are effective. Its idle-node reclamation is node-granular, whereas our question is whether sub-GPU slack becomes whole, CPU-backed GPUs.

---

## 3. `weng2022mlaas`: Alibaba PAI, "MLaaS in the Wild" (NSDI '22)

**Citation.** Qizhen Weng, Wencong Xiao, Yinghao Yu, Wei Wang, Cheng Wang, Jian He, Yong Li, Liping Zhang, Wei Lin, Yu Ding. "MLaaS in the Wild: Workload Analysis and Scheduling in Large-Scale Heterogeneous GPU Clusters." USENIX NSDI 2022.

**URL opened.** https://www.usenix.org/conference/nsdi22/presentation/weng (and the PDF https://www.usenix.org/system/files/nsdi22-paper-weng.pdf)

**Key findings.**
- A two-month trace (July to August 2020) from a cluster of more than 6,000 heterogeneous GPUs, mixing training and inference (Abstract, Sec. 1).
- Over-reservation is severe. The median instance **requests** 6 vCPU, **0.5 GPU** and 29 GiB, but **uses** 1.4 vCPU, **0.042 GPU** and 3.5 GiB. About **18%** of instances barely use the GPU (Sec. 3.3).
- GPU sharing packs low-GPU work so that **only 50% of requested GPUs** are needed on average. Heavy utilization (95% or more) appears in only **7%** of samples (Sec. 5.1, Fig. 9).
- CPU is a bottleneck. Tasks that slow down sit on machines with higher CPU utilization. On T4 machines, slowed tasks average **33.5%** P75 CPU utilization, "noticeably higher" than the comparison group. On 8-GPU machines, workloads demand **1.9x more CPUs per GPU** than the machines provide (12 CPU/GPU). Low-end GPU machines have **over 70%** of CPU/GPU allocated, against **35% CPU / 49% GPU** on high-end machines (Sec. 1).

**Strengths.** This is the closest prior work. It covers fractional-GPU requests, inference, request-vs-usage gaps, and explicitly flags CPU as a bottleneck.

**Limitations.** One operator. 2020 hardware (T4/P100/V100). Pre-LLM. The CPU-mismatch numbers are cluster averages, not tied to whether reclaimed GPU slack is usable. It has no cross-cluster evaluation of predictors.

**Relation to our paper.** PAI established both the GPU over-request and the CPU-per-GPU mismatch. We take these from description to consequence: we measure how much predicted GPU slack survives CPU and packing constraints (3.8%).

---

## 4. `li2026asi`: Alibaba ASI (OSDI '26), the trace we use

**Citation.** Suyi Li, Lingyun Yang, Haoxuan Yu, Sheng Yao, Tianyuan Wu, Xiaoxiao Jiang, Hanfeng Lu, Kangjin Wang, Chenhao Wang, Shenglin Xu, Lun Wang, Qingyang Duan, Shenghao Liang, Xiu Lin, Meng Zhang, Wenchao Wu, Yinghao Yu, Guodong Yang, Liping Zhang, Wei Wang. "Heterogeneity at Hyperscale: Characterization and Scheduling of Large Production AI Clusters at Alibaba." USENIX OSDI 2026, pp. 2187–2203.

**URL opened.** https://www.usenix.org/conference/osdi26/presentation/li-suyi (and the PDF https://www.usenix.org/system/files/osdi26-li-suyi.pdf)

**Key findings.**
- A six-month trace of **155,410 GPUs** across vendors and generations, with jobs from 81 departments. Online inference is **over 50%** of the workload, and classical DNNs (CTR/rec/OCR) still account for about **70% of online-inference GPU hours** (Abstract, Sec. 1–3).
- "High GPU demand does not yield high effective utilization." Online inference has a **median GPU SM utilization of only 6%**. In online serving, Qwen's median SM utilization of 26% is 2.7x CTR's and 9.6x BERT's. CTR, BERT and Qwen request median **24, 8 and 4 CPU cores** respectively (Sec. 1, Sec. 3.4).
- Unallocatable idle GPUs come from stranding, **insufficient CPUs**, and topology. **Fractional-GPU fragmentation is negligible because GPU sharing is rarely used.** For high CPU/GPU-ratio requests (e.g., 1G8C, 8G128C), "Insufficient CPU" is the dominant reason idle GPUs cannot be allocated (Fig. 13, Sec. 4.1).
- Defensive reservation for diurnal peaks, failover and peak events means idle standby capacity peaks at about **10,000 GPU hours around midnight**. SpotGPU raises the GPU allocation ratio from **68% to 93%**, and IPC defragmentation cuts nodes with slack by **20.2%** (Sec. 1, Sec. 4.2).

**Strengths.** The most recent and largest trace. It covers heterogeneous hardware, priorities and request/usage metadata. It is the only study that explicitly attributes unallocatable GPUs to CPU shortage.

**Limitations.** One operator. It characterizes and reclaims at job granularity (Standby/SpotGPU) and does not evaluate per-pod right-sizing predictors or their transfer across clusters. CPU appears as an allocation constraint, not as part of a reuse metric.

**Relation to our paper.** This is our data source. Our "CPU is the binding constraint" result is consistent with ASI's Fig. 13 diagnosis and extends it to the question of whether predicted GPU savings become usable whole GPUs.

---

## 5. `gao2024lowutil`: Low GPU Utilization of DL Jobs (ICSE '24)

**Citation.** Yanjie Gao, Yichen He, Xinze Li, Bo Zhao, Haoxiang Lin, Yoyo Liang, Jing Zhong, Hongyu Zhang, Jingzhou Wang, Yonghua Zeng, Keli Gui, Jie Tong, Mao Yang. "An Empirical Study on Low GPU Utilization of Deep Learning Jobs." ICSE 2024. DOI 10.1145/3597503.3639232.

**URL opened.** https://www.microsoft.com/en-us/research/uploads/prodnew/2024/01/gpu-util-icse2024.pdf (the ACM DL page returned 403)

**Key findings.**
- A manual study of **400** randomly sampled jobs from Microsoft's internal platform ("Platform-X") whose average GPU utilization was **50% or less** (Sec. 1, Sec. 3).
- It identifies **706** low-utilization issues. **46.03%** come from data operations and **45.18%** from model-related causes (Table 1).
- **84.99%** of the issues could be fixed with small code or script changes (Abstract).

**Strengths.** Root-cause depth that trace studies lack. It shows that much low utilization comes from the job (CPU-side data work, small batches), not the scheduler.

**Limitations.** Training/evaluation jobs only. A selected sample of low-utilization jobs, so it gives no fleet-wide rate. One operator. No placement or reservation analysis.

**Relation to our paper.** It helps explain why GPU slack exists, partly because work is CPU/data-bound. That supports our point that CPU, not GPU, limits reuse.

---

## 6. `hu2024acme` (NEW): Shanghai AI Lab Acme, LLM development (NSDI '24)

**Citation.** Qinghao Hu, Zhisheng Ye, Zerui Wang, Guoteng Wang, Meng Zhang, Qiaoling Chen, Peng Sun, Dahua Lin, Xiaolin Wang, Yingwei Luo, Yonggang Wen, Tianwei Zhang. "Characterization of Large Language Model Development in the Datacenter." USENIX NSDI 2024.

**URL opened.** https://www.usenix.org/conference/nsdi24/presentation/hu (and the PDF https://www.usenix.org/system/files/nsdi24-hu.pdf)

**Key findings.**
- Two clusters (Seren, Kalos) with **4,704 A100 GPUs**, traced from March to August 2023 (Sec. 1).
- GPU utilization is polarized at 0% and 100%. The medians are **97% (Seren) and 99% (Kalos)**, against **48% (Philly) and 4% (PAI)**. Median SM activity is about **40%**, twice PAI's reported 20% (Sec. 3.1, Sec. 3.3).
- Pretraining is **3.2%** of jobs but **94.0%** of GPU time in Kalos. Evaluation is **92.9%** of jobs but **0.8%** of resources (Sec. 1, Sec. 3.2).
- Associated resources sit idle. CPU memory utilization stays below 50%, CPUs are typically underutilized, and NICs are idle more than 60% of the time. About **30% of GPUs are idle** yet still draw 60 W (Sec. 3.3–3.4).

**Strengths.** A modern LLM-era contrast. It shows that utilization depends heavily on workload class, and gives a direct side-by-side with Philly and PAI.

**Limitations.** Training/evaluation for LLM development only, with no online serving. One lab. Homogeneous A100s.

**Relation to our paper.** It is evidence that low utilization is specific to inference and small models, not universal. Training clusters run hot, so right-sizing targets online inference, which is our focus.

```bibtex
@inproceedings{hu2024acme,
  author    = {Hu, Qinghao and Ye, Zhisheng and Wang, Zerui and Wang, Guoteng and Zhang, Meng and Chen, Qiaoling and Sun, Peng and Lin, Dahua and Wang, Xiaolin and Luo, Yingwei and Wen, Yonggang and Zhang, Tianwei},
  title     = {Characterization of Large Language Model Development in the Datacenter},
  booktitle = {USENIX Symposium on Networked Systems Design and Implementation (NSDI)},
  year      = {2024},
  url       = {https://www.usenix.org/conference/nsdi24/presentation/hu}
}
```

---

## 7. `shukla2022singularity`: Microsoft Singularity (arXiv 2022)

**Citation.** Dharma Shukla, Muthian Sivathanu, Srinidhi Viswanatha, Bhargav Gulavani, Rimma Nehme, Amey Agrawal, Chen Chen, Nipun Kwatra, Ramachandran Ramjee, Pankaj Sharma, Atul Katiyar, Vipul Modi, Vaibhav Sharma, Abhishek Singh, Shreshth Singhal, Kaustubh Welankar, Lu Xun, Ravi Anupindi, Karthik Elangovan, Hasibur Rahman, Zhou Lin, Rahul Seetharaman, Cheng Xu, Eddie Ailijiang, Suresh Krishnappa, Mark Russinovich. "Singularity: Planet-Scale, Preemptive and Elastic Scheduling of AI Workloads." arXiv:2202.07848, 2022.

**URL opened.** https://arxiv.org/abs/2202.07848 (and the PDF)

**Key findings.**
- Designed for "a global fleet of hundreds of thousands of GPUs and other AI accelerators" for both training and inference (Sec. 1).
- Its first design principle is "No idling of resources": avoid "any resource fragmentation or static reservation of capacity" by using spare capacity across cluster, region and training/inference boundaries (Sec. 1.1).
- It handles inference load spikes by shrinking or preempting training jobs through transparent checkpoint/migration (Sec. 1.1). No fleet-level utilization numbers are reported (no quantitative characterization).

**Strengths.** An operator-scale statement that static reservation is the main source of waste, with a mechanism (elasticity/preemption) to reclaim it.

**Limitations.** A systems design paper, not a characterization. A non-peer-reviewed preprint. No published utilization or reservation numbers.

**Relation to our paper.** It is the "reclaim by preemption" alternative to right-sizing. Like ASI's SpotGPU, it operates at job granularity, which suggests reclaiming whole jobs is easier than reusing sub-GPU slack.

---

## 8. `patel2024splitwise` (NEW): Splitwise, Azure LLM inference (ISCA '24)

**Citation.** Pratyush Patel, Esha Choukse, Chaojie Zhang, Aashaka Shah, Íñigo Goiri, Saeed Maleki, Ricardo Bianchini. "Splitwise: Efficient Generative LLM Inference Using Phase Splitting." ISCA 2024 (arXiv:2311.18677).

**URL opened.** https://arxiv.org/abs/2311.18677 (and the PDF). Venue confirmed at https://www.microsoft.com/en-us/research/publication/splitwise-efficient-generative-llm-inference-using-phase-splitting/

**Key findings.**
- Characterizes two production Azure LLM services (coding, conversation) using 20-minute traces from Nov 11, 2023, released in AzurePublicDataset (Sec. III).
- Median prompt/output lengths are **1500/13 tokens for coding** and **1020/129 tokens for conversation** (Sec. III, Fig. 3).
- The token-generation phase is memory-bound and underutilizes compute, and its power draw does not grow with batch size. The token phase sees almost no latency impact under power caps (Insights V–VII).
- Splitting the phases yields **1.4x throughput at 20% lower cost**, or **2.35x throughput** at the same cost and power (Abstract).

**Strengths.** Production inference traces from a major cloud. Explains *why* inference GPUs are compute-idle even when memory-full.

**Limitations.** Request-level traces only, with no cluster allocation, reservation or CPU data. Short windows. One operator. LLM-only.

**Relation to our paper.** The mechanism matches ASI's observation that GenAI serving fills memory but leaves compute idle. This means SM utilization alone understates how much of a GPU an inference pod needs, which is why our right-sizing target is a "safe" slice.

```bibtex
@inproceedings{patel2024splitwise,
  author    = {Patel, Pratyush and Choukse, Esha and Zhang, Chaojie and Shah, Aashaka and Goiri, {\'I}{\~n}igo and Maleki, Saeed and Bianchini, Ricardo},
  title     = {Splitwise: Efficient Generative {LLM} Inference Using Phase Splitting},
  booktitle = {ACM/IEEE International Symposium on Computer Architecture (ISCA)},
  year      = {2024},
  url       = {https://arxiv.org/abs/2311.18677}
}
```

---

## 9. `stojkovic2025dynamollm` (NEW): DynamoLLM, Azure LLM inference load (HPCA '25)

**Citation.** Jovan Stojkovic, Chaojie Zhang, Íñigo Goiri, Josep Torrellas, Esha Choukse. "DynamoLLM: Designing LLM Inference Clusters for Performance and Energy Efficiency." HPCA 2025 (arXiv:2408.00741; DOI 10.1109/HPCA61900.2025.00102 as listed on arXiv).

**URL opened.** https://arxiv.org/abs/2408.00741 (and the PDF)

**Key findings.**
- Uses week-long Azure Coding and Conversation traces. Peak load is **1.7x average and 3.3x valley** for Conversation, and **2.8x average and 34.6x valley** for Coding (Sec. II, Fig. 2).
- Conventional deployments "provision the static number of instances to handle their peak load resulting in heavy underutilization", because scale-out costs minutes (Sec. II).
- Dynamic reconfiguration of instance count, parallelism and frequency saves **53% energy**, **38% operational carbon** and **61% customer cost** while meeting SLOs (Abstract).

**Strengths.** Quantifies the diurnal peak-to-valley gap that drives inference over-provisioning.

**Limitations.** Load traces only, no allocation/CPU data. One operator. LLM-only. The evaluation is on a small testbed with an open-source model.

**Relation to our paper.** It gives an independent measurement of the peak-provisioning behaviour that ASI blames for idle standby capacity. It also explains why a per-workload history rule (peak-aware) is a natural safe-slice predictor.

```bibtex
@inproceedings{stojkovic2025dynamollm,
  author    = {Stojkovic, Jovan and Zhang, Chaojie and Goiri, {\'I}{\~n}igo and Torrellas, Josep and Choukse, Esha},
  title     = {{DynamoLLM}: Designing {LLM} Inference Clusters for Performance and Energy Efficiency},
  booktitle = {IEEE International Symposium on High-Performance Computer Architecture (HPCA)},
  year      = {2025},
  doi       = {10.1109/HPCA61900.2025.00102},
  url       = {https://arxiv.org/abs/2408.00741}
}
```

---

## 10. `xiang2025aegaeon` (NEW): Alibaba Aegaeon, model-market inference (SOSP '25)

**Citation.** Yuxing Xiang, Xue Li, Kun Qian, Yufan Yang, Diwen Zhu, Wenyuan Yu, Ennan Zhai, Xuanzhe Liu, Xin Jin, Jingren Zhou. "Aegaeon: Effective GPU Pooling for Concurrent LLM Serving on the Market." ACM SOSP 2025. DOI 10.1145/3731569.3764815.

**URL opened.** https://ennanzhai.github.io/pub/sosp25-aegaeon.pdf (author-hosted copy)

**Key findings.**
- In Alibaba Cloud Model Studio, **94.1% of 779 models** receive only **1.35% of 167.6M requests**. Yet reserving dedicated instances for them takes **17.7% of about 30K GPUs**, at under 0.2 requests per second per GPU (Sec. 1, Fig. 1).
- Before pooling, single-instance GPU utilization averaged **13.3% to 33.9%**. After token-level pooling it reached **48.1%** over a 70-hour window (Sec. 7, Fig. 18).
- The deployment reduced the H20 GPUs needed for its model set from **1,192 to 213 (82%)** (Abstract, Sec. 7).

**Strengths.** Recent production evidence from Alibaba that dedicated reservation for inference wastes a large share of the fleet.

**Limitations.** LLM serving only. A system paper with motivating characterization, not a full trace study. One operator. No CPU analysis.

**Relation to our paper.** It is complementary. Aegaeon reclaims waste through software multiplexing within a pool, while we ask whether right-sized slack in a general cluster becomes reusable hardware. Both find reservation, not demand, to be the source of waste.

```bibtex
@inproceedings{xiang2025aegaeon,
  author    = {Xiang, Yuxing and Li, Xue and Qian, Kun and Yang, Yufan and Zhu, Diwen and Yu, Wenyuan and Zhai, Ennan and Liu, Xuanzhe and Jin, Xin and Zhou, Jingren},
  title     = {Aegaeon: Effective {GPU} Pooling for Concurrent {LLM} Serving on the Market},
  booktitle = {ACM Symposium on Operating Systems Principles (SOSP)},
  year      = {2025},
  doi       = {10.1145/3731569.3764815}
}
```

---

## 11. `wang2024burstgpt` (NEW, preprint): BurstGPT, Azure OpenAI serving workload

**Citation.** Yuxin Wang, Yuhan Chen, Zeyu Li, Xueze Kang, Yuchu Fang, Yeju Zhou, Yang Zheng, Zhenheng Tang, Xin He, Rui Guo, Xin Wang, Qiang Wang, Amelie Chi Zhou, Xiaowen Chu. "BurstGPT: A Real-world Workload Dataset to Optimize LLM Serving Systems." arXiv:2401.17644 (v5, 2025).

**URL opened.** https://arxiv.org/abs/2401.17644 (abstract page only)

**Key findings.**
- **10.31 million** request traces from regional Azure OpenAI GPT services over **213 days** (Abstract).
- Burstiness and concurrency vary widely across services and models. Failures in conversation and API services point to high resource demand and limited availability (Abstract).
- A peer-reviewed venue is UNVERIFIED (the arXiv page lists none). Full-text numbers were not checked.

**Strengths.** The longest public LLM-serving request trace.

**Limitations.** Request-level only, with no GPU utilization or allocation data. Preprint status.

**Relation to our paper.** Supporting evidence that inference demand is bursty, which explains why operators reserve headroom and why a "safe" slice needs tail-aware prediction.

```bibtex
@misc{wang2024burstgpt,
  author       = {Wang, Yuxin and Chen, Yuhan and Li, Zeyu and Kang, Xueze and Fang, Yuchu and Zhou, Yeju and Zheng, Yang and Tang, Zhenheng and He, Xin and Guo, Rui and Wang, Xin and Wang, Qiang and Zhou, Amelie Chi and Chu, Xiaowen},
  title        = {{BurstGPT}: A Real-world Workload Dataset to Optimize {LLM} Serving Systems},
  year         = {2024},
  howpublished = {arXiv:2401.17644},
  url          = {https://arxiv.org/abs/2401.17644}
}
```

---

## 12. (Optional) `wongpanich2025mpg` (NEW, preprint): Google TPU fleet efficiency

**Citation.** Arissa Wongpanich, Tayo Oguntebi, Jose Baiocchi Paredes, Yu Emma Wang, Phitchaya Mangpo Phothilimthana, Ritwika Mitra, Zongwei Zhou, Naveen Kumar, Vijay Janapa Reddi. "Machine Learning Fleet Efficiency: Analyzing and Optimizing Large-Scale Google TPU Systems with ML Productivity Goodput." arXiv:2502.06982, 2025.

**URL opened.** https://arxiv.org/abs/2502.06982 (abstract page only)

**Key findings.**
- Argues that "traditional utilization-based metrics are insufficient" for ML fleets of thousands of accelerators, and proposes ML Productivity Goodput (MPG) (Abstract).
- No quantitative utilization figures were verified (full text not read). Inference vs. training breakdown UNVERIFIED.

**Strengths / limitations.** The only Google fleet view found, but it is a TPU-only preprint with no verified numbers.

**Relation to our paper.** Supports our framing that raw utilization or reclaimed capacity is the wrong metric, and that *usable* capacity (our reusable-GPU metric) is what matters.

```bibtex
@misc{wongpanich2025mpg,
  author       = {Wongpanich, Arissa and Oguntebi, Tayo and Baiocchi Paredes, Jose and Wang, Yu Emma and Phothilimthana, Phitchaya Mangpo and Mitra, Ritwika and Zhou, Zongwei and Kumar, Naveen and Janapa Reddi, Vijay},
  title        = {Machine Learning Fleet Efficiency: Analyzing and Optimizing Large-Scale {Google} {TPU} Systems with {ML} Productivity Goodput},
  year         = {2025},
  howpublished = {arXiv:2502.06982},
  url          = {https://arxiv.org/abs/2502.06982}
}
```

---

## Not found / not included
- **Meta GPU inference-fleet characterization:** no peer-reviewed Meta study with GPU inference utilization numbers was located and verified in this pass (UNVERIFIED / omitted).

## Cross-cutting pattern and the gap

Across seven years and three operators, the same pattern recurs: **allocation is high but effective use is low, and the shortfall comes from reservation rather than demand.**
- Philly: about 52% utilization of in-use GPUs despite most GPUs being allocated.
- PAI: a median request of 0.5 GPU against median use of 0.042 GPU.
- ASI: 6% median SM utilization for online inference, and about 10,000 idle standby GPU-hours at night.
- Aegaeon: 17.7% of GPUs serving 1.35% of requests.
- Azure (DynamoLLM): peak-provisioned instances with peak-to-valley ratios up to 34.6x.
- Contrast: LLM *training* clusters (Acme) run near 100%, so the waste concentrates in inference.

Two of these studies (PAI and ASI) separately note that **CPU** can block allocation of idle GPUs. Every study, however, stops at one of three points: characterizing the waste, reclaiming it at job granularity (Singularity, SpotGPU, Helios CES), or multiplexing within a dedicated serving pool (Aegaeon, Splitwise). None asks the downstream question our paper addresses. If a predictor right-sizes each inference pod to its smallest safe slice, and that predictor must transfer to clusters it was not trained on, how much of the "reclaimable" GPU capacity actually becomes **reusable** whole GPUs with enough co-located CPU? Our answer is 3.8%, and the binding constraint is CPU rather than GPU prediction accuracy or placement policy. That turns the scattered CPU-bottleneck observations of PAI and ASI into a measured limit on the value of GPU right-sizing.
