# Theme: Evaluation methodology for ML (and ML-for-systems) under distribution shift

Annotated bibliography for "Reclaimable Is Not Reusable: Evaluating GPU Right-Sizing Under Cluster Shift".
Every claim below was taken from the page listed under "URL opened" (abstract page, proceedings page, or the paper PDF text). Venue metadata was checked on a proceedings page or Crossref where the arXiv page gave none. Nothing in this file is marked UNVERIFIED; the closest cases are flagged in-line (the pre-registration source is a workshop preface, and the DomainBed algorithm count differs between versions).

Existing refs.bib keys reused: `gulrajani2021search`, `koh2021wilds`, `romano2019cqr`, `angelopoulos2021gentle`, `narayanan2020gavel`, `weng2023fgd` (the last two are already in refs.bib, so no new BibTeX is given for them).

---

## A. Benchmarks for evaluating under domain shift

### 1. `gulrajani2021search` (existing key)
**Citation.** Ishaan Gulrajani and David Lopez-Paz. "In Search of Lost Domain Generalization." International Conference on Learning Representations (ICLR), 2021.
**URL opened.** https://arxiv.org/abs/2007.01434 ; https://iclr.cc/virtual/2021/poster/2998 ; https://mlanthology.org/iclr/2021/gulrajani2021iclr-search
- The paper argues that a domain-generalization algorithm without a model-selection strategy is incomplete. Hyperparameter and model selection must be specified as part of the method.
- It releases DomainBed: seven multi-domain datasets and three model-selection criteria. The algorithm count is fourteen in the ICLR poster abstract and nine baselines in arXiv v1, so cite the ICLR version.
- When carefully implemented and tuned, ERM matches or beats recent DG methods on average. Under the same conditions, no algorithm beat ERM by more than about one point (ICLR abstract).

**Strengths.** It established leave-one-domain-out evaluation with a declared selection rule as the standard protocol, and showed how much reported gains depend on the protocol.
**Limitations.** It covers image classification and accuracy only. Nothing downstream of the prediction is evaluated.
**Relation to our paper.** This is the direct template for our leave-one-cluster-out protocol. Our "three declared margin-selection rules, oracle disclaimed" carries DomainBed's model-selection point (no test-domain tuning) over to safety margins.

### 2. `koh2021wilds` (existing key)
**Citation.** Pang Wei Koh, Shiori Sagawa, Henrik Marklund, Sang Michael Xie, Marvin Zhang, Akshay Balsubramani, Weihua Hu, Michihiro Yasunaga, Richard Lanas Phillips, Irena Gao, Tony Lee, Etienne David, Ian Stavness, Wei Guo, Berton Earnshaw, Imran Haque, Sara M. Beery, Jure Leskovec, Anshul Kundaje, Emma Pierson, Sergey Levine, Chelsea Finn, Percy Liang. "WILDS: A Benchmark of in-the-Wild Distribution Shifts." Proceedings of the 38th International Conference on Machine Learning (ICML), PMLR 139:5637-5664, 2021.
**URL opened.** https://arxiv.org/abs/2012.07421 ; https://proceedings.mlr.press/v139/koh21a.html
- It curates 10 datasets with distribution shifts that arise in real deployments, such as across hospitals, camera traps, and time and location in satellite and poverty mapping.
- Standard training performs much worse out of distribution than in distribution, and existing shift-handling methods do not close the gap.
- It ships standardized loaders, default models, hyperparameters, and evaluation so that OOD numbers are comparable.

**Strengths.** It uses real, naturally occurring domain shifts (one domain per site or time period) instead of synthetic corruptions.
**Limitations.** Metrics are predictive (accuracy, worst-group accuracy and similar). There are no systems datasets and no evaluation of decisions taken on the predictions.
**Relation to our paper.** GPU clusters are a natural "in-the-wild" domain split in the WILDS sense. We report the ID-to-OOD gap in coverage (95% target to 92% unseen) and in decision savings, not only in error.

---

## B. Conformal prediction and its validity under shift

