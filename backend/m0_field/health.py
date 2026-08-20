"""The GREEN / YELLOW / RED field-health chip shown on S2.

Two rule sets, in order of preference.

**Relative (preferred).** Rank the field's NDVI against surrounding cropland.
This is what lets one rule serve any crop in any country: a mango orchard, a
rice paddy and a wheat plot have wildly different absolute NDVI, but "worse
than most farms around you" means the same thing everywhere. It also
self-corrects for season, drought and growth stage, because the neighbours are
living through the same ones.

**Absolute (fallback).** Fixed NDVI thresholds, used only when no neighbour
comparison is available. These are tuned for wheat and are the reason the
relative rule exists — they are wrong for crops with different canopy density.

Either way, a field with a healthy canopy and no water left in the root zone is
not GREEN, so moisture can pull the chip down.
"""

from __future__ import annotations

GREEN = "GREEN"
YELLOW = "YELLOW"
RED = "RED"

# Relative thresholds: share of nearby cropland with lower NDVI.
PERCENTILE_STRESSED = 0.15   # bottom 15% of neighbouring farms
PERCENTILE_WATCH = 0.35

# Below this, a pixel is bare soil rather than a canopy. When the whole
# neighbourhood is under it the region is between seasons, and ranking fields
# against each other is ranking noise — a fallow field in Mato Grosso in August
# is not a sick field, it is an empty one.
BARE_SOIL_NDVI = 0.25

# Absolute fallback thresholds — wheat-tuned, crop-specific, last resort.
NDVI_HEALTHY = 0.55
NDVI_STRESSED = 0.35

MOISTURE_DRY = 0.25     # root-zone wetness below this is a drought signal
MOISTURE_CRITICAL = 0.15


def health_chip(
    ndvi: float | None,
    moisture: float | None = None,
    percentile: float | None = None,
    neighbourhood_median: float | None = None,
) -> tuple[str, str]:
    """Return (chip, driver). `driver` names the binding signal for the UI."""
    if neighbourhood_median is not None and neighbourhood_median < BARE_SOIL_NDVI:
        # The whole area is between crops; there is nothing to be healthy yet.
        return YELLOW, "no_active_crop"

    if percentile is not None:
        return _relative(percentile, moisture)
    return _absolute(ndvi, moisture)


def _relative(percentile: float, moisture: float | None) -> tuple[str, str]:
    if percentile < PERCENTILE_STRESSED:
        return RED, "below_neighbours"

    if moisture is not None and moisture < MOISTURE_CRITICAL:
        return RED, "soil_moisture_critical"

    if percentile < PERCENTILE_WATCH:
        return YELLOW, "trailing_neighbours"

    if moisture is not None and moisture < MOISTURE_DRY:
        return YELLOW, "soil_drying"

    return GREEN, "healthy"


def _absolute(ndvi: float | None, moisture: float | None) -> tuple[str, str]:
    if ndvi is None:
        if moisture is not None and moisture < MOISTURE_CRITICAL:
            return RED, "soil_moisture_critical"
        return YELLOW, "ndvi_unavailable"

    if ndvi < NDVI_STRESSED:
        return RED, "canopy_stress"

    if moisture is not None and moisture < MOISTURE_CRITICAL:
        return RED, "soil_moisture_critical"

    if ndvi < NDVI_HEALTHY:
        return YELLOW, "canopy_below_target"

    if moisture is not None and moisture < MOISTURE_DRY:
        return YELLOW, "soil_drying"

    return GREEN, "healthy"
