"""Deterministic tripwires for the training table. DECISION #15.

Every function here answers a question that has a right answer, and returns
a list of failure strings (empty == pass). Nothing in this module has an
opinion; that is the point. A leak either exists in the dataframe or it does
not, and `run_all` will say which.

The ordering matters: contract violations are hard failures that abort the
build, while separation warnings are advisory -- a feature can legitimately
separate the classes (old crystalline rock really does host Georgia gold),
so those get surfaced for judgement rather than silently dropped.
"""

import pandas as pd
from sklearn.metrics import roc_auc_score

#: Univariate AUC above this is suspicious enough to print loudly.
SEPARATION_WARN = 0.90


def check_feature_contract(features: list[str], blocked: dict[str, str]) -> list[str]:
    """No blocked column may appear in the declared feature list (#14)."""
    return [f"BLOCKED FEATURE IN X: {col} -- {blocked[col]}"
            for col in features if col in blocked]


def check_features_present(df: pd.DataFrame, features: list[str]) -> list[str]:
    missing = [c for c in features if c not in df.columns]
    return [f"MISSING FEATURE COLUMN: {c}" for c in missing]


def check_unique_coords(df: pd.DataFrame, precision: int = 4) -> list[str]:
    """Duplicate points leak across CV folds (#13). Must be zero post-dedupe."""
    dupes = df.round({"lat": precision, "lng": precision}).duplicated(["lat", "lng"]).sum()
    return [f"DUPLICATE COORDS: {dupes} rows share a location at {precision}dp"] if dupes else []


def check_labels(df: pd.DataFrame) -> list[str]:
    failures = []
    bad = set(df["label"].unique()) - {0, 1}
    if bad:
        failures.append(f"NON-BINARY LABELS: {sorted(bad)}")
    if df["label"].nunique() < 2:
        failures.append("SINGLE-CLASS TABLE: nothing to train against")
    return failures


def check_status(df: pd.DataFrame) -> list[str]:
    """Only OK rows belong in the training table (Session C step 1)."""
    bad = df.loc[df["status"] != "OK", "status"].value_counts().to_dict()
    return [f"NON-OK ROWS SURVIVED THE FILTER: {bad}"] if bad else []


def univariate_auc(df: pd.DataFrame, features: list[str]) -> dict[str, float]:
    """Per-feature AUC against the label, NaNs dropped pairwise.

    A feature scoring ~1.0 alone is either the single best geologic signal in
    the state or a provenance artefact. This does not distinguish the two --
    it just refuses to let either pass unnoticed.
    """
    scores = {}
    for col in features:
        pair = df[[col, "label"]].dropna()
        if pair["label"].nunique() < 2 or pair[col].nunique() < 2:
            continue
        auc = roc_auc_score(pair["label"], pair[col])
        scores[col] = max(auc, 1.0 - auc)  # direction-agnostic
    return dict(sorted(scores.items(), key=lambda kv: -kv[1]))


def check_separation(df: pd.DataFrame, features: list[str],
                     threshold: float = SEPARATION_WARN) -> list[str]:
    return [f"HIGH SINGLE-FEATURE AUC: {col} = {auc:.3f} -- confirm this is "
            f"geology and not provenance"
            for col, auc in univariate_auc(df, features).items() if auc >= threshold]


def check_nulls(df: pd.DataFrame, features: list[str]) -> list[str]:
    """Nulls are reported, not fatal: XGBoost learns a default split."""
    nulls = {c: int(df[c].isna().sum()) for c in features if df[c].isna().any()}
    return [f"NULLS PRESENT (non-fatal, XGBoost-handled): {nulls}"] if nulls else []


def run_all(df: pd.DataFrame, features: list[str],
            blocked: dict[str, str]) -> tuple[list[str], list[str]]:
    """Returns (fatal, advisory). Caller aborts on any fatal."""
    fatal = (check_feature_contract(features, blocked)
             + check_features_present(df, features)
             + check_unique_coords(df)
             + check_labels(df)
             + check_status(df))
    advisory = check_separation(df, features) + check_nulls(df, features)
    return fatal, advisory
