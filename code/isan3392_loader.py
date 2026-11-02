"""
ISAN 3392 — dataset loader.

Snowflake NUMBER columns arrive from Parquet as Python `decimal.Decimal`
objects. Left alone, D2_PLACEMENT occupies 6,214 MB in pandas; coerced, it
occupies 456 MB (13.6x smaller). Always load through `load_dataset`.

    from isan3392_loader import load_dataset, FEATURES, split_xy
    d1 = load_dataset("ISAN3392_D1_rightsizing.parquet")
    Xtr, ytr = split_xy(d1, "train", target="Y_MVF")
"""
import pandas as pd

CATEGORICAL = ["GPU_SPEC_PUBLIC", "CLUSTER_ID", "PRIORITY_CLASS",
               "MODEL_TYPE_PUBLIC", "ASW_ID"]

# Columns that are NOT features: identifiers, split labels, targets, and
# post-hoc diagnostics that are unknown at admission time.
NOT_FEATURES = {
    "POD_ID", "WORKLOAD_ID", "WL_CODE", "SPLIT", "ADM_DAY",
    "Y_MVF", "Y_READY", "Y_READY_JES_CROSSCHECK",
    "N_POD_HOURS", "N_HOURS_WITH_UTIL", "IS_CENSORED",
    "SCHEDULE_DELAY_SEC", "READY_DELAY_SEC",
}


def load_dataset(path: str) -> pd.DataFrame:
    """Read the Parquet export with memory-safe, model-ready dtypes."""
    df = pd.read_parquet(path)

    # workload id -> int codes (needed for GroupKFold; 32-char hashes are huge)
    if "WORKLOAD_ID" in df.columns:
        df["WL_CODE"] = df["WORKLOAD_ID"].astype("category").cat.codes.astype("int32")
        df = df.drop(columns=["WORKLOAD_ID"])
    df = df.drop(columns=[c for c in ("POD_ID",) if c in df.columns])

    for c in CATEGORICAL + ["SPLIT"]:
        if c in df.columns:
            df[c] = df[c].astype("category")

    # coerce Decimal/object columns to native numerics
    for c in df.columns:
        if df[c].dtype == object or str(df[c].dtype) == "str":
            conv = pd.to_numeric(df[c], errors="coerce")
            df[c] = conv.astype("float32") if conv.notna().any() else df[c].astype("category")

    for c in df.select_dtypes("float64").columns:
        df[c] = df[c].astype("float32")
    for c in df.select_dtypes("bool").columns:
        df[c] = df[c].astype("int8")
    return df


def feature_columns(df: pd.DataFrame) -> list:
    return [c for c in df.columns if c not in NOT_FEATURES]


def split_xy(df: pd.DataFrame, split: str, target: str = "Y_MVF"):
    """Return (X, y, groups) for one split. groups = workload codes."""
    sub = df[df["SPLIT"] == split]
    X = sub[feature_columns(sub)]
    y = sub[target]
    groups = sub["WL_CODE"] if "WL_CODE" in sub.columns else None
    return X, y, groups


FEATURES = feature_columns
