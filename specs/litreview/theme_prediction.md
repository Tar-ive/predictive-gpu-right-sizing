# Theme: Workload/Resource Prediction, Right-Sizing and Autoscaling

Annotated bibliography for "Reclaimable Is Not Reusable: Evaluating GPU Right-Sizing Under Cluster Shift".
Every number below was read on the page/PDF listed under "URL opened". Items marked UNVERIFIED could not be confirmed from a primary page.

---

## A. CPU/memory right-sizing and prediction in clouds

### 1. `rzadca2020autopilot` (existing key)
**Citation:** K. Rzadca, P. Findeisen, J. Swiderski, P. Zych, P. Broniek, J. Kusmierek, P. Nowak, B. Strack, P. Witusowski, S. Hand, J. Wilkes. "Autopilot: Workload Autoscaling at Google Scale." EuroSys 2020.
**URL opened:** https://research.google/pubs/autopilot-workload-autoscaling-at-google-scale/ (abstract page; ACM full text returned 403)
**Key findings:**
- Autopiloted jobs run with 23% slack vs 46% for manually managed jobs.
- Number of jobs severely impacted by OOM reduced by a factor of 10.
- Autopiloted jobs account for over 48% of Google's fleet-wide resource usage.
**Strength:** Largest production evidence that automatic, history-driven vertical sizing beats human-set limits.
**Limitation:** Evaluated inside one operator's fleet; no cross-cluster or cross-operator transfer test; internal recommender details not verified here (full text inaccessible).
**Relation to us:** The canonical "per-job history sizes limits" result for CPU/memory; our P90-of-past-need rule is the GPU-slice analogue, and we ask whether such sizing transfers to unseen clusters and whether freed capacity is actually reusable.

### 2. `cortez2017resource` (existing key)
**Citation:** E. Cortez, A. Bonde, A. Muzio, M. Russinovich, M. Fontoura, R. Bianchini. "Resource Central: Understanding and Predicting Workloads for Improved Resource Management in Large Cloud Platforms." SOSP 2017, pp. 153-167. doi:10.1145/3132747.3132772
**URL opened:** https://www.microsoft.com/en-us/research/publication/resource-central-understanding-predicting-workloads-improved-resource-management-large-cloud-platforms/ and the PDF https://www.microsoft.com/en-us/research/wp-content/uploads/2017/10/Resource-Central-SOSP17.pdf
**Key findings:**
- Core observation: many VM behaviours are consistent across lifetimes, i.e., "history is an accurate predictor of future behavior."
- Bucketed predictions of six metrics reach 79% (lifetime) to 90% (workload class) accuracy; average CPU utilisation of a new VM predicted with 81% accuracy.
- Dropping low-confidence predictions (score < 0.6) raises precision to 85-94%, with recall 73-98%; the most important features are the subscription's history of bucket assignments.
- Case study: Azure VM scheduler oversubscribes servers using predicted 95th-percentile CPU utilisation.
**Strength:** Shows simple per-subscription history features dominate, and pairs prediction with a downstream scheduler.
**Limitation:** Bucket classification (not continuous sizing), single provider, evaluation on its own traces; no shift across clusters.
**Relation to us:** Closest precedent for our "per-workload history matches the ML model" finding; we extend the history-is-predictive argument to GPU slices and test it on held-out clusters.

