"""Agro-climate history from NASA POWER — free, key-free, global.

https://power.larc.nasa.gov/api/

Supplies the two signals no forecast gives us: root-zone soil wetness (the
`soil.moisture` the Tech Spec asks for, which SoilGrids cannot provide) and
observed shortwave radiation.

LATENCY — POWER daily lags real time by roughly 5 days and back-fills missing
days with the sentinel -999. Measured 2026-08-19: the last valid day was
2026-08-14. So we always request a wide window and take the most recent valid
day rather than "yesterday", which would be empty.
"""

from __future__ import annotations

from datetime import date, timedelta

from ..contract import LIVE, Provenance
from ..fetch import get_json

ENDPOINT = "https://power.larc.nasa.gov/api/temporal/daily/point"

PARAMETERS = [
    "T2M",
    "T2M_MAX",
    "ALLSKY_SFC_SW_DWN",
    "PRECTOTCORR",
    "GWETTOP",
    "GWETROOT",
]

FILL_VALUE = -999.0
LOOKBACK_DAYS = 30

# Shortwave irradiance range used to normalise radiationScore to 0-1.
RADIATION_MIN_MJ = 5.0
RADIATION_MAX_MJ = 28.0


def fetch_agroclimate(lat: float, lng: float, today: date | None = None) -> tuple[dict, Provenance]:
    """Return recent soil wetness, radiation and observed rainfall."""
    today = today or date.today()
    start = today - timedelta(days=LOOKBACK_DAYS)

    payload = get_json(
        ENDPOINT,
        {
            "parameters": ",".join(PARAMETERS),
            "community": "AG",
            "longitude": lng,
            "latitude": lat,
            "start": start.strftime("%Y%m%d"),
            "end": today.strftime("%Y%m%d"),
            "format": "JSON",
        },
        timeout=60,
    )

    series = payload.get("properties", {}).get("parameter", {})

    moisture, moisture_day = _latest_valid(series.get("GWETROOT", {}))
    surface_wetness, _ = _latest_valid(series.get("GWETTOP", {}))
    radiation = _mean_valid(series.get("ALLSKY_SFC_SW_DWN", {}))
    rain_30d = _sum_valid(series.get("PRECTOTCORR", {}))

    result = {
        "moisture": round(moisture, 3) if moisture is not None else None,
        "surfaceWetness": round(surface_wetness, 3) if surface_wetness is not None else None,
        "radiationScore": _radiation_score(radiation),
        "radiationMjPerM2Day": round(radiation, 2) if radiation is not None else None,
        "observedRain30dMm": round(rain_30d, 1) if rain_30d is not None else None,
        "observationDate": moisture_day,
    }

    note = None
    if moisture_day:
        lag = (today - date(int(moisture_day[:4]), int(moisture_day[4:6]), int(moisture_day[6:]))).days
        note = f"most recent valid observation is {lag} day(s) behind today"

    return result, Provenance(source="NASA POWER daily (AG community)", status=LIVE, note=note)


def _valid_items(series: dict) -> list[tuple[str, float]]:
    return [(k, v) for k, v in sorted(series.items()) if v is not None and v != FILL_VALUE]


def _latest_valid(series: dict) -> tuple[float | None, str | None]:
    items = _valid_items(series)
    return (items[-1][1], items[-1][0]) if items else (None, None)


def _mean_valid(series: dict) -> float | None:
    items = _valid_items(series)
    return sum(v for _, v in items) / len(items) if items else None


def _sum_valid(series: dict) -> float | None:
    items = _valid_items(series)
    return sum(v for _, v in items) if items else None


def _radiation_score(radiation: float | None) -> float | None:
    """Clamp observed irradiance onto 0-1 for M3's scoring curves."""
    if radiation is None:
        return None
    span = RADIATION_MAX_MJ - RADIATION_MIN_MJ
    return round(max(0.0, min(1.0, (radiation - RADIATION_MIN_MJ) / span)), 3)
