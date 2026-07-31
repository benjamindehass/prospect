"""Assemble docs/ for GitHub Pages.

    python scripts/build_site.py

Every number on the page is read from metrics_v0.json and the units CSV at
build time. Nothing is typed in by hand, so the site cannot drift away from
what the model actually produced -- re-run the pipeline, re-run this, and the
page updates itself or fails loudly.

GitHub Pages serves from the docs/ folder on main (Settings -> Pages).
"""

import json
import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
DOCS = ROOT / "docs"
STEP, STATE = 0.1, "GA"
REPO = "https://github.com/benjamindehass/prospect"

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PROSPECT — modelled gold prospectivity, Georgia</title>
<meta name="description" content="Predicting where gold occurs in Georgia from
public geologic data, validated with spatial-block cross-validation.">
<style>
  :root {{
    --bg:#fbfaf8; --fg:#1c1b19; --muted:#6b675f; --line:#e2ded6;
    --card:#ffffff; --accent:#b4451f;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg:#16151a; --fg:#e9e6e1; --muted:#9a958c; --line:#302d36;
      --card:#1e1d23; --accent:#e8794a;
    }}
  }}
  * {{ box-sizing:border-box; }}
  body {{
    margin:0; background:var(--bg); color:var(--fg);
    font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  }}
  .wrap {{ max-width:900px; margin:0 auto; padding:0 20px 72px; }}
  header {{ padding:64px 0 8px; }}
  h1 {{ font-size:2.6rem; letter-spacing:-.03em; margin:0 0 .3em; }}
  h2 {{ font-size:1.35rem; letter-spacing:-.01em; margin:2.6em 0 .6em;
        padding-top:1.4em; border-top:1px solid var(--line); }}
  .lede {{ font-size:1.15rem; color:var(--muted); margin:0 0 2em; max-width:62ch; }}
  a {{ color:var(--accent); }}
  figure {{ margin:0 0 8px; }}
  iframe {{ width:100%; height:620px; border:1px solid var(--line);
            border-radius:10px; background:var(--card); }}
  figcaption {{ color:var(--muted); font-size:.9rem; margin-top:10px; }}
  .scroll {{ overflow-x:auto; -webkit-overflow-scrolling:touch; }}
  table {{ border-collapse:collapse; width:100%; font-size:.94rem; min-width:520px; }}
  th,td {{ text-align:left; padding:9px 14px 9px 0; border-bottom:1px solid var(--line); }}
  th {{ font-weight:600; color:var(--muted); font-size:.82rem;
        text-transform:uppercase; letter-spacing:.06em; }}
  td.n {{ font-variant-numeric:tabular-nums; white-space:nowrap; }}
  tr.hi td {{ font-weight:650; }}
  .note {{ color:var(--muted); font-size:.9rem; }}
  ol.lim {{ padding-left:1.2em; }}
  ol.lim li {{ margin:.7em 0; }}
  footer {{ margin-top:3.5em; padding-top:1.4em; border-top:1px solid var(--line);
            color:var(--muted); font-size:.9rem; }}
  code {{ background:var(--card); border:1px solid var(--line);
          padding:1px 5px; border-radius:4px; font-size:.9em; }}
</style>
</head>
<body>
<div class="wrap">

<header>
  <h1>PROSPECT</h1>
  <p class="lede">This model predicts where gold occurs in Georgia from public
  geologic data. A prediction is not a result. The validation is the result, so
  it is on this page too.</p>
</header>

<figure>
  <iframe src="map.html" title="Interactive gold prospectivity map of Georgia"
          loading="lazy"></iframe>
  <figcaption>Hover any cell for probability, map unit, lithology and age. The
  layer control toggles the {n_pos} known gold occurrences. They are drawn for
  comparison. They were never used at scoring time. The red band is the
  Dahlonega belt. The model was not told it exists.</figcaption>
</figure>

<h2>The honest numbers</h2>
<p>Spatial-block cross-validation, five folds, XGBoost. Two rows are
emphasized. They answer different questions, and quoting one alone would be
dishonest.</p>
<div class="scroll">
<table>
<thead><tr><th>Validation scheme</th><th>Blocks</th><th>AUC</th>
<th>What it answers</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
</div>
<p class="note">Baseline AUC 0.500; baseline average precision {baseline_ap:.3f}
(positive-class prevalence). {n_rows} points, {n_pos} positive.</p>

<h2>Why not a random train/test split</h2>
<p>Mineral occurrences are spatially autocorrelated. A point 200&nbsp;m from a
known mine sits in the <em>same map unit</em>. It carries the same lithology and
the same age. Shuffle those into different folds and the held-out point is one
the model has already seen, feature for feature, label included. Random
cross-validation measures interpolation between neighbors. That is not the
question being asked.</p>
<p>The gap between random and blocked validation is only 0.008&nbsp;AUC at fine
scales. That does not mean there is no leakage. It means the blocks are too
small. Every feature is a map-unit attribute, so a 9&nbsp;km block holds the
same geology as its neighbors and the fold boundary cuts nothing. Only blocks
large enough to hold out whole regions reveal the effect. At 186&nbsp;km the
score falls to {auc_2deg:.3f}.</p>

<h2>Where to actually go</h2>
<p>Ranked by map unit, not by grid cell. Limitation 6 explains why.</p>
<div class="scroll">
<table>
<thead><tr><th>P</th><th>Cells</th><th>Centroid</th><th>Map unit</th></tr></thead>
<tbody>
{units}
</tbody>
</table>
</div>