### 3. `romano2019cqr` (existing key)
**Citation.** Yaniv Romano, Evan Patterson, Emmanuel Candès. "Conformalized Quantile Regression." Advances in Neural Information Processing Systems 32 (NeurIPS), 2019.
**URL opened.** https://arxiv.org/abs/1905.03222 ; https://papers.nips.cc/paper/2019/hash/5103c3584b063c431bd1268e9b5e76fb-Abstract.html
- It combines split conformal prediction (finite-sample, distribution-free validity) with quantile regression.
- Intervals adapt to heteroscedasticity, whereas earlier conformal intervals have roughly constant width.
- It gives a coverage guarantee and reports generally shorter intervals than other conformal methods on standard regression datasets.

**Strengths.** Valid and adaptive. It wraps any quantile regressor.
**Limitations.** Validity rests on exchangeability between the calibration and test data.
**Relation to our paper.** This is the mechanism behind our split-conformal margins. Fitting them on other clusters deliberately breaks the exchangeability CQR assumes, which is what our 92% result measures.

### 4. `angelopoulos2021gentle` (existing key)
**Citation.** Anastasios N. Angelopoulos and Stephen Bates. "A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification." arXiv:2107.07511, 2021 (v6, Dec 2022).
**URL opened.** https://arxiv.org/abs/2107.07511
- Conformal prediction wraps any pre-trained model to produce sets that contain the truth with a user-chosen probability, such as 90%.
- The guarantees are distribution-free and finite-sample.
- The tutorial covers extensions to distribution shift, time series, outliers, and abstention, with code.

**Strengths.** A clear, practitioner-oriented reference with code. Widely cited.
**Limitations.** A tutorial on arXiv, not peer-reviewed. The shift extensions are surveyed rather than evaluated.
**Relation to our paper.** Background citation for the split-conformal procedure and for the conditions under which marginal coverage holds.

### 5. `tibshirani2019covariate` (new)
**Citation.** Ryan J. Tibshirani, Rina Foygel Barber, Emmanuel Candès, Aaditya Ramdas. "Conformal Prediction Under Covariate Shift." Advances in Neural Information Processing Systems 32 (NeurIPS), 2019.
**URL opened.** https://arxiv.org/abs/1904.06019 ; https://papers.nips.cc/paper/2019/hash/8fb21ee7a2207526da55a679f0332de2-Abstract.html
- Weighted conformal prediction yields distribution-free intervals when the train and test covariate distributions differ.
- It requires the likelihood ratio between the test and train covariate distributions to be known or estimated, for example from unlabeled test covariates.
- It introduces a "weighted exchangeability" notion that covers this setting.

**Strengths.** A principled fix that retains coverage under pure covariate shift.
**Limitations.** It needs a reliable density-ratio estimate. It does not address label or conditional shift, which cluster shift can involve (different workloads and schedulers).
**Relation to our paper.** A natural next step beyond our unweighted cross-cluster margins. The 3-point coverage loss is what an unweighted method suffers. Weighting by cluster covariates is a candidate remedy we can name as future work.

### 6. `barber2023beyond` (new)
**Citation.** Rina Foygel Barber, Emmanuel J. Candès, Aaditya Ramdas, Ryan J. Tibshirani. "Conformal Prediction Beyond Exchangeability." The Annals of Statistics, 51(2):816-845, 2023. doi:10.1214/23-AOS2276.
**URL opened.** https://arxiv.org/abs/2202.13415 ; metadata via Crossref for doi:10.1214/23-AOS2276 (the projecteuclid page returned no content)
- Conformal guarantees assume exchangeable data and a symmetric fitting algorithm, and both often fail, for example under drift over time.
- It uses weighted quantiles to be robust to drift, plus a randomization technique for algorithms that treat points asymmetrically, such as up-weighting recent data.
- When exchangeability holds, the standard guarantees are retained. Under violation, substantially more coverage is kept. Demonstrated on electricity and election data.

**Strengths.** It bounds the coverage gap in terms of how far the distribution deviates from exchangeability. Top statistics venue.
**Limitations.** The weights must be chosen a priori. The bounds are informative only when the shift is small or the weights match it.
**Relation to our paper.** It gives the theory for why our cross-cluster coverage dropped by a bounded amount (95% to 92%) rather than collapsing. It also supports reporting coverage loss as a measured quantity rather than assuming validity.

