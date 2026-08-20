"""Climate, thermal and terrain signals from the Earth Engine catalog.

Chosen by measured latency and resolution, not by reputation. Probed
2026-08-19 at the demo field:

    GPM IMERG v07      11 km    1 day behind    observed rainfall
    MODIS MOD11A1       1 km    2 days behind   land surface temperature
    ERA5-Land          11 km    6-8 days        soil water, radiation, ET0
    SRTM               30 m     static          elevation, slope, aspect

Deliberately NOT used, despite being obvious picks — both measured stale:
    SMAP L4 soil moisture   418 days behind
    MODIS MCD12Q2 phenology 961 days behind
    CHIRPS daily             19 days behind (fine for normals, not for "today")

COARSE PIXELS: an 11 km pixel dwarfs a 1.5 ha field, so no pixel centroid
falls inside it and reduceRegion returns null. Every coarse read is taken over
the centroid buffered to at least one pixel.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

from ..contract import LIVE, Provenance
from ..geometry import to_geojson
from .earth_engine import _initialise, earth_engine_ready

ERA5 = "ECMWF/ERA5_LAND/DAILY_AGGR"
MODIS_LST = "MODIS/061/MOD11A1"
IMERG = "NASA/GPM_L3/IMERG_V07"
SRTM = "USGS/SRTMGL1_003"

ERA5_SCALE_M = 11_000
IMERG_SCALE_M = 11_000
LST_SCALE_M = 1_000
TERRAIN_SCALE_M = 30

# Publication lag, from the latency probe. Windows start far enough back that
# the collection is never empty.
ERA5_LAG_DAYS = 10
LST_LAG_DAYS = 4

RADIATION_MIN_MJ = 5.0
RADIATION_MAX_MJ = 28.0


class ClimateUnavailable(RuntimeError):
    """Earth Engine climate layers could not be read."""


def fetch_climate(
    polygon: list[list[float]],
    today: date | None = None,
    window_days: int = 14,
) -> tuple[dict, Provenance]:
    """Read every raster climate signal for the field in one round trip.

    Each dataset is reduced server-side and the results combined into a single
    dictionary, so this costs one `getInfo` rather than four.
    """
    if not earth_engine_ready():
        raise ClimateUnavailable("no Earth Engine credentials configured")

    try:
        import ee
    except ImportError as error:  # pragma: no cover - depends on deploy env
        raise ClimateUnavailable(f"earthengine-api not installed: {error}") from error

    today = today or date.today()

    try:
        _initialise(ee)
        region = ee.Geometry(to_geojson(polygon))
        # One pixel wide at the coarsest scale, so a reduction always has data.
        coarse = region.centroid(1).buffer(ERA5_SCALE_M)

        era_end = today - timedelta(days=ERA5_LAG_DAYS)
        era_start = era_end - timedelta(days=window_days)
        era = (
            ee.ImageCollection(ERA5)
            .filterDate(str(era_start), str(era_end))
            .mean()
            .select(
                [
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "dewpoint_temperature_2m",
                    "soil_temperature_level_2",
                    "volumetric_soil_water_layer_1",
                    "volumetric_soil_water_layer_2",
                    "volumetric_soil_water_layer_3",
                    "surface_solar_radiation_downwards_sum",
                    "potential_evaporation_sum",
                ]
            )
            .reduceRegion(ee.Reducer.mean(), coarse, ERA5_SCALE_M, maxPixels=int(1e9), bestEffort=True)
        )

        lst_end = today - timedelta(days=LST_LAG_DAYS)
        lst_start = lst_end - timedelta(days=window_days)
        lst = (
            ee.ImageCollection(MODIS_LST)
            .filterDate(str(lst_start), str(lst_end))
            .select(["LST_Day_1km", "LST_Night_1km"])
            .mean()
            .multiply(0.02)
            .subtract(273.15)
            .rename(["lstDayC", "lstNightC"])
            .reduceRegion(
                ee.Reducer.mean(),
                region.centroid(1).buffer(LST_SCALE_M),
                LST_SCALE_M,
                maxPixels=int(1e9),
                bestEffort=True,
            )
        )

        # IMERG is a half-hourly rate in mm/hr; each frame covers 0.5 h.
        rain = (
            ee.ImageCollection(IMERG)
            .filterDate(str(today - timedelta(days=7)), str(today))
            .select("precipitation")
            .sum()
            .multiply(0.5)
            .rename("observedRain7dMm")
            .reduceRegion(ee.Reducer.mean(), coarse, IMERG_SCALE_M, maxPixels=int(1e9), bestEffort=True)
        )

        srtm = ee.Image(SRTM)
        terrain = (
            ee.Image.cat(
                srtm.select("elevation").rename("elevationM"),
                ee.Terrain.slope(srtm).rename("slopeDeg"),
                ee.Terrain.aspect(srtm).rename("aspectDeg"),
            ).reduceRegion(
                ee.Reducer.mean(), region, TERRAIN_SCALE_M, maxPixels=int(1e9), bestEffort=True
            )
        )

        raw = (
            ee.Dictionary({})
            .combine(era, overwrite=False)
            .combine(lst, overwrite=False)
            .combine(rain, overwrite=False)
            .combine(terrain, overwrite=False)
            .getInfo()
        )
    except Exception as error:  # EE raises a wide surface of its own errors
        raise ClimateUnavailable(f"Earth Engine climate read failed: {error}") from error

    return _shape(raw), Provenance(
        source="Earth Engine: ERA5-Land 11 km, MODIS LST 1 km, GPM IMERG 11 km, SRTM 30 m",
        status=LIVE,
        note=f"{window_days}-day means; ERA5 lags ~{ERA5_LAG_DAYS}d, LST ~{LST_LAG_DAYS}d",
    )


def _shape(raw: dict) -> dict:
    """Convert Earth Engine's SI units into the ones the contract speaks."""
    t_max = _celsius(raw.get("temperature_2m_max"))
    t_min = _celsius(raw.get("temperature_2m_min"))
    t_dew = _celsius(raw.get("dewpoint_temperature_2m"))

    radiation_mj = _scaled(raw.get("surface_solar_radiation_downwards_sum"), 1e-6)

    # ERA5 signs fluxes downward-positive, so potential evaporation is negative;
    # its magnitude in metres per day is the ET0 an agronomist expects in mm.
    et0 = _scaled(raw.get("potential_evaporation_sum"), 1000.0)
    if et0 is not None:
        et0 = abs(et0)

    return {
        "surfaceTempDayC": _round(raw.get("lstDayC")),
        "surfaceTempNightC": _round(raw.get("lstNightC")),
        "airTempMaxC": _round(t_max),
        "airTempMinC": _round(t_min),
        "soilTempC": _round(_celsius(raw.get("soil_temperature_level_2"))),
        "soilWater": {
            "0_7cm": _round(raw.get("volumetric_soil_water_layer_1"), 3),
            "7_28cm": _round(raw.get("volumetric_soil_water_layer_2"), 3),
            "28_100cm": _round(raw.get("volumetric_soil_water_layer_3"), 3),
        },
        "observedRain7dMm": _round(raw.get("observedRain7dMm")),
        "et0MmPerDay": _round(et0, 2),
        "vpdKpa": _round(_vpd_kpa(t_max, t_min, t_dew), 2),
        "radiationMjPerM2Day": _round(radiation_mj, 2),
        "radiationScore": _radiation_score(radiation_mj),
        "terrain": {
            "elevationM": _round(raw.get("elevationM"), 1),
            "slopeDeg": _round(raw.get("slopeDeg"), 2),
            "aspectDeg": _round(raw.get("aspectDeg"), 1),
        },
    }


