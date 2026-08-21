"""NDVI from Sentinel-2 via Google Earth Engine.

COPERNICUS/S2_SR_HARMONIZED — 10 m, ~5-day revisit, global:
https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED

This is the one M0 signal that needs credentials, and Earth Engine registration
has roughly a day of lead time. `earthengine-api` is imported lazily and any
failure is reported rather than raised, so the whole profile degrades to its
cached NDVI instead of the home screen failing to render.

NDVI = (B8 - B4) / (B8 + B4), cloud-masked, median over ~30 days, clipped to the
field polygon and reduced to a mean.
"""

from __future__ import annotations

import os
from pathlib import Path

from ..contract import CACHED, LIVE, Provenance
from ..geometry import to_geojson

COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
LOOKBACK_DAYS = 30
MAX_CLOUD_PCT = 40

# Peak wheat canopy in the Haryana Rabi season (sown Nov, harvested Apr).
# A reading taken outside this window measures whatever else is in the ground,
# so the demo narrative and the number only agree inside it.
RABI_PEAK_WINDOW = ("2026-01-15", "2026-03-15")

# How far around the field to look when judging whether it is doing well.
# Big enough for a meaningful sample of comparable farms, small enough that
# they share weather, soil and planting calendar.
NEIGHBOURHOOD_KM = 5.0

# ESA WorldCover class 40 = cropland. Global, 10 m, free in Earth Engine:
# https://developers.google.com/earth-engine/datasets/catalog/ESA_WorldCover_v200
WORLDCOVER = "ESA/WorldCover/v200"
CROPLAND_CLASS = 40

# Bit 10 = opaque cloud, bit 11 = cirrus, in the QA60 band.
_CLOUD_BIT = 1 << 10
_CIRRUS_BIT = 1 << 11


class EarthEngineUnavailable(RuntimeError):
    """Earth Engine is not configured, not approved yet, or returned nothing."""


def adc_path() -> Path:
    """Where `gcloud auth application-default login` writes its credential."""
    config = os.environ.get("CLOUDSDK_CONFIG")
    if config:
        return Path(config) / "application_default_credentials.json"
    if os.name == "nt":  # pragma: no cover - the team is on macOS
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "gcloud" / "application_default_credentials.json"
    return Path.home() / ".config" / "gcloud" / "application_default_credentials.json"


def earth_engine_ready() -> bool:
    """True when Earth Engine has some credential to initialise with.

    Three shapes count, and the third is the one that bites. `GCP_SA_JSON` is
    this repo's own variable and `GOOGLE_APPLICATION_CREDENTIALS` is the
    standard one, but `gcloud auth application-default login` — the path a
    collaborator with an IAM role uses, and the one that needs no key file
    handed around — sets no environment variable at all. It writes a file and
    says nothing.

    Missing that case fails silently rather than loudly: NDVI degrades to
    unavailable, the health chip still renders off the other signals, and
    nobody notices the satellite was never asked.
    """
    if os.environ.get("GCP_SA_JSON") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return True
    return adc_path().is_file()


def fetch_ndvi(
    polygon: list[list[float]],
    window: tuple[str, str] | None = None,
    lookback_days: int = LOOKBACK_DAYS,
    neighbourhood_km: float = NEIGHBOURHOOD_KM,
) -> tuple[dict, Provenance]:
    """Cloud-masked NDVI over the field, plus how it compares to its neighbours.

    Returns {"ndvi", "percentile", "neighbourhoodMedian", "sampleKm"}.

    `percentile` (0-1) is the share of surrounding cropland pixels with a LOWER
    NDVI than this field. It is what makes the health chip work for any crop in
    any country: a mango orchard, a rice paddy and a wheat plot all have wildly
    different absolute NDVI, but "worse than 90% of the farms around you" means
    the same thing everywhere, and self-corrects for season and weather.

    `window` is an explicit ("YYYY-MM-DD", "YYYY-MM-DD") range. Without it, the
    last `lookback_days` are used, which is the live current reading.

    Raises EarthEngineUnavailable so the caller can fall back rather than fail.
    """
    if not earth_engine_ready():
        raise EarthEngineUnavailable(
            "no Earth Engine credentials — set GCP_SA_JSON or GOOGLE_APPLICATION_CREDENTIALS"
        )

    try:
        import ee  # imported lazily: the package must work without it installed
    except ImportError as error:  # pragma: no cover - depends on deploy env
        raise EarthEngineUnavailable(f"earthengine-api not installed: {error}") from error

    try:
        _initialise(ee)

        region = ee.Geometry(to_geojson(polygon))
        if window:
            start, end = ee.Date(window[0]), ee.Date(window[1])
            described = f"{window[0]} to {window[1]}"
        else:
            end = ee.Date.fromYMD(*_today_ymd())
            start = end.advance(-lookback_days, "day")
            described = f"last {lookback_days} days"

        collection = (
            ee.ImageCollection(COLLECTION)
            .filterBounds(region)
            .filterDate(start, end)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", MAX_CLOUD_PCT))
            .map(_mask_clouds(ee))
        )

        composite = collection.median()
        ndvi_image = composite.normalizedDifference(["B8", "B4"]).rename("ndvi")

        reduced = ndvi_image.clip(region).reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=region,
            scale=10,
            maxPixels=1e9,
        )

        value = reduced.get("ndvi").getInfo()
        if value is None:
            raise EarthEngineUnavailable(
                f"no cloud-free Sentinel-2 pixels in the window ({described})"
            )

        field_ndvi = round(float(value), 3)
        context = _neighbourhood_context(
            ee, ndvi_image, region, field_ndvi, neighbourhood_km
        )

        note = f"median over {described}, clouds masked below {MAX_CLOUD_PCT}%"
        if context.get("percentile") is not None:
            note += (
                f"; ranked against cropland within {neighbourhood_km:g} km"
            )
        else:
            note += "; no neighbour comparison available"

        return (
            {"ndvi": field_ndvi, **context},
            Provenance(
                source=f"Sentinel-2 SR via Earth Engine ({COLLECTION})",
                status=LIVE,
                note=note,
            ),
        )

    except EarthEngineUnavailable:
        raise
    except Exception as error:  # EE raises a wide surface of its own errors
        raise EarthEngineUnavailable(f"Earth Engine call failed: {error}") from error