### 7. `gibbs2021adaptive` (new)
**Citation.** Isaac Gibbs and Emmanuel Candès. "Adaptive Conformal Inference Under Distribution Shift." Advances in Neural Information Processing Systems 34 (NeurIPS), 2021.
**URL opened.** https://arxiv.org/abs/2106.00170 ; https://proceedings.neurips.cc/paper/2021/hash/0d441de75945e5acbc865406fc9a2559-Abstract.html
- An online conformal wrapper for settings where the data-generating distribution changes in unknown ways over time.
- It treats the shift as a single-parameter learning problem that is continuously re-estimated.
- It "provably achieves the desired coverage frequency over long-time intervals" regardless of the data-generating process, and is robust on two real datasets.

**Strengths.** Long-run coverage holds with no assumptions on the shift.
**Limitations.** It needs a stream of feedback (realized labels) and guarantees only long-run average coverage, not coverage per window or per domain. It recovers after miscoverage rather than preventing it.
**Relation to our paper.** A candidate deployment-time fix: start with cross-cluster margins, then adapt online as pods finish in the new cluster. This contrasts with our static, pre-declared rules and motivates a future-work paragraph.

---

## C. Leakage, temporal bias, and evaluation pitfalls

### 8. `kapoor2023leakage` (new)
**Citation.** Sayash Kapoor and Arvind Narayanan. "Leakage and the Reproducibility Crisis in Machine-Learning-Based Science." Patterns, 4(9):100804, 2023. doi:10.1016/j.patter.2023.100804.
**URL opened.** https://arxiv.org/abs/2207.07048 ; Crossref record for the Patterns version (the cell.com page returned 403) ; https://reproducible.cs.princeton.edu/
- A survey of 17 fields finds leakage errors in 329 papers. It proposes a taxonomy of 8 leakage types and "model info sheets" for reporting.
- The taxonomy includes "lack of clean separation of training and test set", "model uses features which are not legitimate", and "test set is not drawn from the distribution of interest" (from the project page).
- In a civil-war prediction case study, complex ML models no longer substantively outperform decades-old logistic regression once leakage is fixed.
- The project page lists temporal leakage in papers from several fields, including an IT-operations paper (Lyu et al. 2021).

**Strengths.** Cross-disciplinary evidence and an actionable taxonomy and reporting checklist.
**Limitations.** Focused on scientific prediction claims. It does not quantify leakage effects on downstream operational decisions.
**Relation to our paper.** Our leakage audit (history features built only from pods finished before admission) addresses the "illegitimate features" and temporal-leakage types. The 1.9-point inflation in savings is a concrete systems instance of the effect they document.

### 9. `pendlebury2019tesseract` (new)
**Citation.** Feargus Pendlebury, Fabio Pierazzi, Roberto Jordaney, Johannes Kinder, Lorenzo Cavallaro. "TESSERACT: Eliminating Experimental Bias in Malware Classification across Space and Time." 28th USENIX Security Symposium, pp. 729-746, 2019.
**URL opened.** https://arxiv.org/abs/1807.07838 ; https://www.usenix.org/conference/usenixsecurity19/presentation/pendlebury
- Published near-0.99 F1 scores for Android malware detection are inflated by spatial bias (training and test sets unrepresentative of deployment) and temporal bias (time-inconsistent splits creating impossible configurations).
- It proposes experiment-design constraints to remove both biases, a metric for expected robustness over time, and a tuning algorithm.
- With TESSERACT on 129K apps over three years, prior published results are shown to be biased.

**Strengths.** A canonical demonstration that time-aware splits change conclusions, with a released evaluation framework.
**Limitations.** Specific to malware classification. The constraints are about splits, not about features computed from future data inside a record.
**Relation to our paper.** Supports our time-respecting feature construction (only pods finished before admission) and our "space" split (leave-one-cluster-out). The temporal and spatial bias framing maps onto our leakage audit and cluster shift.