### 3. `k8svpa` (NEW) Kubernetes Vertical Pod Autoscaler
**Citation:** Kubernetes Authors. "Vertical Pod Autoscaling" (documentation) and kubernetes/autoscaler VPA recommender source, accessed Nov 2026.
**URLs opened:** https://kubernetes.io/docs/concepts/workloads/autoscaling/vertical-pod-autoscale/ ; https://raw.githubusercontent.com/kubernetes/autoscaler/master/vertical-pod-autoscaler/pkg/recommender/config/config.go
**Key findings:**
- Recommender defaults: target CPU and memory percentile 0.9 (P90), lower bound 0.5, upper bound 0.95, and a 0.15 (15%) recommendation margin fraction; minimum 25 millicores / 250 MB per pod.
- OOM handling: flag help states a default OOM bump-up ratio of 1.2 and a minimum bump of 100 MiB; memory aggregation interval default 24h (flag help).
- Update modes: Off, Initial (set only at pod creation), Recreate (evicts pods), InPlaceOrRecreate/InPlace.
**Strength:** The de facto open-source right-sizer; its rule is fully specified and inspectable.
**Limitation:** CPU/memory only, no GPU; heuristic with no published accuracy evaluation; no notion of cluster shift.
**Relation to us:** Our P90-of-history rule is essentially VPA's default target percentile applied to GPU slices; "Initial" mode is exactly admission-time sizing, and the OOM bump parallels our full-request fallback. Strong framing that the industry baseline is already a percentile-plus-margin rule.

### 4. `pan2023magicscaler` (existing key)
**Citation:** Z. Pan, Y. Wang, Y. Zhang, S. B. Yang, Y. Cheng, P. Chen, C. Guo, Q. Wen, X. Tian, Y. Dou, Z. Zhou, C. Yang, A. Zhou, B. Yang. "MagicScaler: Uncertainty-aware, Predictive Autoscaling." PVLDB 16(12):3808-3821, 2023. doi:10.14778/3611540.3611566
**URL opened:** https://www.vldb.org/pvldb/vol16/p3808-yang.pdf
**Key findings:**
- Predictor combines multi-scale attention with Gaussian-process regression to output demand with quantified uncertainty; the scaler uses it in a loss with stochastic (chance) constraints to trade cost vs QoS-violation risk.
- Predictor reduces MAE by 64.3% on average vs plain GP.
- On clusters HZ and SH, MagicScaler's QoS loss is 11.7% and 4.9% of Passive and Statistics baselines, at +1.2% and +43.9% resource cost respectively.
- The deterministic variant (MagicScaler-D) performs poorly on cluster BJ, failing to capture sudden demand, with higher QoS loss than the baselines.
**Strength:** Explicitly couples probabilistic prediction to a risk knob, from the same company (Alibaba) as our trace.
**Limitation:** Horizontal ECS instance scaling, not per-pod GPU sizing; results differ markedly by cluster and the paper does not train on one cluster and test on another.
**Relation to us:** Supports our claim that the safety/uncertainty rule drives outcomes; its cluster-BJ result is anecdotal evidence of the cluster-dependence we measure systematically.

### 5. `romano2019cqr` (existing key)
**Citation:** Y. Romano, E. Patterson, E. J. Candès. "Conformalized Quantile Regression." NeurIPS 2019.
**URL opened:** https://arxiv.org/abs/1905.03222 (arXiv page lists no venue; NeurIPS venue from existing refs.bib, not re-verified on this page)
**Key findings:**
- Combines quantile regression with conformal prediction to obtain finite-sample valid coverage without distributional assumptions.
- Adapts to heteroscedasticity, producing shorter intervals than prior conformal methods (qualitative; no single headline number in abstract).
**Strength:** Principled way to calibrate a quantile model's margin to a target violation rate.
**Limitation:** Coverage assumes exchangeability between calibration and test data, which cluster shift violates.
**Relation to us:** Theoretical backing for treating the safety margin as the key knob; our cross-cluster results probe exactly the exchangeability assumption.

---

## B. Predictive autoscaling for microservices

### 6. `qiu2020firm` (NEW)
**Citation:** H. Qiu, S. S. Banerjee, S. Jha, Z. T. Kalbarczyk, R. K. Iyer. "FIRM: An Intelligent Fine-grained Resource Management Framework for SLO-Oriented Microservices." OSDI 2020.
**URL opened:** https://www.usenix.org/conference/osdi20/presentation/qiu
**Key findings (vs Kubernetes autoscaling, four microservice benchmarks):**
- SLO violations reduced by up to 16x.
- Overall requested CPU limit reduced by up to 62%.
- Tail latency reduced by up to 11x.
**Strength:** Fine-grained, SLO-aware reprovisioning using ML (SVM localisation + RL).
**Limitation:** Benchmarks on a testbed, CPU-centric; RL policy trained per deployment with no transfer evaluation.
**Relation to us:** Representative of ML-heavy right-sizing; we show a simple history rule can match ML when evaluated on unseen clusters.

