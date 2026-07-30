"""Session E: score the grid and render the prospectivity map.

    python scripts/render_map.py --step 0.1 --state GA

Outputs, both committed to the repo:
    outputs/prospectivity_GA_0.1.html   interactive folium, one rect per cell
    outputs/prospectivity_GA_0.1.png    static, for the README

The model is fitted on the FULL training table here. That is correct for
producing a map and wrong for producing a metric -- the honest numbers come
from spatial CV in train_model.py (D16) and are never recomputed from this
fit. The two scripts are separate so that boundary stays obvious.
"""

import argparse
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import branca.colormap as cm  # noqa: E402
import folium  # noqa: E402
import geopandas as gpd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prospect import features, grid  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_model import make_model  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
STATES_ZIP = ROOT / "data" / "raw" / "cb_2023_us_state_500k.zip"

PALETTE = ["#2b2d42", "#3d5a80", "#98c1d9", "#f4a261", "#e63946"]


def score_grid(train: pd.DataFrame, cells: pd.DataFrame) -> pd.DataFrame:
    model = make_model().fit(train[features.FEATURE_COLUMNS], train["label"])
    out = cells.copy()
    out["prob"] = model.predict_proba(cells[features.FEATURE_COLUMNS])[:, 1]
    return out


def render_html(scored: pd.DataFrame, train: pd.DataFrame,
                step: float, path: Path) -> None:
    centre = [scored["lat"].mean(), scored["lng"].mean()]
    fmap = folium.Map(location=centre, zoom_start=7, tiles="cartodbpositron")
    ramp = cm.LinearColormap(PALETTE, vmin=0.0, vmax=1.0,
                             caption="P(gold occurrence) — spatial-CV AUC 0.86–0.92, see README")

    cells = folium.FeatureGroup(name=f"prospectivity ({step}°)")
    for row in scored.itertuples(index=False):
        folium.Rectangle(
            bounds=grid.cell_bounds(row.lat, row.lng, step),
            color=None, fill=True, fill_color=ramp(row.prob),
            fill_opacity=0.65, weight=0,
            tooltip=(f"P={row.prob:.3f}<br>{row.unit_name}<br>"
                     f"{row.lith}<br>{row.b_age}–{row.t_age} Ma"),
        ).add_to(cells)
    cells.add_to(fmap)

    known = folium.FeatureGroup(name="known gold occurrences (MRDS)", show=True)
    for row in train[train["label"] == 1].itertuples(index=False):
        folium.CircleMarker([row.lat, row.lng], radius=2, color="#111111",
                            fill=True, fill_opacity=0.9, weight=1,
                            tooltip=f"{row.site_name} ({row.dev_stat})").add_to(known)
    known.add_to(fmap)

    ramp.add_to(fmap)
    folium.LayerControl(collapsed=False).add_to(fmap)
    fmap.save(str(path))


def render_png(scored: pd.DataFrame, train: pd.DataFrame, state: str,
               step: float, path: Path) -> None:
    states = gpd.read_file(STATES_ZIP)
    outline = states[states["STUSPS"] == state]

    fig, ax = plt.subplots(figsize=(7.5, 8.5), dpi=140)
    outline.boundary.plot(ax=ax, color="#333333", linewidth=0.8, zorder=3)

    ramp = matplotlib.colors.LinearSegmentedColormap.from_list("prospect", PALETTE)

    # pcolormesh, not scatter: marker area does not track data units, so
    # scatter leaves gaps between cells at one step size and overplots at
    # another. A pivoted mesh tiles exactly, and cells outside the state
    # stay NaN rather than being drawn as zero-probability ground.
    mesh = scored.pivot_table(index="lat", columns="lng", values="prob")
    lat_edges = np.append(mesh.index.values - step / 2, mesh.index.values[-1] + step / 2)
    lng_edges = np.append(mesh.columns.values - step / 2, mesh.columns.values[-1] + step / 2)
    sc = ax.pcolormesh(lng_edges, lat_edges, np.ma.masked_invalid(mesh.values),
                       cmap=ramp, vmin=0, vmax=1, zorder=2, shading="flat")
    pos = train[train["label"] == 1]
    ax.scatter(pos["lng"], pos["lat"], s=3, c="#111111", zorder=4,
               label=f"known gold occurrences (n={len(pos)})")

    bar = fig.colorbar(sc, ax=ax, fraction=0.036, pad=0.02)
    bar.set_label("P(gold occurrence)")
    ax.set_title(f"PROSPECT v0 — modelled gold prospectivity, {state}\n"
                 f"{step}° grid ({len(scored)} cells) · XGBoost on Macrostrat "
                 f"lith + age · spatial-CV AUC 0.86–0.92", fontsize=9)
    ax.set_xlabel("longitude"); ax.set_ylabel("latitude")
    ax.legend(loc="lower left", fontsize=7, framealpha=0.9)
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", type=float, default=0.1)
    ap.add_argument("--state", default="GA")
    args = ap.parse_args()

    train = pd.read_csv(PROCESSED / "training_table_v0.csv")
    cells = pd.read_csv(PROCESSED / f"grid_{args.state}_{args.step}.csv")
    print(f"train={len(train)} rows  grid={len(cells)} cells")

    scored = score_grid(train, cells)
    OUTPUTS.mkdir(exist_ok=True)
    stem = f"prospectivity_{args.state}_{args.step}"
    scored.to_csv(PROCESSED / f"{stem}_scored.csv", index=False)

    render_html(scored, train, args.step, OUTPUTS / f"{stem}.html")
    render_png(scored, train, args.state, args.step, OUTPUTS / f"{stem}.png")

    print(f"\nprobability distribution:")
    print(scored["prob"].describe().round(3).to_string())

    # The model sees map-unit attributes, so every cell in a unit gets an
    # identical score. Ranking tied cells would be false precision, so the
    # "go look here" list is by UNIT, with the cell count behind each one.
    n_distinct = scored["prob"].round(6).nunique()
    print(f"\nresolution ceiling: {len(scored)} cells -> only {n_distinct} "
          f"distinct probabilities (see README limitation 6)")

    units = (scored.groupby(["unit_name", "lith"])
                   .agg(prob=("prob", "first"), cells=("prob", "size"),
                        lat=("lat", "median"), lng=("lng", "median"))
                   .reset_index().nlargest(8, "prob"))
    print(f"\ntop prospective map units (the 'go look here' list):")
    for r in units.itertuples(index=False):
        print(f"  P={r.prob:.3f}  {r.cells:>3} cells  centroid "
              f"{r.lat:.2f},{r.lng:.2f}  {r.unit_name}")

    units.to_csv(PROCESSED / f"{stem}_units.csv", index=False)
    print(f"\nwrote outputs/{stem}.html, outputs/{stem}.png, "
          f"and {stem}_units.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