### 10. `arp2022dos` (new)
**Citation.** Daniel Arp, Erwin Quiring, Feargus Pendlebury, Alexander Warnecke, Fabio Pierazzi, Christian Wressnegger, Lorenzo Cavallaro, Konrad Rieck. "Dos and Don'ts of Machine Learning in Computer Security." 31st USENIX Security Symposium, pp. 3971-3988, 2022. (Distinguished Paper Award.)
**URL opened.** https://arxiv.org/abs/2010.09470 ; https://www.usenix.org/conference/usenixsecurity22/presentation/arp ; arXiv PDF v2 (text extracted)
- It names ten pitfalls: P1 Sampling Bias, P2 Label Inaccuracy, P3 Data Snooping, P4 Spurious Correlations, P5 Biased Parameter Selection, P6 Inappropriate Baseline, P7 Inappropriate Performance Measures, P8 Base Rate Fallacy, P9 Lab-Only Evaluation, P10 Inappropriate Threat Model.
- Data snooping comes in three types (test, temporal, selective). Temporal snooping "occurs if time dependencies within the data are ignored."
- In 30 papers from top security venues, sampling bias and data snooping are at least partly present in 90% and 73% of papers respectively (PDF text).
- P9: a system "solely evaluated in a laboratory setting, without discussing its practical limitations."

**Strengths.** A systematic, quantified pitfall list from a systems-adjacent community. Directly reusable as a checklist.
**Limitations.** Security-specific. Pitfalls are prevalence-coded by the authors' judgment, and the paper evaluates few downstream system outcomes.
**Relation to our paper.** Our design avoids P3 (temporal snooping, through the leakage audit), P5 (biased parameter selection, through declared margin rules with the oracle disclaimed) and P7 (inappropriate measures, through reporting reusable rather than "reclaimable" capacity). P9 motivates our validated-simulator replay.

---

## D. Pre-registration

### 11. `bertinetto2020prereg` (new; workshop, not a peer-reviewed paper)
**Citation.** Luca Bertinetto, João F. Henriques, Samuel Albanie, Michela Paganini, Gül Varol (organizers). "The Pre-registration Experiment: An Alternative Publication Model for Machine Learning Research." NeurIPS 2020 Workshop. Follow-up: Albanie, Henriques, Bertinetto, Hernández-García, Doughty, Varol (eds.), NeurIPS 2021 Workshop on Pre-registration in Machine Learning, PMLR vol. 181, 2022.
**URL opened.** https://neurips.cc/virtual/2020/workshop/16158 ; https://proceedings.mlr.press/v181/albanie22a.html
- Papers are reviewed with no results, as an experimental protocol to be executed after acceptance. Reviewers judge the argument and the design, not the numbers.
- Motivation: pressure to "beat the state of the art" erodes rigorous experimental design, and unpublished negative results get wastefully repeated.
- It builds on a small computer-vision trial and on pre-registration practice in the life sciences. The 2021 edition's papers appear in PMLR 181.

**Strengths.** The only venue-level pre-registration experiment in ML. It makes the case for committing to protocols before seeing outcomes.
**Limitations.** The pages describe the model but report no evidence of its effect. This is a workshop description, not an empirical study. No systems-community equivalent was found in this pass.
**Relation to our paper.** Precedent for our pre-registered go/no-go gate and for publishing a negative ("not reusable") result instead of tuning until positive.

---

## E. ML-for-systems evaluation realism and simulator fidelity

### 12. `yan2020puffer` (new)
**Citation.** Francis Y. Yan, Hudson Ayers, Chenzhi Zhu, Sadjad Fouladi, James Hong, Keyi Zhang, Philip Levis, Keith Winstein. "Learning in situ: a randomized experiment in video streaming." 17th USENIX Symposium on Networked Systems Design and Implementation (NSDI), pp. 495-511, 2020.
**URL opened.** https://arxiv.org/abs/1906.01113
- A randomized controlled trial of ABR and network-prediction schemes: 14.2 years of video streamed to 56,000 users over eight months.
- A simple buffer-based controller was hard to beat. Sophisticated and ML schemes that looked strong in emulators or simulators often underperformed in the real world.
- The authors attribute this to network variability and heavy tails. A predictor trained in situ on deployment data outperformed the other schemes.

