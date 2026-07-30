"""Session D: train XGBoost and measure it honestly. DECISION #16.

Produces four things, in increasing order of how much they hurt:
  1. random KFold vs spatial-block CV at five block sizes  (the leakage gap)
  2. feature-group ablation: age only, lith only, both      (what carries it)
  3. province-stratified AUC                                (is it a province
     discriminator or a prospectivity model?)
  4. the fitted full-data model + metrics.json

Run from the repo root:  python scripts/train_model.py
"""

import json
import sys
from pathlib import Path

import pandas as pd
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prospect import features, spatial  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "data" / "processed" / "training_table_v0.csv"
OUT_DIR = ROOT / "data" / "processed"
SEED = 42

AGE_FEATURES = ["b_age", "t_age", "age_mid"]
LITH_FEATURES = [c for c in features.FEATURE_COLUMNS if c.startswith("lith_")]

# DECISION #11 / #6: dev_stat is a trust gradient, so it becomes a weight.
# A Past Producer is ground someone actually pulled gold out of; an Occurrence
# is a report. Negatives get 1.0 -- a random point carries no such gradient.
DEV_STAT_WEIGHT = {
    "Producer": 1.0, "Past Producer": 1.0,
    "Prospect": 0.7, "Unknown": 0.5, "Occurrence": 0.4,
}


def make_model() -> XGBClassifier:
    """Deliberately small. 854 rows and 13 features cannot support depth."""
    return XGBClassifier(
        n_estimators=300, max_depth=3, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        reg_lambda=1.0, eval_metric="logloss",
        random_state=SEED, n_jobs=4,
    )


def _fmt(df: pd.DataFrame) -> str:
    show = df[["label", "n_blocks", "auc_mean", "auc_std", "ap_mean", "n_folds", "skipped"]]
    return show.to_string(index=False, float_format=lambda v: f"{v:.3f}")


def main() -> int:
    df = pd.read_csv(TABLE)
    X, y = df[features.FEATURE_COLUMNS], df["label"]
    lat, lng = df["lat"], df["lng"]
    df["province"] = spatial.fall_line_province(lat, lng)

    print(f"table: {len(df)} rows  {y.sum()} pos / {(1 - y).sum()} neg  "
          f"{len(features.FEATURE_COLUMNS)} features")
    print(f"provinces: {df['province'].value_counts().to_dict()}")
    print(f"\nbaselines: AUC 0.500 by construction, AP {y.mean():.3f} (prevalence)")

    print("\n=== 1. leakage gap: random vs spatial-block CV ===")
    sweep = spatial.block_size_sweep(make_model, X, y, lat, lng, n_splits=5, seed=SEED)
    print(_fmt(sweep))
    leaky = sweep.loc[0, "auc_mean"]
    honest = sweep.loc[sweep["block_deg"] == 0.5, "auc_mean"].iloc[0]
    print(f"\ninflation from random splits: {leaky - honest:+.3f} AUC "
          f"({leaky:.3f} -> {honest:.3f} at 0.5deg blocks)")

    print("\n=== 2. feature-group ablation (0.5deg spatial blocks) ===")
    blocks = spatial.assign_blocks(lat, lng, 0.5)
    ablation = []
    for name, cols in [("age only", AGE_FEATURES), ("lith only", LITH_FEATURES),
                       ("age + lith (full)", features.FEATURE_COLUMNS)]:
        res = spatial.cross_validate(make_model, df[cols], y, blocks, 5, SEED)
        ablation.append({"features": name, "n": len(cols), **res})
    abl = pd.DataFrame(ablation)
    print(abl[["features", "n", "auc_mean", "auc_std", "ap_mean", "n_folds"]]
          .to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    print("\n=== 3. province-stratified (0.5deg blocks, within each province) ===")
    province = {}
    for prov, sub in df.groupby("province"):
        res = spatial.cross_validate(
            make_model, sub[features.FEATURE_COLUMNS], sub["label"],
            spatial.assign_blocks(sub["lat"], sub["lng"], 0.5), 5, SEED)
        province[prov] = res
        print(f"  {prov:<14} n={len(sub):<4} pos={int(sub['label'].sum()):<4} "
              f"AUC={res['auc_mean']:.3f} +/-{res['auc_std']:.3f}  "
              f"AP={res['ap_mean']:.3f}  folds={res['n_folds']} "
              f"skipped={res['skipped']}")

    print("\n=== 4. full-data fit: feature importance ===")
    model = make_model().fit(X, y)
    imp = (pd.Series(model.feature_importances_, index=features.FEATURE_COLUMNS)
             .sort_values(ascending=False))
    for name, val in imp.items():
        print(f"  {val:.4f}  {name}")

    print("\n=== 5. DECISION #11: dev_stat as sample_weight ===")
    weights = df["dev_stat"].map(DEV_STAT_WEIGHT).fillna(1.0)
    print(f"  positive weights: "
          f"{weights[y == 1].value_counts().sort_index().to_dict()}")
    weighted = spatial.cross_validate(
        make_model, X, y, blocks, 5, SEED,
        sample_weight=weights)
    unweighted = spatial.cross_validate(make_model, X, y, blocks, 5, SEED)
    print(f"  unweighted  AUC={unweighted['auc_mean']:.3f} "
          f"+/-{unweighted['auc_std']:.3f}  AP={unweighted['ap_mean']:.3f}")
    print(f"  weighted    AUC={weighted['auc_mean']:.3f} "
          f"+/-{weighted['auc_std']:.3f}  AP={weighted['ap_mean']:.3f}")

    # "Does it move the map?" -- rank agreement between the two fitted models.
    p_unw = make_model().fit(X, y).predict_proba(X)[:, 1]
    p_wtd = make_model().fit(X, y, sample_weight=weights).predict_proba(X)[:, 1]
    rho = pd.Series(p_unw).corr(pd.Series(p_wtd), method="spearman")
    top = max(1, len(df) // 10)
    overlap = len(set(pd.Series(p_unw).nlargest(top).index)
                  & set(pd.Series(p_wtd).nlargest(top).index)) / top
    print(f"  rank agreement: Spearman rho={rho:.4f}, "
          f"top-{top} overlap={overlap:.1%}")
    print("  -> re-test on the real grid in Session E; this is points-only.")

    metrics = {
        "seed": SEED, "n_rows": len(df),
        "dev_stat_weighting": {
            "scheme": DEV_STAT_WEIGHT, "weighted": weighted,
            "unweighted": unweighted, "spearman_rho": float(rho),
            "top_decile_overlap": float(overlap),
        },
        "n_positive": int(y.sum()), "n_negative": int((1 - y).sum()),
        "features": features.FEATURE_COLUMNS,
        "baseline_ap": float(y.mean()),
        "block_sweep": sweep.to_dict(orient="records"),
        "ablation": ablation,
        "province": province,
        "importance": imp.round(5).to_dict(),
    }
    (OUT_DIR / "metrics_v0.json").write_text(json.dumps(metrics, indent=2))
    print(f"\nwrote {(OUT_DIR / 'metrics_v0.json').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