### 7. `zhang2021sinan` (NEW)
**Citation:** Y. Zhang, W. Hua, Z. Zhou, G. E. Suh, C. Delimitrou. "Sinan: ML-Based and QoS-Aware Resource Management for Cloud Microservices." ASPLOS 2021, pp. 167-181.
**URLs opened:** https://arxiv.org/abs/2105.13424 ; https://www.csl.cornell.edu/~delimitrou/papers/2021.asplos.sinan.pdf
**Key findings:**
- Meets QoS while saving 25.9% of CPU on average (up to 46.0%) on Hotel Reservation and 59.0% on average (up to 68.1%) on Social Network.
- Its boosted-trees violation predictor has accuracy above 94%; prediction inference is within 1% of the 1 s decision interval.
- Autoscaling baseline (AutoScaleOpt) probability of meeting QoS drops to 90.3% at 2800 users.
**Strength:** Learns a QoS-violation classifier and uses it as a safety check on allocations.
**Limitation:** Microservice benchmarks on a controlled cluster/GCE; retraining needed for new applications; no GPU.
**Relation to us:** Like our fallback, Sinan protects safety with an explicit violation check; we evaluate the analogous trade-off for GPU slices with production traces.

---

## C. ML inference serving: autoscaling and right-sizing

### 8. `crankshaw2017clipper` (NEW)
**Citation:** D. Crankshaw, X. Wang, G. Zhou, M. J. Franklin, J. E. Gonzalez, I. Stoica. "Clipper: A Low-Latency Online Prediction Serving System." NSDI 2017.
**URL opened:** https://www.usenix.org/conference/nsdi17/technical-sessions/presentation/crankshaw
**Key findings:**
- Caching, adaptive batching and adaptive model selection reduce latency and improve throughput, accuracy and robustness without changing ML frameworks.
- Throughput and latency comparable to TensorFlow Serving on four benchmark datasets (abstract gives no specific numbers).
**Strength:** Foundational serving system; established latency-SLO-driven batch sizing.
**Limitation:** No resource right-sizing or GPU partitioning; single-cluster evaluation.
**Relation to us:** Background for the online-inference workloads we size; shows serving systems tune batching, not GPU allocation.

### 9. `zhang2019mark` (NEW)
**Citation:** C. Zhang, M. Yu, W. Wang, F. Yan. "MArk: Exploiting Cloud Services for Cost-Effective, SLO-Aware Machine Learning Inference Serving." USENIX ATC 2019.
**URL opened:** https://www.usenix.org/conference/atc19/presentation/zhang-chengliang
**Key findings:**
- Reduces serving cost by up to 7.8x vs SageMaker while achieving better latency.
**Strength:** Combines predictive autoscaling with instance-type choice (IaaS + serverless).
**Limitation:** Chooses cloud instance types, not fractional GPUs; one-cloud evaluation.
**Relation to us:** Predictive provisioning for inference; we instead size the GPU share per pod at admission.

### 10. `romero2021infaas` (NEW)
**Citation:** F. Romero, Q. Li, N. J. Yadwadkar, C. Kozyrakis. "INFaaS: Automated Model-less Inference Serving." USENIX ATC 2021.
**URL opened:** https://www.usenix.org/conference/atc21/presentation/romero
**Key findings (vs state-of-the-art serving on AWS EC2):**
- 1.3x higher throughput; latency objectives violated 1.6x less often.
- Cost savings up to 21.6x, 8.5x on average.
**Strength:** Automates variant and hardware selection from user SLO requirements.
**Limitation:** Profiling-based per-variant choice; no evaluation of how sizing generalises across clusters.
**Relation to us:** Shows automated hardware/variant right-sizing pays off for inference; our paper asks whether the savings translate into reusable capacity.

