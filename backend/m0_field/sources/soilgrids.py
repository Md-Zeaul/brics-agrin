"""Soil chemistry from ISRIC SoilGrids v2.0 — free, key-free, global.

https://rest.isric.org/soilgrids/v2.0/docs

Global coverage is exactly why this is the right pick for a nation-agnostic
architecture: onboarding a new BRICS node needs no new soil integration.

KNOWN GAP — SoilGrids models pH, nitrogen, CEC, organic carbon and texture, but
carries NO phosphorus and NO potassium. The Tech Spec's soil{ph,moisture,n,p,k}
therefore cannot be filled from remote sensing alone. `p` and `k` come back None
and must be supplied from a district Soil Health Card seed; M3's scoring has to
treat them as optional rather than assume zero.
"""

from __future__ import annotations

from ..contract import LIVE, Provenance, Soil
from ..fetch import FetchError, get_json

ENDPOINT = "https://rest.isric.org/soilgrids/v2.0/properties/query"

# SoilGrids property -> the Soil field it populates.
PROPERTY_MAP = {
    "phh2o": "ph",
    "nitrogen": "n",
    "cec": "cec",
    "soc": "soc",
    "clay": "clay",
}

DEFAULT_DEPTH = "0-5cm"

# SoilGrids is a global machine-learning model, not a sample of this field, and
# its spread is wide: pH at the demo field is mean 7.9 with a 90% interval of
# 6.2-10.3. Fetching the quantiles lets the app show that honestly instead of
# implying a precision the model does not have.
QUANTILES = ("Q0.05", "Q0.95")


def fetch_soil(
    lat: float, lng: float, depth: str = DEFAULT_DEPTH
) -> tuple[Soil, dict, Provenance]:
    """Return topsoil chemistry at the field centroid, with its uncertainty.

    SoilGrids ships integers scaled by a per-property `d_factor`; the real value
    is always `mean / d_factor` (pH*10 -> pH, cg/kg -> g/kg, and so on).

    The second return value maps each property to its 90% interval, so callers
    can show a range rather than a point estimate.
    """
    payload = get_json(
        ENDPOINT,
        {
            "lon": lng,
            "lat": lat,
            "property": list(PROPERTY_MAP),
            "depth": depth,
            "value": ["mean", *QUANTILES],
        },
        timeout=60,  # SoilGrids is slow under load; it is worth the wait
    )

    soil = parse_soil_payload(payload, depth)
    spread = parse_soil_range(payload, depth)

    provenance = Provenance(
        source=f"ISRIC SoilGrids v2.0 ({depth})",
        status=LIVE,
        note="global model prediction at 250 m, not a sample of this field; "
             "phosphorus and potassium are not modelled at all",
    )
    return soil, spread, provenance


def parse_soil_range(payload: dict, depth: str = DEFAULT_DEPTH) -> dict:
    """Map each soil property to its 90% confidence interval."""
    spread: dict[str, dict] = {}
    for layer in payload.get("properties", {}).get("layers", []):
        attribute = PROPERTY_MAP.get(layer.get("name"))
        if not attribute:
            continue

        d_factor = layer.get("unit_measure", {}).get("d_factor", 1) or 1
        for entry in layer.get("depths", []):
            if entry.get("label") != depth:
                continue
            values = entry.get("values", {})
            low, high = values.get(QUANTILES[0]), values.get(QUANTILES[1])
            if low is not None and high is not None:
                spread[attribute] = {
                    "low": round(low / d_factor, 3),
                    "high": round(high / d_factor, 3),
                }
    return spread


def parse_soil_payload(payload: dict, depth: str = DEFAULT_DEPTH) -> Soil:
    """Convert a SoilGrids response into a Soil, applying each property's d_factor."""
    layers = payload.get("properties", {}).get("layers", [])
    if not layers:
        raise FetchError("SoilGrids returned no layers for this location")

    soil = Soil()
    for layer in layers:
        attribute = PROPERTY_MAP.get(layer.get("name"))
        if not attribute:
            continue

        d_factor = layer.get("unit_measure", {}).get("d_factor", 1) or 1
        for entry in layer.get("depths", []):
            if entry.get("label") != depth:
                continue
            raw = entry.get("values", {}).get("mean")
            if raw is not None:
                setattr(soil, attribute, round(raw / d_factor, 3))

    return soil