**Strengths.** The strongest evidence in ML-for-systems that simulation-trained learned controllers fail to transfer, from a randomized design at scale.
**Limitations.** One domain (video streaming), and it requires a live deployment that most cluster-scheduling work cannot run.
**Relation to our paper.** The networking analogue of our finding: gains measured in the source environment (reclaimable capacity) do not carry over to a shifted target environment (reusable capacity on unseen clusters).

### 13. `narayanan2020gavel` (existing key)
**Citation.** Deepak Narayanan, Keshav Santhanam, Fiodar Kazhamiaka, Amar Phanishayee, Matei Zaharia. "Heterogeneity-Aware Cluster Scheduling Policies for Deep Learning Workloads." 14th USENIX Symposium on Operating Systems Design and Implementation (OSDI), pp. 481-498, 2020.
**URL opened.** https://www.usenix.org/conference/osdi20/presentation/narayanan-deepak ; OSDI'20 PDF (text extracted)
- Gavel recasts scheduling policies as optimization problems over "effective throughput" across heterogeneous accelerators. It reports 1.4x makespan and 3.5x average-JCT improvement over heterogeneity-agnostic policies.
- The authors validate a roughly 500-LOC simulator against a 48-GPU physical cluster (8 V100, 16 P100, 24 K80). Table 3 compares physical and simulated results: average JCT 3.4 vs 3.7 h (Gavel) and 5.1 vs 5.4 h (LAS); makespan 17.7 vs 17.6 h (Gavel) and 21.3 vs 22.1 h (Gandiva). The paper states agreement within 8%.
- Larger-scale results (36 GPUs of each type) come from the validated simulator.

**Strengths.** A clear, reusable pattern for scheduler-simulator validation: compare end objectives on the same traces at small scale, then extrapolate.
**Limitations.** Validation covers only a few policy and trace pairs at small scale. Agreement on aggregate objectives does not establish fidelity at scale or under different workloads.
**Relation to our paper.** Methodological precedent for our "validated scheduler simulator" claim. We should report our validation in the same form (end-objective agreement on held-out traces).

### 14. `weng2023fgd` (existing key)
**Citation.** Qizhen Weng, Lingyun Yang, Yinghao Yu, Wei Wang, Xiaochuan Tang, Guodong Yang, Liping Zhang. "Beware of Fragmentation: Scheduling GPU-Sharing Workloads with Fragmentation Gradient Descent." USENIX Annual Technical Conference (ATC), pp. 995-1008, 2023.
**URL opened.** https://www.usenix.org/conference/atc23/presentation/weng
- In Alibaba production traces, partial-GPU allocation (GPU sharing) causes severe fragmentation that leaves hundreds of GPUs unallocatable.
- It proposes a statistical fragmentation measure and FGD, which places tasks to minimize fragmentation growth. Implemented as a Kubernetes scheduler.
- It is evaluated on an emulated cluster of more than 6,200 GPUs replaying production traces. FGD reduces unallocated GPUs by up to 49% (about 290 more GPUs allocated) versus packing baselines.

**Strengths.** Realistic trace-driven evaluation at production scale for GPU-sharing schedulers, with an open simulator.
**Limitations.** The evaluation is emulation and trace replay of one provider's cluster. The abstract does not describe validating the emulator against live placements (not checked beyond the landing page).
**Relation to our paper.** Our Phase 6 snapshot replay uses the FGD simulator. It is the vehicle for turning predicted right-sizing into a downstream "reusable capacity" metric, rather than stopping at predicted savings.

---

## BibTeX (new keys only)