def cached_ndvi(
    value: float, note: str = "Earth Engine access pending"
) -> tuple[dict, Provenance]:
    """The Build Brief's day-1 fallback: a stored NDVI so S2 always renders."""
    return (
        {"ndvi": value, "percentile": None, "neighbourhoodMedian": None},
        Provenance(source="seeded field profile", status=CACHED, note=note),
    )


def _neighbourhood_context(
    ee, ndvi_image, region, field_ndvi: float, neighbourhood_km: float
) -> dict:
    """Where this field sits in the distribution of nearby cropland.

    Best-effort: a failure here costs the comparison, not the NDVI, so the
    profile still renders with absolute thresholds.
    """
    empty = {"percentile": None, "neighbourhoodMedian": None, "sampleKm": neighbourhood_km}
    try:
        neighbourhood = region.buffer(neighbourhood_km * 1000)

        # Compare against farmland only — water bodies and towns would drag the
        # distribution down and flatter every field near a village.
        cropland = (
            ee.ImageCollection(WORLDCOVER).first().select("Map").eq(CROPLAND_CLASS)
        )
        peers = ndvi_image.updateMask(cropland).clip(neighbourhood)

        # The share of neighbouring cropland below this field is exactly the
        # field's percentile rank — one reducer, no histogram bucketing.
        stats = ee.Image.cat(
            peers.lt(ee.Number(field_ndvi)).rename("below"),
            peers.rename("value"),
        ).reduceRegion(
            reducer=ee.Reducer.mean().combine(
                ee.Reducer.median(), sharedInputs=False
            ),
            geometry=neighbourhood,
            scale=30,  # coarser than the field read: this is a distribution
            maxPixels=1e9,
            bestEffort=True,
        ).getInfo()

        # A combined reducer with sharedInputs=False names its outputs after
        # the reducers, not the bands; accept either spelling.
        percentile = stats.get("below_mean", stats.get("mean"))
        median = stats.get("value_median", stats.get("median"))

        return {
            "percentile": round(float(percentile), 3) if percentile is not None else None,
            "neighbourhoodMedian": round(float(median), 3) if median is not None else None,
            "sampleKm": neighbourhood_km,
        }
    except Exception:  # noqa: BLE001 - context is optional by design
        return empty


_initialised = False


def _initialise(ee) -> None:
    """Authenticate with the service account and initialise Earth Engine.

    Idempotent and shared: several sources use Earth Engine and any of them may
    run first, so each calls this rather than assuming another already has.
    """
    global _initialised
    if _initialised:
        return

    service_account_json = os.environ.get("GCP_SA_JSON")
    if service_account_json and os.path.exists(os.path.expanduser(service_account_json)):
        credentials = ee.ServiceAccountCredentials(
            None, key_file=os.path.expanduser(service_account_json)
        )
        ee.Initialize(credentials, project=os.environ.get("GCP_PROJECT"))
    else:
        ee.Initialize(project=os.environ.get("GCP_PROJECT"))

    _initialised = True


def _mask_clouds(ee):
    def _apply(image):
        qa = image.select("QA60")
        clear = qa.bitwiseAnd(_CLOUD_BIT).eq(0).And(qa.bitwiseAnd(_CIRRUS_BIT).eq(0))
        return image.updateMask(clear).divide(10_000)

    return _apply


def _today_ymd() -> tuple[int, int, int]:
    from datetime import date

    today = date.today()
    return today.year, today.month, today.day