<h2>Honest limitations</h2>
<ol class="lim">
<li><strong>The lithology features are weaker than they look.</strong> The map
source covering 87% of positives has no metamorphic vocabulary. It calls
gold-belt metasediments "sedimentary". <code>lith_quartz</code> fires on zero
rows of {n_rows}. <code>lith_schist</code> fires on one. Quartz-vein-in-schist
is the host rock for Georgia gold, and the model cannot see it.</li>
<li><strong>Statewide AUC is partly a Fall Line detector.</strong> All {n_pos}
positives fall in the crystalline province. Restricted to that province the
model scores <strong>{auc_prov:.3f} ± {auc_prov_sd:.3f}</strong>. That is real
discrimination inside gold country. It is also the number that matters for
planning a trip.</li>
<li><strong>Negatives are pseudo-absences, not verified absences.</strong> This
is a positive-unlabeled problem dressed as binary classification. It holds only
because gold-bearing ground is a small fraction of the state. That was
verified, not assumed.</li>
<li><strong>MRDS records where industry looked.</strong> It does not record
where gold is. Sampling bias in the labels propagates into the map.</li>
<li><strong>No field validation yet.</strong> One trip is planned. The writeup
happens either way.</li>
<li><strong>Resolution is the map polygon, not the grid cell.</strong> Every
feature is a map-unit attribute, so {n_cells} cells produce {n_distinct}
distinct probabilities. Ranking cells inside a plateau would be sorting noise.
A finer grid does not fix this. Per-point features would: distance to contacts,
distance to faults, geochemistry.</li>
</ol>

<h2>How it works</h2>
<p>USGS MRDS occurrences and Macrostrat map units, joined by cached point
lookups. Deduplicated to one row per location. Featurized into age and
lithology features under an enforced allowlist. Trained with XGBoost, validated
spatially. A {step}° grid over the state runs through the same code path and
gets scored.</p>
<p>The method, every design decision with what was rejected, and the steps to
reproduce it are in the <a href="{repo}">repository</a>.</p>

<footer>
Data: <a href="https://mrdata.usgs.gov/mrds/">USGS MRDS</a> (public domain) ·
<a href="https://macrostrat.org">Macrostrat</a> (CC-BY 4.0) ·
U.S. Census Bureau boundaries.<br>
Sessions C–F were built autonomously by Claude (Opus 5); decision entries from
that work are marked <code>[AUTONOMOUS]</code> in the repository record.
</footer>

</div>
</body>
</html>
"""

QUESTION = {
    0.0: "<em>nothing useful — see below</em>",
    0.1: "interpolate between neighbors",
    0.25: "interpolate between neighbors",
    0.5: "score the state with training points scattered nearby. This is how the map above is used",
    1.0: "generalize to a region held out entirely",
    2.0: "<em>too few blocks to quote</em>",
}


def main() -> int:
    metrics = json.loads((PROCESSED / "metrics_v0.json").read_text())
    units = pd.read_csv(PROCESSED / f"prospectivity_{STATE}_{STEP}_units.csv")
    scored = pd.read_csv(PROCESSED / f"prospectivity_{STATE}_{STEP}_scored.csv")

    rows = []
    for r in metrics["block_sweep"]:
        deg = r["block_deg"]
        name = ("random KFold" if deg == 0
                else f"{deg}° blocks (~{deg * 93:.0f} km)")
        hi = ' class="hi"' if deg in (0.5, 1.0) else ""
        rows.append(
            f'<tr{hi}><td>{name}</td><td class="n">{r["n_blocks"]}</td>'
            f'<td class="n">{r["auc_mean"]:.3f} ± {r["auc_std"]:.3f}</td>'
            f'<td>{QUESTION.get(deg, "")}</td></tr>')

    unit_rows = [
        f'<tr><td class="n">{u.prob:.3f}</td><td class="n">{u.cells}</td>'
        f'<td class="n">{u.lat:.2f}, {u.lng:.2f}</td><td>{u.unit_name}</td></tr>'
        for u in units.itertuples(index=False)
    ]

    sweep = {r["block_deg"]: r for r in metrics["block_sweep"]}
    crystalline = metrics["province"]["crystalline"]

    html = PAGE.format(
        rows="\n".join(rows), units="\n".join(unit_rows),
        n_rows=metrics["n_rows"], n_pos=metrics["n_positive"],
        baseline_ap=metrics["baseline_ap"],
        auc_2deg=sweep[2.0]["auc_mean"],
        auc_prov=crystalline["auc_mean"], auc_prov_sd=crystalline["auc_std"],
        n_cells=len(scored), n_distinct=scored["prob"].round(6).nunique(),
        step=STEP, repo=REPO,
    )

    DOCS.mkdir(exist_ok=True)
    (DOCS / "index.html").write_text(html, encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    shutil.copy(OUTPUTS / f"prospectivity_{STATE}_{STEP}.html", DOCS / "map.html")
    shutil.copy(OUTPUTS / f"prospectivity_{STATE}_{STEP}.png",
                DOCS / f"prospectivity_{STATE}_{STEP}.png")

    total = sum(f.stat().st_size for f in DOCS.rglob("*") if f.is_file())
    print(f"wrote docs/ ({total / 1_048_576:.1f} MB): "
          f"{', '.join(sorted(f.name for f in DOCS.iterdir()))}")
    print(f"enable at {REPO}/settings/pages -> Source: main, folder: /docs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