### 11. `gunasekaran2022cocktail` (NEW)
**Citation:** J. R. Gunasekaran, C. S. Mishra, P. Thinakaran, B. Sharma, M. T. Kandemir, C. R. Das. "Cocktail: A Multidimensional Optimization for Model Serving in Cloud." NSDI 2022.
**URL opened:** https://www.usenix.org/conference/nsdi22/presentation/gunasekaran
**Key findings:**
- Deployment cost reduced by 1.45x and latency by 2x vs state-of-the-art serving.
- Target accuracy met for up to 96% of requests.
**Strength:** Joint ensemble selection and predictive, cost-aware autoscaling.
**Limitation:** Instance-level autoscaling; workloads/traces not from GPU-sharing production clusters.
**Relation to us:** Another prediction-driven inference autoscaler; complementary horizontal dimension to our vertical GPU-slice sizing.

### 12. `stojkovic2025dynamollm` (NEW)
**Citation:** J. Stojkovic, C. Zhang, Í. Goiri, J. Torrellas, E. Choukse. "DynamoLLM: Designing LLM Inference Clusters for Performance and Energy Efficiency." HPCA 2025. doi:10.1109/HPCA61900.2025.00102
**URL opened:** https://arxiv.org/abs/2408.00741 (venue inferred from the DOI listed on the arXiv page)
**Key findings (service level):**
- Conserves 53% energy, reduces operational carbon by 38%, and cuts customer cost by 61% while meeting latency SLOs.
**Strength:** Recent LLM-serving work that reconfigures GPU resources (instances, parallelism, frequency) per load.
**Limitation:** Microsoft-specific LLM workloads; reconfiguration rather than admission-time sizing.
**Relation to us:** Evidence that right-sizing GPU resources for inference is a live 2024-2026 problem; our work adds the transfer/reuse evaluation.

---

## D. GPU requirement estimation for DL jobs

### 13. `gao2020dnnmem` (NEW)
**Citation:** Y. Gao, Y. Liu, H. Zhang, Z. Li, Y. Zhu, H. Lin, M. Yang. "Estimating GPU Memory Consumption of Deep Learning Models." ESEC/FSE 2020 (Industry Track). doi:10.1145/3368089.3417050
**URL opened:** https://www.microsoft.com/en-us/research/publication/estimating-gpu-memory-consumption-of-deep-learning-models/
**Key findings:**
- Motivated by many DL job failures being due to GPU memory exhaustion.
- DNNMem analytically models the computation graph and framework runtime; evaluated on 5 models across TensorFlow, PyTorch and MXNet.
- Specific relative-error figures: UNVERIFIED (not in the abstract; full text not accessible).
**Strength:** White-box estimate available before the job runs, no history needed.
**Limitation:** Needs model graph/code; training jobs; per-framework engineering.
**Relation to us:** Alternative to history-based sizing; the ASI trace has no model graphs, so history is the only admissible signal there, which motivates our approach.

### 14. `yeung2022horus` (NEW)
**Citation:** G. Yeung, D. Borowiec, R. Yang, A. Friday, R. Harper, P. Garraghan. "Horus: Interference-Aware and Prediction-Based Scheduling in Deep Learning Systems." IEEE TPDS 33(1):88-100, 2022.
**URL opened:** https://eprints.lancs.ac.uk/id/eprint/154311
**Key findings:**
- Predicts a DL job's GPU utilisation from computation-graph features, avoiding online profiling.
- Up to 61.5% higher GPU resource utilisation, 23.7-30.7% makespan reduction, 68.3% lower job wait time.
**Strength:** Combines utilisation prediction with interference-aware co-location.
**Limitation:** Graph features required; mostly training jobs; generalisation beyond the evaluated models not established.
**Relation to us:** Prediction-for-packing on GPUs; we evaluate prediction where only past usage is known and test on unseen clusters.

