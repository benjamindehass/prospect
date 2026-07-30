"""Session C: build data/processed/training_table_v0.csv.

    positives_gold.csv + pseudo_absences.csv
      -> filter status == OK
      -> collapse duplicate coordinates            (DECISION #13)
      -> age + lith features                       (DECISION #8)
      -> enforce the feature contract              (DECISION #14)
      -> deterministic tripwires                   (DECISION #15)
      -> training_table_v0.csv

Run from the repo root:  python scripts/build_training_table.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prospect import checks, features  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
OUT = PROCESSED / "training_table_v0.csv"

COORD_PRECISION = 4  # ~11m, matching prospect.cache's key precision

# DECISION #6: dev_stat is a trust gradient. When several MRDS records share
# one coordinate we keep the most-attested rung, not an arbitrary first row.
DEV_STAT_RANK = {
    "Producer": 0,
    "Past Producer": 1,
    "Prospect": 2,
    "Occurrence": 3,
    "Unknown": 4,
}


def collapse_duplicate_coords(df: pd.DataFrame) -> pd.DataFrame:
    """One row per physical location. DECISION #13.

    MRDS logs a record per claim/shaft/report, so 509 gold records occupy only
    345 distinct coordinates. Those duplicates carry byte-identical Macrostrat
    features, so keeping them would (a) triple-count some ground in the loss
    and (b) put the same point in a training fold and a test fold, which is
    exactly the leak spatial CV exists to prevent.

    The multiplicity itself is real evidence, so it survives as
    n_mrds_records -- metadata for weighting, blocked from X (#14).
    """
    df = df.copy()
    df["_lat_r"] = df["lat"].round(COORD_PRECISION)
    df["_lng_r"] = df["lng"].round(COORD_PRECISION)

    counts = df.groupby(["_lat_r", "_lng_r"], dropna=False).size().rename("n_mrds_records")

    if "dev_stat" in df.columns:
        df["_rank"] = df["dev_stat"].map(DEV_STAT_RANK).fillna(len(DEV_STAT_RANK))
    else:
        df["_rank"] = 0

    kept = (df.sort_values("_rank")
              .drop_duplicates(["_lat_r", "_lng_r"], keep="first")
              .merge(counts, left_on=["_lat_r", "_lng_r"], right_index=True))

    return kept.drop(columns=["_lat_r", "_lng_r", "_rank"])


def main() -> int:
    pos = pd.read_csv(PROCESSED / "positives_gold.csv")
    neg = pd.read_csv(PROCESSED / "pseudo_absences.csv")
    print(f"loaded  positives={len(pos)}  negatives={len(neg)}")

    # Step 1 is a no-op on the current extracts (all 1018 rows are OK), but it
    # stays as code: the next Macrostrat run may not be so lucky.
    pos, neg = pos[pos["status"] == "OK"], neg[neg["status"] == "OK"]
    print(f"status==OK  positives={len(pos)}  negatives={len(neg)}")

    pos = collapse_duplicate_coords(pos)
    neg = collapse_duplicate_coords(neg)
    print(f"deduped  positives={len(pos)}  negatives={len(neg)}")

    # Same add_features the grid uses -- see features.add_features / D12.
    df = features.add_features(pd.concat([pos, neg], ignore_index=True))

    fatal, advisory = checks.run_all(df, features.FEATURE_COLUMNS,
                                     features.BLOCKED_FROM_FEATURES)
    for msg in advisory:
        print(f"  [advisory] {msg}")
    if fatal:
        for msg in fatal:
            print(f"  [FATAL] {msg}", file=sys.stderr)
        print("aborting: training table not written", file=sys.stderr)
        return 1

    ordered = [c for c in df.columns if c not in features.FEATURE_COLUMNS] + features.FEATURE_COLUMNS
    df[ordered].to_csv(OUT, index=False)

    print(f"\nwrote {OUT.relative_to(ROOT)}  rows={len(df)}  features={len(features.FEATURE_COLUMNS)}")
    print(f"class balance: {df['label'].value_counts().to_dict()}")
    print("\nunivariate AUC (direction-agnostic):")
    for col, auc in checks.univariate_auc(df, features.FEATURE_COLUMNS).items():
        print(f"  {auc:.3f}  {col}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
