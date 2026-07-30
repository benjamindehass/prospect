"""Session E: generate and featurize the prediction grid. DECISION #12.

    python scripts/build_grid.py                 # 0.1 deg, Georgia
    python scripts/build_grid.py --step 0.05     # finer, resumable
    python scripts/build_grid.py --state NC      # the instance is an argument

Resumable by construction: every Macrostrat answer is cached on disk
(prospect.cache), so re-running only pays for cells not yet fetched. Partial
progress is flushed to CSV every FLUSH_EVERY cells, so a killed run is not
a lost run.
"""

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prospect import cache, features, geology, grid  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STATES_ZIP = ROOT / "data" / "raw" / "cb_2023_us_state_500k.zip"
PROCESSED = ROOT / "data" / "processed"

# DECISION #17: Macrostrat answers a point query in ~20s and that latency is
# flat under concurrency (measured: 1/4/8 workers all ~21.7s per request, so
# throughput scales linearly). The bottleneck is their spatial query, not a
# rate limit. WORKERS is therefore the politeness knob -- 8 concurrent
# connections at ~0.37 req/s total, which is gentler in requests-per-second
# than the old serial loop with a 0.4s sleep would have been at normal latency.
WORKERS = 8
FLUSH_EVERY = 200


def state_polygon(code: str):
    states = gpd.read_file(STATES_ZIP)
    match = states[states["STUSPS"] == code]
    if match.empty:
        raise SystemExit(f"no state with STUSPS == {code!r}")
    return match.geometry.iloc[0]


def featurize_grid(cells: pd.DataFrame, out_path: Path,
                   workers: int = WORKERS) -> pd.DataFrame:
    """Cache-first, then fetch the remainder concurrently.

    Cache hits are resolved serially because they are local file reads; only
    misses go to the pool. A bad point costs a row, never the run (CLAUDE.md) --
    get_geology already swallows failures into FETCH_FAILED status.
    """
    rows, todo = [], []
    for cell in cells.itertuples(index=False):
        hit = cache.get(cell.lat, cell.lng)
        if hit is None:
            todo.append((cell.lat, cell.lng))
        else:
            rows.append({"lat": cell.lat, "lng": cell.lng, **hit})

    print(f"  {len(rows)} from cache, fetching {len(todo)} with "
          f"{workers} workers", flush=True)

    started, done = time.time(), 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(geology.get_geology, lat, lng): (lat, lng)
                   for lat, lng in todo}
        for future in as_completed(futures):
            lat, lng = futures[future]
            rows.append({"lat": lat, "lng": lng, **future.result()})
            done += 1
            if done % FLUSH_EVERY == 0 or done == len(todo):
                pd.DataFrame(rows).to_csv(out_path, index=False)
                elapsed = time.time() - started
                eta = (len(todo) - done) / max(done / elapsed, 1e-9) / 60
                print(f"  fetched {done}/{len(todo)}  "
                      f"{done / elapsed:.2f}/s  ETA {eta:.0f} min", flush=True)

    df = pd.DataFrame(rows)
    print(f"  statuses: {df['status'].value_counts().to_dict()}", flush=True)
    return df


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", type=float, default=0.1, help="grid step, degrees")
    ap.add_argument("--state", default="GA", help="STUSPS code")
    ap.add_argument("--workers", type=int, default=WORKERS)
    args = ap.parse_args()

    poly = state_polygon(args.state)
    cells = grid.make_grid(poly, args.step)
    raw_path = PROCESSED / f"grid_{args.state}_{args.step}_raw.csv"
    out_path = PROCESSED / f"grid_{args.state}_{args.step}.csv"

    already = sum(1 for c in cells.itertuples(index=False)
                  if cache.get(c.lat, c.lng) is not None)
    print(f"{args.state} @ {args.step}deg: {len(cells)} cells inside the polygon")
    print(f"cache: {already} known, {len(cells) - already} to fetch")

    df = featurize_grid(cells, raw_path, args.workers)

    ok = df[df["status"] == "OK"].copy()
    out = features.add_features(ok)
    out.to_csv(out_path, index=False)

    print(f"\nwrote {out_path.relative_to(ROOT)}  "
          f"{len(out)} scorable cells of {len(cells)} "
          f"({len(cells) - len(out)} dropped: no coverage / fetch failure)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