### 15. `yousefzadeh2026gpuestimation` (NEW, preprint)
**Citation:** E. Yousefzadeh-Asl-Miandoab, R. Karimzadeh, D. Yorulmaz, B. Ibragimov, P. Tözün. "GPU Memory and Utilization Estimation for Training-Aware Resource Management: Opportunities and Limitations." arXiv:2602.17817, 2026.
**URL opened:** https://arxiv.org/abs/2602.17817
**Key findings:**
- Compares Horus, PyTorch FakeTensor and a lightweight ML estimator for accuracy, generalisability and overhead on synthetic MLPs, CNNs and Transformers.
- Concludes analytical models generalise poorly and that estimators depend on model specs/graphs (abstract gives no numbers).
**Strength:** Explicitly asks the generalisation question for GPU estimators.
**Limitation:** Preprint, synthetic models, training-focused.
**Relation to us:** Independent support that GPU estimators may not generalise; we measure generalisation across real production clusters.

---

## E. Sizing GPU fractions / MIG profiles

### 16. `li2022miso` (NEW)
**Citation:** B. Li, T. Patel, S. Samsi, V. Gadepally, D. Tiwari. "MISO: Exploiting Multi-Instance GPU Capability on Multi-Tenant Systems for Machine Learning." ACM SoCC 2022, pp. 173-189. doi:10.1145/3542929.3563510
**URLs opened:** https://arxiv.org/abs/2207.11428 ; https://api.crossref.org/works/10.1145/3542929.3563510 (venue/pages)
**Key findings:**
- Uses MPS co-location profiling to predict each job's best MIG slice, then optimises the partition.
- 49% lower average JCT than an unpartitioned GPU and 16% lower than the optimal static partition.
**Strength:** Directly predicts MIG slice size per job.
**Limitation:** Training/batch jobs; repartitioning incurs checkpoint overhead; testbed scale.
**Relation to us:** Closest analogue to choosing the smallest safe slice; we do it at admission from history for inference pods and evaluate under cluster shift.

### 17. `tan2021migserving` (NEW, preprint)
**Citation:** C. Tan, Z. Li, J. Zhang, Y. Cao, S. Qi, Z. Liu, Y. Zhu, C. Guo. "Serving DNN Models with Multi-Instance GPUs: A Case of the Reconfigurable Machine Scheduling Problem." arXiv:2109.11067, 2021.
**URL opened:** https://arxiv.org/abs/2109.11067
**Key findings:**
- Different models prefer different MIG instance sizes; mixing sizes improves serving.
- Up to 40% fewer GPUs at the same throughput vs A100 with MIG disabled.
**Strength:** Inference-specific MIG sizing from an industrial (ByteDance) team.
**Limitation:** arXiv only (no peer-reviewed venue listed); offline profiling per model.
**Relation to us:** Shows per-model slice choice matters for inference; we study whether such choices can be predicted safely at admission without profiling.

### 18. `kim2022parisElsa` (NEW)
**Citation:** Y. Kim, Y. Choi, M. Rhu. "PARIS and ELSA: An Elastic Scheduling Algorithm for Reconfigurable Multi-GPU Inference Servers." DAC 2022.
**URL opened:** https://arxiv.org/abs/2202.13481 (venue from arXiv comment)
**Key findings:**
- PARIS partitions reconfigurable (MIG) GPUs into heterogeneous slices; ELSA schedules inference queries across them, balancing latency and utilisation.
- Abstract gives no numbers (quantitative gains UNVERIFIED).
**Strength:** Inference-specific heterogeneous slice sizing.
**Limitation:** Simulated/server scale; model profiles assumed known.
**Relation to us:** Further evidence that slice heterogeneity helps inference; our results caution that freed slices are not automatically reusable.

---

## BibTeX (new keys only)

