"""M0 orchestrator — pin in, cached field profile out.

Contract (Tech Spec section 4):
    IN : { pin:{lat,lng} } or { polygon }
    OUT: { polygon, centroid, ndvi, soil{...}, rainForecastMm, ... }

Degradation is the design point. Each source is fetched independently and a
failure marks that one signal `unavailable` instead of sinking the profile —
the farmer's home screen must render even when a source is down, which is the
same property that lets the demo run on venue wifi.
"""

from __future__ import annotations

import logging

from .contract import (
    LIVE,
    REPORTED,
    SEEDED,
    UNAVAILABLE,
    FieldProfile,
    Provenance,
    Soil,
)
from .geometry import (
    DEFAULT_PLOT_HA,
    _open_ring,
    area_ha,
    centroid_of,
    is_simple,
    square_polygon_around,
)
from .health import health_chip
from .sources import nasa_power, open_meteo, soilgrids
from .sources.earth_engine import EarthEngineUnavailable, cached_ndvi, fetch_ndvi
from .sources.ee_climate import ClimateUnavailable, fetch_climate

log = logging.getLogger(__name__)


def build_field_profile(
    pin: dict | None = None,
    polygon: list[list[float]] | None = None,
    field_id: str = "field-demo",
    plot_ha: float = DEFAULT_PLOT_HA,
    fallback_ndvi: float | None = None,
    seeded_soil: dict | None = None,
    ndvi_window: tuple[str, str] | None = None,
    crop: dict | None = None,
    sowing_date: str | None = None,
) -> FieldProfile:
    """Build the profile for one field.

    `fallback_ndvi` keeps S2 alive if Earth Engine is unreachable.
    `seeded_soil` fills phosphorus/potassium, which no remote source provides.
    `ndvi_window` pins NDVI to an explicit date range instead of the live
    30-day median — pass RABI_PEAK_WINDOW to measure the wheat canopy.
    `crop` is what the farmer says is growing; M0 records it for M3 rather
    than using it, because the health rule is deliberately crop-neutral.
    `sowing_date` is likewise recorded, not used — M1 needs it to place the
    crop in its growth stage, and neither is a measurement of this field.
    """
    drawn = polygon is not None
    if polygon is None:
        if not pin:
            raise ValueError("build_field_profile needs either a pin or a polygon")
        polygon = square_polygon_around(pin["lat"], pin["lng"], plot_ha)
    elif len(_open_ring(polygon)) < 3:
        raise ValueError("a field boundary needs at least three corners")
    elif not is_simple(polygon):
        # A crossed boundary shoelaces to ~0 ha, and every per-hectare figure
        # downstream divides by it. Refuse it rather than advise on it.
        raise ValueError(
            "the boundary crosses itself; redraw it without crossing lines"
        )

    centroid = centroid_of(polygon)
    profile = FieldProfile(
        field_id=field_id,
        polygon=polygon,
        centroid=centroid,
        area_ha=area_ha(polygon),
        soil=Soil(),
        boundary_mode="drawn" if drawn else "pin",
        crop=crop or None,
        sowing_date=sowing_date or None,
    )
    profile.sources["boundary"] = Provenance(
        source="farmer-drawn polygon" if drawn else "farmer pin",
        status=LIVE,
        note="area measured from the drawn boundary"
        if drawn
        else f"no boundary drawn; area is a default {plot_ha} ha square, not a measurement",
    ).to_dict()

    if sowing_date:
        profile.sources["sowingDate"] = Provenance(
            source="farmer",
            status=REPORTED,
            note="used by M1 to place the crop in its growth stage",
        ).to_dict()

    if crop:
        profile.sources["crop"] = Provenance(
            source="farmer's own answer at capture",
            status=REPORTED,
            note="recorded for M3 crop scoring; M0's health rule is crop-neutral",
        ).to_dict()

    _apply_soil(profile, centroid, seeded_soil)
    _apply_forecast(profile, centroid)
    _apply_agroclimate(profile, centroid)
    _apply_climate(profile, polygon)
    _apply_ndvi(profile, polygon, fallback_ndvi, ndvi_window)

    chip, driver = health_chip(
        profile.ndvi,
        profile.soil.moisture,
        profile.ndvi_percentile,
        profile.neighbourhood_median_ndvi,
    )
    profile.health_chip = chip
    profile.sources["healthChip"] = Provenance(
        source="M0 rule set (health.py)", status=LIVE, note=f"driver: {driver}"
    ).to_dict()

    return profile