def _vpd_kpa(t_max: float | None, t_min: float | None, t_dew: float | None) -> float | None:
    """Vapour pressure deficit — how hard the air pulls water from the crop.

    FAO-56: saturation pressure is averaged over the daily extremes, and actual
    pressure comes from the dewpoint. High VPD closes stomata and stalls growth
    even when the soil still holds water, which is why air temperature alone
    under-reads stress.
    """
    if t_max is None or t_min is None or t_dew is None:
        return None
    es = (_saturation_kpa(t_max) + _saturation_kpa(t_min)) / 2.0
    return max(0.0, es - _saturation_kpa(t_dew))


def _saturation_kpa(temp_c: float) -> float:
    return 0.6108 * math.exp(17.27 * temp_c / (temp_c + 237.3))


def _radiation_score(radiation: float | None) -> float | None:
    if radiation is None:
        return None
    span = RADIATION_MAX_MJ - RADIATION_MIN_MJ
    return round(max(0.0, min(1.0, (radiation - RADIATION_MIN_MJ) / span)), 3)


def _celsius(kelvin: float | None) -> float | None:
    return None if kelvin is None else kelvin - 273.15


def _scaled(value: float | None, factor: float) -> float | None:
    return None if value is None else value * factor


def _round(value: float | None, places: int = 1) -> float | None:
    return None if value is None else round(value, places)