```bibtex
@misc{k8svpa,
  author       = {{Kubernetes Authors}},
  title        = {Vertical Pod Autoscaling},
  howpublished = {\url{https://kubernetes.io/docs/concepts/workloads/autoscaling/vertical-pod-autoscale/}; recommender defaults in \url{https://github.com/kubernetes/autoscaler/blob/master/vertical-pod-autoscaler/pkg/recommender/config/config.go}},
  note         = {Accessed November 2026},
  year         = {2026}
}

@inproceedings{qiu2020firm,
  author    = {Qiu, Haoran and Banerjee, Subho S. and Jha, Saurabh and Kalbarczyk, Zbigniew T. and Iyer, Ravishankar K.},
  title     = {{FIRM}: An Intelligent Fine-grained Resource Management Framework for {SLO}-Oriented Microservices},
  booktitle = {USENIX Symposium on Operating Systems Design and Implementation (OSDI)},
  year      = {2020}
}

@inproceedings{zhang2021sinan,
  author    = {Zhang, Yanqi and Hua, Weizhe and Zhou, Zhuangzhuang and Suh, G. Edward and Delimitrou, Christina},
  title     = {Sinan: {ML}-Based and {QoS}-Aware Resource Management for Cloud Microservices},
  booktitle = {ACM International Conference on Architectural Support for Programming Languages and Operating Systems (ASPLOS)},
  pages     = {167--181},
  year      = {2021}
}

@inproceedings{crankshaw2017clipper,
  author    = {Crankshaw, Daniel and Wang, Xin and Zhou, Guilio and Franklin, Michael J. and Gonzalez, Joseph E. and Stoica, Ion},
  title     = {Clipper: A Low-Latency Online Prediction Serving System},
  booktitle = {USENIX Symposium on Networked Systems Design and Implementation (NSDI)},
  year      = {2017}
}

@inproceedings{zhang2019mark,
  author    = {Zhang, Chengliang and Yu, Minchen and Wang, Wei and Yan, Feng},
  title     = {{MArk}: Exploiting Cloud Services for Cost-Effective, {SLO}-Aware Machine Learning Inference Serving},
  booktitle = {USENIX Annual Technical Conference (ATC)},
  year      = {2019}
}

@inproceedings{romero2021infaas,
  author    = {Romero, Francisco and Li, Qian and Yadwadkar, Neeraja J. and Kozyrakis, Christos},
  title     = {{INFaaS}: Automated Model-less Inference Serving},
  booktitle = {USENIX Annual Technical Conference (ATC)},
  year      = {2021}
}

@inproceedings{gunasekaran2022cocktail,
  author    = {Gunasekaran, Jashwant Raj and Mishra, Cyan Subhra and Thinakaran, Prashanth and Sharma, Bikash and Kandemir, Mahmut Taylan and Das, Chita R.},
  title     = {Cocktail: A Multidimensional Optimization for Model Serving in Cloud},
  booktitle = {USENIX Symposium on Networked Systems Design and Implementation (NSDI)},
  year      = {2022}
}

@inproceedings{stojkovic2025dynamollm,
  author    = {Stojkovic, Jovan and Zhang, Chaojie and Goiri, {\'I}{\~n}igo and Torrellas, Josep and Choukse, Esha},
  title     = {{DynamoLLM}: Designing {LLM} Inference Clusters for Performance and Energy Efficiency},
  booktitle = {IEEE International Symposium on High-Performance Computer Architecture (HPCA)},
  year      = {2025},
  doi       = {10.1109/HPCA61900.2025.00102}
}

@inproceedings{gao2020dnnmem,
  author    = {Gao, Yanjie and Liu, Yu and Zhang, Hongyu and Li, Zhengxian and Zhu, Yonghao and Lin, Haoxiang and Yang, Mao},
  title     = {Estimating {GPU} Memory Consumption of Deep Learning Models},
  booktitle = {ACM Joint European Software Engineering Conference and Symposium on the Foundations of Software Engineering (ESEC/FSE), Industry Track},
  year      = {2020},
  doi       = {10.1145/3368089.3417050}
}

@article{yeung2022horus,
  author  = {Yeung, Gingfung and Borowiec, Damian and Yang, Renyu and Friday, Adrian and Harper, Richard and Garraghan, Peter},
  title   = {Horus: Interference-Aware and Prediction-Based Scheduling in Deep Learning Systems},
  journal = {IEEE Transactions on Parallel and Distributed Systems},
  volume  = {33},
  number  = {1},
  pages   = {88--100},
  year    = {2022}
}

@misc{yousefzadeh2026gpuestimation,
  author        = {Yousefzadeh-Asl-Miandoab, Ehsan and Karimzadeh, Reza and Yorulmaz, Danyal and Ibragimov, Bulat and T{\"o}z{\"u}n, P{\i}nar},
  title         = {{GPU} Memory and Utilization Estimation for Training-Aware Resource Management: Opportunities and Limitations},
  eprint        = {2602.17817},
  archivePrefix = {arXiv},
  year          = {2026}
}

@inproceedings{li2022miso,
  author    = {Li, Baolin and Patel, Tirthak and Samsi, Siddharth and Gadepally, Vijay and Tiwari, Devesh},
  title     = {{MISO}: Exploiting Multi-Instance {GPU} Capability on Multi-Tenant Systems for Machine Learning},
  booktitle = {ACM Symposium on Cloud Computing (SoCC)},
  pages     = {173--189},
  year      = {2022},
  doi       = {10.1145/3542929.3563510}
}

@misc{tan2021migserving,
  author        = {Tan, Cheng and Li, Zhichao and Zhang, Jian and Cao, Yu and Qi, Sikai and Liu, Zherui and Zhu, Yibo and Guo, Chuanxiong},
  title         = {Serving {DNN} Models with Multi-Instance {GPUs}: A Case of the Reconfigurable Machine Scheduling Problem},
  eprint        = {2109.11067},
  archivePrefix = {arXiv},
  year          = {2021}
}

@inproceedings{kim2022parisElsa,
  author    = {Kim, Yunseong and Choi, Yujeong and Rhu, Minsoo},
  title     = {{PARIS} and {ELSA}: An Elastic Scheduling Algorithm for Reconfigurable Multi-{GPU} Inference Servers},
  booktitle = {ACM/IEEE Design Automation Conference (DAC)},
  year      = {2022}
}
```