def _apply_soil(profile: FieldProfile, centroid: dict, seeded_soil: dict | None) -> None:
    try:
        soil, spread, provenance = soilgrids.fetch_soil(centroid["lat"], centroid["lng"])
        profile.soil = soil
        profile.soil_range = spread
        profile.sources["soil"] = provenance.to_dict()
    except Exception as error:
        log.warning("SoilGrids unavailable: %s", error)
        profile.sources["soil"] = Provenance(
            source="ISRIC SoilGrids v2.0", status=UNAVAILABLE, note=str(error)
        ).to_dict()

    # Phosphorus and potassium are not modelled by SoilGrids. A farmer's own
    # Soil Health Card beats any district average, so it is applied first and
    # labelled differently.
    if seeded_soil and seeded_soil.get("_reported"):
        for nutrient in ("p", "k"):
            if seeded_soil.get(nutrient) is not None:
                setattr(profile.soil, nutrient, seeded_soil[nutrient])
        profile.sources["soilNPK"] = Provenance(
            source="farmer's Soil Health Card",
            status=REPORTED,
            note="entered by the farmer; not independently verified",
        ).to_dict()
        return

    if seeded_soil:
        for nutrient in ("p", "k"):
            if seeded_soil.get(nutrient) is not None and getattr(profile.soil, nutrient) is None:
                setattr(profile.soil, nutrient, seeded_soil[nutrient])
        district = seeded_soil.get("_district")
        rating = seeded_soil.get("_rating") or {}
        detail = ", ".join(f"{k}: {v}" for k, v in rating.items())
        profile.sources["soilNPK"] = Provenance(
            source=f"{district} district average (seeded)" if district
                   else "district average (seeded)",
            status=SEEDED,
            note="phosphorus and potassium have no remote-sensing source"
                 + (f"; {detail}" if detail else ""),
        ).to_dict()


def _apply_forecast(profile: FieldProfile, centroid: dict) -> None:
    try:
        forecast, provenance = open_meteo.fetch_forecast(centroid["lat"], centroid["lng"])
        profile.rain_forecast_mm = forecast["rainForecastMm"]
        profile.rain_forecast_7d_mm = forecast["rainForecast7dMm"]
        profile.temp_forecast = forecast["tempForecast"]
        # Forecast ET0 was previously fetched and thrown away. Water balance is
        # rain minus ET0, so an irrigation call needs both halves.
        profile.climate["et0Forecast7dMm"] = forecast.get("et0SumMm")
        profile.sources["forecast"] = provenance.to_dict()
    except Exception as error:
        log.warning("Open-Meteo unavailable: %s", error)
        profile.sources["forecast"] = Provenance(
            source="Open-Meteo", status=UNAVAILABLE, note=str(error)
        ).to_dict()


def _apply_agroclimate(profile: FieldProfile, centroid: dict) -> None:
    try:
        agro, provenance = nasa_power.fetch_agroclimate(centroid["lat"], centroid["lng"])
        profile.soil.moisture = agro["moisture"]
        profile.radiation_score = agro["radiationScore"]
        # Previously fetched and discarded. Surface wetness governs whether it
        # is safe to sow; root-zone wetness governs whether the crop has water.
        profile.climate["surfaceWetness"] = agro.get("surfaceWetness")
        profile.climate["observedRain30dMm"] = agro.get("observedRain30dMm")
        profile.sources["agroclimate"] = provenance.to_dict()
    except Exception as error:
        log.warning("NASA POWER unavailable: %s", error)
        profile.sources["agroclimate"] = Provenance(
            source="NASA POWER", status=UNAVAILABLE, note=str(error)
        ).to_dict()


def _apply_climate(profile: FieldProfile, polygon: list) -> None:
    """Thermal, water-balance and terrain signals from the Earth Engine catalog.

    Higher resolution than the point APIs it supplements: 1 km measured surface
    temperature and 11 km rainfall and soil water, against NASA POWER's ~50 km.
    Optional by design — losing it costs detail, not the profile.
    """
    try:
        climate, provenance = fetch_climate(polygon)
    except ClimateUnavailable as error:
        log.info("Earth Engine climate unavailable: %s", error)
        profile.sources["climate"] = Provenance(
            source="Earth Engine climate layers", status=UNAVAILABLE, note=str(error)
        ).to_dict()
        return

    profile.terrain = climate.pop("terrain", {})
    profile.climate.update({k: v for k, v in climate.items() if v is not None})

    # ERA5-Land measures irradiance at 11 km against NASA POWER's ~50 km, so it
    # supersedes the coarser score when both are present.
    if climate.get("radiationScore") is not None:
        profile.radiation_score = climate["radiationScore"]

    profile.sources["climate"] = provenance.to_dict()


def _apply_ndvi(
    profile: FieldProfile,
    polygon: list,
    fallback_ndvi: float | None,
    window: tuple[str, str] | None = None,
) -> None:
    try:
        result, provenance = fetch_ndvi(polygon, window=window)
        profile.ndvi = result["ndvi"]
        profile.ndvi_percentile = result.get("percentile")
        profile.neighbourhood_median_ndvi = result.get("neighbourhoodMedian")
        profile.sources["ndvi"] = provenance.to_dict()
        return
    except EarthEngineUnavailable as error:
        log.info("Earth Engine unavailable, falling back: %s", error)
        reason = str(error)

    if fallback_ndvi is not None:
        result, provenance = cached_ndvi(fallback_ndvi, note=reason)
        profile.ndvi = result["ndvi"]
        profile.sources["ndvi"] = provenance.to_dict()
    else:
        profile.sources["ndvi"] = Provenance(
            source="Sentinel-2 via Earth Engine", status=UNAVAILABLE, note=reason
        ).to_dict()
