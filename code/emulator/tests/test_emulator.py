"""Hand-checked tests for the emulator inputs and metrics.

run: uv run --with pytest --with pandas --with pyyaml --with pyarrow pytest code/emulator/tests -q
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import build_snapshots as bs  # noqa: E402
import metrics  # noqa: E402


# ---------------- request conversion ----------------
@pytest.mark.parametrize("g,expected", [
    (0, (0, 0)), (np.nan, (0, 0)), (0.5, (1, 500)), (0.25, (1, 250)), (0.0004, (1, 1)),
    (1.0, (1, 1000)), (2.0, (2, 1000)), (1.4, (2, 1000)), (8.0, (8, 1000)), (16.0, (16, 1000)),
])
def test_gpu_ask(g, expected):
    assert bs.gpu_ask(g) == expected


def test_pod_doc_carries_type_constraint_and_cpu():
    d = bs.pod_doc("p1", 7.5, 0.5, "A10")
    ann = d["metadata"]["annotations"]
    assert ann["alibabacloud.com/gpu-milli"] == "500" and ann["alibabacloud.com/gpu-count"] == "1"
    assert ann["alibabacloud.com/gpu-card-model"] == "A10"
    assert d["spec"]["containers"][0]["resources"]["requests"]["cpu"] == "7500m"
    assert "annotations" not in bs.pod_doc("p2", 2, 0, "A10")["metadata"]   # CPU-only pod: no GPU annotations


def test_node_doc_capacity():
    n = bs.node_doc("n1", 16, 192, "H20")
    c = n["status"]["capacity"]
    assert c["alibabacloud.com/gpu-count"] == "16" and c["alibabacloud.com/gpu-milli"] == "16000"
    assert c["cpu"] == "192000m"


def test_yaml_round_trip_totals(tmp_path):
    """Exported totals match the source snapshot (CPU exactly to the milli-core, GPU after ladder rounding)."""
    rng = np.random.default_rng(0)
    gpu = rng.choice([0, 0, 0.25, 0.5, 1, 1, 2, 8], size=200)
    cpu = rng.choice([0.5, 2, 4, 7.5, 16], size=200)
    docs = [bs.pod_doc(f"p{i}", c, g, "A10") for i, (c, g) in enumerate(zip(cpu, gpu))]
    bs.dump(docs, tmp_path / "pods.yaml")
    back = list(yaml.safe_load_all(open(tmp_path / "pods.yaml")))
    cpu_back = sum(int(d["spec"]["containers"][0]["resources"]["requests"]["cpu"][:-1]) for d in back) / 1000
    gpu_back = sum(int(d["metadata"]["annotations"]["alibabacloud.com/gpu-count"]) *
                   int(d["metadata"]["annotations"]["alibabacloud.com/gpu-milli"]) / 1000
                   for d in back if "annotations" in d["metadata"])
    assert len(back) == 200
    assert cpu_back == pytest.approx(cpu.sum())
    assert gpu_back == pytest.approx(gpu.sum())          # these requests are all on the ladder: exact


# ---------------- capacity metrics ----------------
def test_fits():
    assert metrics.fits(8, 64, 8, 64) == 1
    assert metrics.fits(8, 63.9, 8, 64) == 0      # one core short: stranded by CPU
    assert metrics.fits(7, 500, 8, 64) == 0       # one GPU short: multi-GPU shortfall
    assert metrics.fits(16, 128, 2, 16) == 8
    assert metrics.fits(16, 40, 2, 16) == 2       # CPU binds


def test_summarize_hand_checked_cluster():
    # node A: 8 GPUs, 3 whole free, 0.5 residue, 20 cores  -> 1G8C fits 2 (CPU binds), 1G12C fits 1
    # node B: 2 GPUs, 2 whole free, 0 residue,   64 cores  -> 1G8C fits 2, 1G12C fits 2, 4G32C fits 0
    # node C: 16 GPUs, 0 whole free, 0.75 residue, 100 cores -> nothing fits
    s = metrics.summarize([(8, 3, 0.5, 20.0), (2, 2, 0.0, 64.0), (16, 0, 0.75, 100.0)])
    assert s["node_gpus"] == 26 and s["whole_free"] == 5
    assert s["frac_residue"] == pytest.approx(1.25)
    assert s["whole_free_cpu8"] == 2 + 2 + 0
    assert s["whole_free_cpu16"] == 1 + 2 + 0
    assert s["fit_1G8C"] == 4 and s["fit_1G12C"] == 3 and s["fit_4G32C"] == 0 and s["fit_8G64C"] == 0


def test_causes_hand_checked():
    nodes = [(8, 3, 0.5, 20.0), (2, 2, 0.0, 64.0), (16, 0, 0.75, 100.0)]
    # 1G8C: A fits 2 (1 GPU left, CPU short), B fits 2, C none -> usable 4, cpu 1, residue 1.25
    c = metrics.causes(nodes, 1, 8)
    assert c == {"usable": 4, "fractional": pytest.approx(1.25), "insufficient_cpu": 1, "multi_gpu_shortfall": 0}
    # 4G32C: no node has 4 whole GPUs -> A's 3 and B's 2 are shortfall
    c = metrics.causes(nodes, 4, 32)
    assert c["usable"] == 0 and c["multi_gpu_shortfall"] == 5 and c["insufficient_cpu"] == 0
    # parts always sum to the free capacity
    for g, cc in metrics.PROFILES:
        assert sum(metrics.causes(nodes, g, cc).values()) == pytest.approx(5 + 1.25)


def test_trace_nodes_ideal_sharing():
    df = pd.DataFrame({"gpu_count": [8, 2], "gpu_used": [5.5, 2.0], "cpu_capacity_cores": [96, 64],
                       "cpu_used": [90.0, 70.0]})
    out = list(metrics.trace_nodes(df))
    assert out[0] == (8, 2, pytest.approx(0.5), 6.0)
    assert out[1] == (2, 0, 0.0, 0.0)            # CPU over-commit is clipped at zero free


def test_sim_nodes_reads_16_devices():
    cols = {f"gpu_milli_left_{i}": [1000 if i >= 10 else (300 if i == 0 else 0)] for i in range(16)}
    df = pd.DataFrame({"gpu": [16], "cpu_milli_left": [48000], **cols})
    (n, whole, frac, cpu), = list(metrics.sim_nodes(df))
    assert (n, whole, cpu) == (16, 6, 48.0)       # devices 10-15 free: lost if only 8 columns were read
    assert frac == pytest.approx(0.3)
