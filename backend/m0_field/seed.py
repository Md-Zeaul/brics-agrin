"""Seeded district data — the nutrients remote sensing cannot supply.

SoilGrids models pH, nitrogen, CEC, organic carbon and texture, but neither
phosphorus nor potassium. The Tech Spec's soil{ph,moisture,n,p,k} therefore
cannot be filled from satellites alone, so P and K come from published Indian
soil-survey data, keyed by district and always marked `seeded` in provenance.

These are district averages, not field measurements. They are the right order
of magnitude for advisory banding ("phosphorus: medium") and the wrong thing to
quote as a reading from this particular field.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "seed" / "district_soil.json"

# Beyond this, the nearest district is too far away to be a fair proxy.
MAX_MATCH_KM = 150.0


@lru_cache(maxsize=1)
def _load() -> dict:
    try:
        return json.loads(SEED_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {"districts": []}


def district_for(lat: float, lng: float) -> dict | None:
    """Nearest seeded district to a point, or None if nothing is close enough."""
    districts = _load().get("districts", [])
    if not districts:
        return None

    nearest = min(
        districts,
        key=lambda d: _haversine_km(
            lat, lng, d["centroid"]["lat"], d["centroid"]["lng"]
        ),
    )
    distance = _haversine_km(
        lat, lng, nearest["centroid"]["lat"], nearest["centroid"]["lng"]
    )
    return nearest if distance <= MAX_MATCH_KM else None


def seeded_soil_for(lat: float, lng: float) -> dict | None:
    """The {p, k} to inject for this location, or None outside seeded districts."""
    district = district_for(lat, lng)
    if not district:
        return None

    soil = dict(district.get("soil", {}))
    soil["_district"] = district.get("district")
    soil["_rating"] = district.get("rating")
    return soil


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))
