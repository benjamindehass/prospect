"""Disk cache for Macrostrat lookups. Key = coords rounded to 4 decimals (~11m)."""
import json
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parents[2] / "cache"
CACHE_DIR.mkdir(exist_ok=True)

def _key(lat: float, lng: float) -> Path:
    return CACHE_DIR / f"{round(lat, 4)}_{round(lng, 4)}.json"

def get(lat: float, lng: float) -> dict | None:
    p = _key(lat, lng)
    return json.loads(p.read_text()) if p.exists() else None

def put(lat: float, lng: float, result: dict) -> None:
    _key(lat, lng).write_text(json.dumps(result))