```bibtex
@inproceedings{tibshirani2019covariate,
  title     = {Conformal Prediction Under Covariate Shift},
  author    = {Tibshirani, Ryan J. and Barber, Rina Foygel and Cand{\`e}s, Emmanuel and Ramdas, Aaditya},
  booktitle = {Advances in Neural Information Processing Systems 32 (NeurIPS)},
  year      = {2019}
}

@article{barber2023beyond,
  title   = {Conformal Prediction Beyond Exchangeability},
  author  = {Barber, Rina Foygel and Cand{\`e}s, Emmanuel J. and Ramdas, Aaditya and Tibshirani, Ryan J.},
  journal = {The Annals of Statistics},
  volume  = {51},
  number  = {2},
  pages   = {816--845},
  year    = {2023},
  doi     = {10.1214/23-AOS2276}
}

@inproceedings{gibbs2021adaptive,
  title     = {Adaptive Conformal Inference Under Distribution Shift},
  author    = {Gibbs, Isaac and Cand{\`e}s, Emmanuel},
  booktitle = {Advances in Neural Information Processing Systems 34 (NeurIPS)},
  year      = {2021}
}

@article{kapoor2023leakage,
  title   = {Leakage and the Reproducibility Crisis in Machine-Learning-Based Science},
  author  = {Kapoor, Sayash and Narayanan, Arvind},
  journal = {Patterns},
  volume  = {4},
  number  = {9},
  pages   = {100804},
  year    = {2023},
  doi     = {10.1016/j.patter.2023.100804}
}

@inproceedings{pendlebury2019tesseract,
  title     = {{TESSERACT}: Eliminating Experimental Bias in Malware Classification across Space and Time},
  author    = {Pendlebury, Feargus and Pierazzi, Fabio and Jordaney, Roberto and Kinder, Johannes and Cavallaro, Lorenzo},
  booktitle = {28th USENIX Security Symposium (USENIX Security 19)},
  pages     = {729--746},
  year      = {2019}
}

@inproceedings{arp2022dos,
  title     = {Dos and Don'ts of Machine Learning in Computer Security},
  author    = {Arp, Daniel and Quiring, Erwin and Pendlebury, Feargus and Warnecke, Alexander and Pierazzi, Fabio and Wressnegger, Christian and Cavallaro, Lorenzo and Rieck, Konrad},
  booktitle = {31st USENIX Security Symposium (USENIX Security 22)},
  pages     = {3971--3988},
  year      = {2022}
}

@misc{bertinetto2020prereg,
  title        = {The Pre-registration Experiment: An Alternative Publication Model for Machine Learning Research},
  author       = {Bertinetto, Luca and Henriques, Jo{\~a}o F. and Albanie, Samuel and Paganini, Michela and Varol, G{\"u}l},
  howpublished = {NeurIPS 2020 Workshop},
  year         = {2020},
  url          = {https://neurips.cc/virtual/2020/workshop/16158}
}

@inproceedings{yan2020puffer,
  title     = {Learning in situ: a randomized experiment in video streaming},
  author    = {Yan, Francis Y. and Ayers, Hudson and Zhu, Chenzhi and Fouladi, Sadjad and Hong, James and Zhang, Keyi and Levis, Philip and Winstein, Keith},
  booktitle = {17th USENIX Symposium on Networked Systems Design and Implementation (NSDI 20)},
  pages     = {495--511},
  year      = {2020}
}
```

---

## Cross-cutting pattern and the gap

Across these communities the same lesson keeps returning: results measured in the environment used for development overstate performance in the one used for deployment. Each community supplies a piece of discipline. DomainBed and WILDS require held-out domains and declared model selection. Conformal work (CQR, Tibshirani et al., Barber et al., Gibbs and Candès) says exactly which assumptions coverage rests on and how far it degrades when they fail. Kapoor and Narayanan, TESSERACT, and Arp et al. show that leakage and time-inconsistent splits routinely inflate results. The pre-registration workshops argue for committing to protocols before seeing outcomes. Puffer, Gavel, and FGD show that simulator or emulator results need validating before anyone trusts them. But each piece stops short. Shift-aware ML evaluation scores *predictions* (accuracy, coverage), not the operational *decisions* built on them. Pitfall papers catalogue errors in security and science but not in resource management. Systems papers validate simulators yet evaluate learned components in-distribution, with tuning on the test environment left implicit. No work we found combines all of these for ML-driven resource allocation: held-out clusters as domains, safety margins chosen by a declared rule with no oracle, coverage reported after shift, a pre-registered gate, a leakage audit with a quantified effect, and a downstream metric (capacity actually reusable by a validated scheduler simulator). Our paper fills that gap. It shows that a 3-point coverage loss and a 1.9-point leakage effect are enough to separate "reclaimable" from "reusable" GPU capacity.
