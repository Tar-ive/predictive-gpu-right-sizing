# What six GPU schedulers actually do: reverse-engineered from their release binaries

Run on Nov 3, 2026. We pulled the shipped `linux/amd64` binaries from the projects' public container images, identified them with
[REA](https://github.com/morluto/rea) (`rea-agents` 6.8.0), and read the sizing and scoring code from disassembly. We read the
binaries rather than GitHub source so that the constants are the ones actually deployed in these releases.

## Tooling

| Step | Tool |
|---|---|
| Image to binary | `crane export` (go-containerregistry v0.20.2) |
| Build identity (Go version, module, commit, ldflags, dependencies) | `rea inspect-go-binary` → `evidence/go_build_info.json` |
| Disassembly of symbolized binaries (Koordinator, KAI, Volcano) | `rea inspect-with-objdump <bin> disassemble --symbol <fn>` |
| Function recovery in **stripped** binaries (HAMi, kube-scheduler, VPA) | `gofuncs/` reads Go's `.gopclntab` (handles cgo binaries whose Go text does not start at `.text`) |
| Constant recovery | `godis.py` disassembles a pclntab range with objdump, then resolves `movsd [rip+x]` float literals, `lea` string literals and call targets |

Ghidra 12.1 (REA's decompiler backend) could not be installed in this environment because GitHub release downloads are blocked
there, and building Rizin from source was not permitted. All findings therefore come from REA's engine-free readers plus
disassembly; nothing was decompiled.

## Binaries

| Binary (image) | Version / commit (from REA) | Go | Stripped |
|---|---|---|---|
| `vpa-recommender` (registry.k8s.io/autoscaling/vpa-recommender:1.4.1) | autoscaler VPA, `-ldflags -s` | 1.24.3 | yes |
| `kube-scheduler` (registry.k8s.io/kube-scheduler:v1.34.1) | k8s v1.34.1 @ 93248f9a | 1.24.6 | yes |
| `kai-scheduler` (ghcr.io/nvidia/kai-scheduler/scheduler:v0.9.3) | KAI v0.9.3 @ 0a680562, k8s v1.32.7 | 1.24.4 | no |
| `hami-scheduler` (docker.io/projecthami/hami:v2.6.1) | HAMi v2.6.1 @ e482ca3f, cgo | 1.22.5 | yes |
| `vc-scheduler` (docker.io/volcanosh/vc-scheduler:v1.12.1) | Volcano v1.12.1 @ f7acc998, k8s v1.32.2 | 1.23.7 | no |
| `koord-scheduler` (ghcr.io/koordinator-sh/koord-scheduler:v1.6.0) | Koordinator (devel build), k8s v1.28.7 | 1.20.14 | no |

## Findings

### 1. VPA recommender: the closest algorithm to Model A, but it does not handle GPUs

From `logic.init`, `main.init`, `model.(*AggregationsConfig).cpuHistogramOptions` and `logic.CreatePodResourceRecommender`:

| Parameter | Recovered value | Evidence |
|---|---|---|
| `recommendation-margin-fraction` | **0.15** | `0x1ac7cc5 movsd … ; const=0.15` |
| `target-cpu-percentile` / `target-memory-percentile` | **0.90** / 0.90 | `0x1ac7db2`, `0x1ac7ef1` |
| lower / upper bound percentile | 0.50 / 0.95 | `0x1ac7e01`, `0x1ac7e50` |
| `cpu-` / `memory-histogram-decay-half-life`, `memory-aggregation-interval` | **24 h** (`0x4e94914f0000` ns) | `0x1aff61f`, `0x1aff5cd`, `0x1aff52d` |
| Histogram buckets | first bucket 0.01, ×1.05 growth (`0x3fa999999999999a`), max 1000, ε 1e-4 | `0x1a9be7b–8b`, `0x1a9bfb4` |
| Confidence multipliers | upper `(1.0, 1.0)`, lower `(0.001, −2.0)` | `0x1ac9685–97f2` |
| OOM bump | ×1.2, min +100 MiB | `0x1aff671`, `0x1aff6c0` |
| Min recommendation | 25 mCPU, 250 MB | `0x1ac7d14`, `0x1ac7d63` |

The binary contains no `nvidia.com/*` string, so the recommender only covers CPU and memory. Its target is **P90 of a decayed
usage histogram × 1.15**. That is essentially our A1 history rule, which matches the paper's point that Autopilot/VPA-style
percentile rules are the incumbent.

### 2. kube-scheduler: GPUs are opaque integer counts scored on requests

`noderesources.leastRequestedScore` (`0x18ad573 imul rax,rbx,0x64; idiv`) computes `(capacity − requested) × 100 / capacity`.
`mostRequestedScore` computes `requested × 100 / capacity`. Both use **requests**, and the binary has no GPU-specific string. A GPU is
an integer extended resource, so the only lever is an admission webhook that lowers `nvidia.com/gpu` for multi-GPU pods.

### 3. NVIDIA KAI scheduler: shares GPUs, but the user picks the fraction

- `common_info/resources.extractGpuAndMemoryFrom` parses the **`gpu-fraction` / `gpu-memory` annotations** with a regexp plus
  `strconv.Atoi`. That is the only source of the size.
- `gpupack.gpuOrderFn` orders GPUs by `NodeInfo.GetUsedGpuPortion` (fullest first). `gpuspread.gpuOrderFn` uses
  `1.0 − used portion` (`0x23fa8b7 const=1.0`). `gpusharingorder.nodeOrderFn` scores a node **1000.0** (`0x23fa534`) when the
  task fits on an already-shared GPU group.
- KAI has no estimator. It packs whatever fractions it is given well, but never chooses one.

### 4. HAMi: undeclared memory reserves the whole GPU

`nvidia.(*NvidiaGPUDevices).GenerateResourceRequests` (`device.go:404`) uses `101` (`0x65`) as the sentinel for "percentage
unset" (`0x15ac58e`). When neither `gpumem` nor `gpumem-percentage` is given and the configured `DefaultMemory` (`[cfg+0x54]`)
is 0, it sets **`memPercentage = 100` (`0x15ac5c4 mov eax,0x64`)**: the pod reserves the device's full memory. Cores default
to `DefaultCores` (`[cfg+0x58]`). Node and device scoring (`policy.(*NodeScore).ComputeDefaultScore`,
`(*DeviceListsScore).ComputeScore`) is `10.0 × (used/total + usedCore/totalCore + usedMem/totalMem)` (`const=10.0` at
`0x15c207d`, `0x15c1727`), feeding binpack or spread. All of it is computed on declared requests.

### 5. Volcano: the HAMi rule again, plus request-based binpack

`vgpu.resourcereqs` (`utils.go:173`) reads `volcano.sh/vgpu-number`, `vgpu-memory`, `vgpu-memory-percentage` (**default
`0x64` = 100%**, `0x1d50ac9`) and `vgpu-cores`. This is the same rule as HAMi. `binpack.calculateWeight` reads `binpack.weight`,
`binpack.cpu`, `binpack.memory` and `binpack.resources`, so scoring is again on requests.

### 6. Koordinator: a usage estimator exists, but not for GPUs

- `loadaware/estimator.estimatedUsedByResource` compares the resource name against `"cpu"` (`cmpw 0x7063` / `cmpb 0x75`) and
  `"memory"` (`cmpl 0x6f6d656d` / `cmpw 0x7972`). A zero request is estimated as **250 m** (`0xfa`) or **200 MiB**
  (`0xc800000`). Otherwise it returns `ScaledValue × factor / 100` (`cvtsi2sd; mulsd; divsd`).
- `config/v1beta3.init` stores the default factors as **cpu 85** (`0x55`) and **memory 70** (`0x46`), with a cpu usage threshold of
  65 (`0x41`).
- Any other resource falls through unestimated, so **GPU has no estimator**. The estimator is pluggable (`estimator.NewEstimator`
  looks one up by name), which makes it a ready-made socket for Model A. GPU sharing itself (`koordinator.sh/gpu-core`,
  `gpu-memory-ratio`, `gpu-partition-*`) is again request-declared.

## Gaps where Model A plugs in

| Scheduler | What sizes the GPU today | Gap | Where Model A attaches |
|---|---|---|---|
| kube-scheduler | Integer `nvidia.com/gpu` request | No fractional notion; scoring uses requests | Mutating webhook: fewer whole GPUs for multi-GPU pods only |
| KAI | User's `gpu-fraction` annotation | No sizing logic; strong packer (`gpupack`, score 1000 for an already-shared GPU group) | Webhook writes `gpu-fraction` = Model A slice; KAI packs it |
| HAMi | User's `gpumem` / `gpucores`; **100% memory if unset** | Over-reservation by default; MVF's SM and memory parts map 1:1 onto `gpucores` and `gpumem` | Webhook writes `gpumem`/`gpucores` from Model A |
| Volcano vGPU | Same as HAMi (`vgpu-memory-percentage` default 100) | Same | Same |
| Koordinator | `koordinator.sh/gpu-*` requests; usage estimator = request × 85/70% for cpu/mem only | **No GPU estimator**; fixed factors ignore workload history | Register a `ModelA` estimator via the named-estimator registry |
| VPA | Not applicable (cpu/memory only) | No GPU; no cold-start answer (needs history) | Same algorithm family; Model A's learned part covers cold starts |

None of the six uses readiness or failure risk at admission, so Model B has no counterpart in any of them.
