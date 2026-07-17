"""Macrostrat point-lookup: geologic features for a lat/lng.

Implements DECISIONS #1-#4:
  #1/#2  prefer the most specifically mapped unit via smallest age span
  #3     retry with backoff before declaring a miss
  #4     distinguish NO_COVERAGE (real absence) from FETCH_FAILED (network)
"""

import time
import requests

MACROSTRAT_URL = "https://macrostrat.org/api/geologic_units/map"


def _query(lat: float, lng: float, scale: str | None = None, timeout: int = 10) -> list:
    """One raw API call. Raises on any HTTP/network problem."""
    params = {"lat": lat, "lng": lng}
    if scale:
        params["scale"] = scale
    r = requests.get(MACROSTRAT_URL, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()["success"]["data"]


def get_geology(lat: float, lng: float, retries: int = 2) -> dict:
    """Geologic unit at a point.

    Returns a dict whose 'status' key is one of:
      OK            -> geology fields populated
      NO_COVERAGE   -> API answered; no map unit here (water, map edge)
      FETCH_FAILED  -> network/HTTP failure after all retries
    """
    for attempt in range(retries + 1):
        try:
            data = _query(lat, lng, scale="large") or _query(lat, lng)

            if not data:
                return {"status": "NO_COVERAGE"}

            # DECISION #2: smallest age span ~ most specifically mapped unit.
            # Nulls score as maximal span (4600 Myr) so undated blobs lose.
            best = min(data, key=lambda u: (u["b_age"] or 4600) - (u["t_age"] or 0))

            return {
                "status": "OK",
                "lith": best.get("lith"),
                "b_age": best.get("b_age"),
                "t_age": best.get("t_age"),
                "unit_name": best.get("name"),
                "map_source": best.get("source_id"),
            }

        except Exception:
            if attempt < retries:
                time.sleep(2 + 3 * attempt)  # DECISION #3: 2s, then 5s

    return {"status": "FETCH_FAILED"}