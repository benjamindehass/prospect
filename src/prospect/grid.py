"""Prediction grid over an arbitrary state polygon. DECISION #12.

No state-specific logic lives here: callers pass a polygon. Georgia is an
instance (CLAUDE.md), so `build_grid.py` is where "GA" appears, not this file.

Grids are snapped to a global origin at (0, 0) so that a coarse grid is a
strict SUBSET of a finer one at any step that divides it -- 0.1deg points are
also 0.05deg points. That makes the Macrostrat cache compound across runs
instead of being thrown away when the resolution changes.
"""

import numpy as np
import pandas as pd
import shapely


def make_grid(polygon, step_deg: float) -> pd.DataFrame:
    """Cell centres inside `polygon`, snapped to a global origin.

    Returns lat/lng rounded to 4dp to match prospect.cache's key precision --
    otherwise float drift produces cache misses for the same physical point.
    """
    minx, miny, maxx, maxy = polygon.bounds
    lngs = np.arange(np.floor(minx / step_deg) * step_deg,
                     maxx + step_deg, step_deg)
    lats = np.arange(np.floor(miny / step_deg) * step_deg,
                     maxy + step_deg, step_deg)

    mesh_lng, mesh_lat = np.meshgrid(lngs, lats)
    flat_lng, flat_lat = mesh_lng.ravel(), mesh_lat.ravel()

    inside = shapely.contains_xy(polygon, flat_lng, flat_lat)
    return pd.DataFrame({
        "lat": np.round(flat_lat[inside], 4),
        "lng": np.round(flat_lng[inside], 4),
    }).drop_duplicates(["lat", "lng"]).reset_index(drop=True)


def cell_bounds(lat: float, lng: float, step_deg: float) -> list[list[float]]:
    """[[south, west], [north, east]] for drawing a cell as a rectangle."""
    half = step_deg / 2.0
    return [[lat - half, lng - half], [lat + half, lng + half]]
