"""Spatial cross-validation. DECISION #16.

Why not random KFold. Mineral occurrences are spatially autocorrelated: a
point 200m from a known gold mine sits in the same map unit, so it carries
the same lith and the same b_age. Shuffle those into different folds and the
test set is not held out in any meaningful sense — the model has already seen
that exact feature vector with that exact label. Random CV then reports how
well the model interpolates between neighbours, which is not the question.
The question is whether it generalises to ground nobody has walked.

Spatial-block CV answers that question: tile the state, assign whole blocks
to folds, so every test point is separated from every training point by at
least the block edge. The honest number is always lower, and the GAP between
random and blocked CV is itself the measurement — it is how much of the
apparent skill was spatial memorisation.

Block size is the knob and there is no single right answer, so
`block_size_sweep` reports the whole curve rather than defending one value.

Also here: `fall_line_province`, splitting Georgia into its two geologic
provinces, used to ask whether the model discriminates WITHIN gold country
or merely separates gold country from the Coastal Plain.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold, KFold

# Georgia's Fall Line, the Piedmont / Coastal Plain contact, approximated as a
# straight line through Columbus and Augusta. A real boundary is a mapped
# contact, not a chord -- but it is independent of every model feature, which
# is what makes it usable as a province label here.
_FALL_LINE = ((32.47, -84.99), (33.47, -81.97))  # (lat, lng) Columbus, Augusta


def fall_line_province(lat: pd.Series, lng: pd.Series) -> pd.Series:
    """'crystalline' (Piedmont/Blue Ridge, north) or 'coastal_plain' (south)."""
    (lat1, lng1), (lat2, lng2) = _FALL_LINE
    # Sign of the cross product of the line vector with the point vector.
    side = (lng2 - lng1) * (lat - lat1) - (lat2 - lat1) * (lng - lng1)
    return pd.Series(np.where(side > 0, "crystalline", "coastal_plain"), index=lat.index)


def assign_blocks(lat: pd.Series, lng: pd.Series, size_deg: float) -> pd.Series:
    """Label each point with the spatial block that owns it."""
    return (np.floor(lat / size_deg).astype(int).astype(str) + "_"
            + np.floor(lng / size_deg).astype(int).astype(str))


def _score(y_true, y_prob) -> dict[str, float]:
    return {"auc": roc_auc_score(y_true, y_prob),
            "ap": average_precision_score(y_true, y_prob)}


def cross_validate(model_fn, X: pd.DataFrame, y: pd.Series,
                   groups: pd.Series | None = None,
                   n_splits: int = 5, seed: int = 42,
                   sample_weight: pd.Series | None = None) -> dict:
    """Run CV. groups=None -> random KFold (the dishonest baseline).

    sample_weight, if given, is sliced to the training side only: weighting
    the test side would change what the metric means fold to fold.

    Folds whose test side is single-class are skipped and counted, not
    silently averaged over: with large blocks that genuinely happens, and
    hiding it would overstate how many folds backed the mean.
    """
    if groups is None:
        splitter = KFold(n_splits=n_splits, shuffle=True, random_state=seed)
        split = splitter.split(X)
    else:
        n = min(n_splits, groups.nunique())
        split = GroupKFold(n_splits=n).split(X, y, groups)

    rows, skipped = [], 0
    for train_idx, test_idx in split:
        y_test = y.iloc[test_idx]
        if y_test.nunique() < 2:
            skipped += 1
            continue
        model = model_fn()
        if sample_weight is None:
            model.fit(X.iloc[train_idx], y.iloc[train_idx])
        else:
            model.fit(X.iloc[train_idx], y.iloc[train_idx],
                      sample_weight=sample_weight.iloc[train_idx])
        prob = model.predict_proba(X.iloc[test_idx])[:, 1]
        rows.append(_score(y_test, prob))

    if not rows:
        return {"auc_mean": float("nan"), "auc_std": float("nan"),
                "ap_mean": float("nan"), "n_folds": 0, "skipped": skipped}

    auc = [r["auc"] for r in rows]
    return {"auc_mean": float(np.mean(auc)), "auc_std": float(np.std(auc)),
            "ap_mean": float(np.mean([r["ap"] for r in rows])),
            "n_folds": len(rows), "skipped": skipped}


def block_size_sweep(model_fn, X: pd.DataFrame, y: pd.Series,
                     lat: pd.Series, lng: pd.Series,
                     sizes: tuple[float, ...] = (0.1, 0.25, 0.5, 1.0, 2.0),
                     n_splits: int = 5, seed: int = 42) -> pd.DataFrame:
    """AUC as a function of block size, with random KFold as row zero."""
    out = [{"block_deg": 0.0, "n_blocks": len(X), "label": "random KFold (leaky)",
            **cross_validate(model_fn, X, y, None, n_splits, seed)}]
    for size in sizes:
        blocks = assign_blocks(lat, lng, size)
        out.append({"block_deg": size, "n_blocks": blocks.nunique(),
                    "label": f"spatial blocks {size}deg (~{size * 93:.0f}km)",
                    **cross_validate(model_fn, X, y, blocks, n_splits, seed)})
    return pd.DataFrame(out)