Optional upgrade to the existing `rzadca2020autopilot` and `cortez2017resource` entries: replace `and others` with the full author lists given above; add `pages = {153--167}, doi = {10.1145/3132747.3132772}` to Resource Central and `pages = {3808--3821}, doi = {10.14778/3611540.3611566}` plus the full author list to MagicScaler.

---

## Cross-cutting pattern and the gap we fill

Across CPU/memory clouds (Autopilot, Resource Central, VPA), microservices (FIRM, Sinan), inference serving (MArk, INFaaS, Cocktail, DynamoLLM) and GPU/MIG sizing (MISO, MIG-serving, PARIS/ELSA, Horus, DNNMem), the same two facts recur. First, *history is a strong predictor*: Resource Central's most important features are a subscription's past behaviour, and the open-source baseline (VPA) is literally a P90-of-history rule plus a 15% margin with an OOM bump. Second, *outcomes hinge on the safety/uncertainty policy* (MagicScaler's chance constraints, Sinan's violation check, VPA's margin and OOM bump, CQR's calibrated coverage) as much as on the predictor. Yet almost every system is evaluated inside the fleet or testbed it was trained on, and success is measured as reduced allocation, slack or cost, not as whether freed capacity can actually be reused by other work. Only incidental hints of cluster dependence appear (e.g., MagicScaler-D failing on cluster BJ), and GPU/MIG sizing work relies on profiling or model graphs and targets training jobs. Our paper fills this gap. It evaluates admission-time GPU-slice prediction for online inference on *held-out clusters* of a production trace. It shows a VPA-style history rule matches XGBoost quantile models there, and that the margin rule matters about 5x more than the model. It also measures the *downstream* question prior work skips: once safety fallbacks are counted (restoring the full request after 6 short hours removes 81% of short pod-hours), how much reclaimed GPU actually becomes reusable.
