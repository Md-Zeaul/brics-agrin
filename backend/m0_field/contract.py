"""The M0 output contract — the shape every other module reads.

Tech Spec M0 returns { polygon, centroid, ndvi, soil{ph,moisture,n,p,k},
rainForecastMm }; the Data Model Spec widens it with cec, tempForecast[],
radiationScore and healthChip. This is the superset, plus per-signal
provenance so the demo can always answer "is that number live?".
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

# Provenance status values, in descending order of trustworthiness.
LIVE = "live"          # fetched from the real source this run
CACHED = "cached"      # a previous live value, reused
REPORTED = "reported"  # supplied by the farmer, e.g. from their Soil Health Card
SEEDED = "seeded"      # a district or product default, not this field
UNAVAILABLE = "unavailable"  # no source exists for this signal


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Provenance:
    """Where one signal came from, and whether to trust it on stage."""

    source: str
    status: str
    fetched_at: str = field(default_factory=utc_now_iso)
    note: str | None = None

    def to_dict(self) -> dict:
        out = {"source": self.source, "status": self.status, "fetchedAt": self.fetched_at}
        if self.note:
            out["note"] = self.note
        return out


@dataclass
class Soil:
    """Soil chemistry. `p` and `k` are Optional by necessity — see sources/soilgrids.py."""

    ph: float | None = None
    n: float | None = None          # total nitrogen, g/kg
    p: float | None = None          # phosphorus, kg/ha — not in SoilGrids
    k: float | None = None          # potassium, kg/ha — not in SoilGrids
    cec: float | None = None        # cation exchange capacity, cmol(c)/kg
    moisture: float | None = None   # root-zone wetness, 0-1
    soc: float | None = None        # soil organic carbon, g/kg
    clay: float | None = None       # %

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FieldProfile:
    """The cached substrate for M1 advisory, M3 crop scoring and M5 aggregation."""

    field_id: str
    polygon: list[list[float]]
    centroid: dict[str, float]
    area_ha: float
    soil: Soil
    # "drawn" means the farmer traced the boundary and area_ha is measured from
    # it; "pin" means we generated a default square, so area_ha is an assumption
    # echoed back rather than a finding. The app must not present them alike.
    boundary_mode: str = "pin"
    # What the farmer says is growing. M0 does not use it — the relative health
    # rule is deliberately crop-neutral — but M3 scoring will, and recording it
    # at capture time is the only moment it is cheap to ask.
    crop: dict | None = None
    ndvi: float | None = None
    ndvi_percentile: float | None = None        # rank among nearby cropland, 0-1
    neighbourhood_median_ndvi: float | None = None
    rain_forecast_mm: float | None = None       # next 24h
    rain_forecast_7d_mm: float | None = None
    temp_forecast: list[dict] = field(default_factory=list)
    radiation_score: float | None = None        # 0-1, normalised shortwave
    soil_range: dict = field(default_factory=dict)   # 90% interval per property
    climate: dict = field(default_factory=dict)      # thermal, water, atmosphere
    terrain: dict = field(default_factory=dict)      # elevation, slope, aspect
    health_chip: str = "YELLOW"
    sources: dict[str, dict] = field(default_factory=dict)
    generated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict:
        """camelCase JSON, matching the Firestore documents the app reads."""
        return {
            "fieldId": self.field_id,
            "polygon": self.polygon,
            "centroid": self.centroid,
            "areaHa": self.area_ha,
            "boundaryMode": self.boundary_mode,
            "crop": self.crop,
            "ndvi": self.ndvi,
            "ndviPercentile": self.ndvi_percentile,
            "neighbourhoodMedianNdvi": self.neighbourhood_median_ndvi,
            "soil": self.soil.to_dict(),
            "soilRange": self.soil_range,
            "climate": self.climate,
            "terrain": self.terrain,
            "rainForecastMm": self.rain_forecast_mm,
            "rainForecast7dMm": self.rain_forecast_7d_mm,
            "tempForecast": self.temp_forecast,
            "radiationScore": self.radiation_score,
            "healthChip": self.health_chip,
            "sources": self.sources,
            "generatedAt": self.generated_at,
        }
