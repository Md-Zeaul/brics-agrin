"""Weather forecast from Open-Meteo — free, key-free, global.

https://open-meteo.com/en/docs

Supplies the forward-looking half of the profile: the rain that drives M1's
"hold irrigation" advisory and the daily maxima M3 needs for its heat-stress
penalty above ~32 C. IMD can replace this per-nation without touching callers.
"""

from __future__ import annotations

from ..contract import LIVE, Provenance
from ..fetch import get_json

ENDPOINT = "https://api.open-meteo.com/v1/forecast"

DAILY_VARIABLES = [
    "precipitation_sum",
    "temperature_2m_max",
    "temperature_2m_min",
    "shortwave_radiation_sum",
    "et0_fao_evapotranspiration",
]

FORECAST_DAYS = 7


def fetch_forecast(lat: float, lng: float, days: int = FORECAST_DAYS) -> tuple[dict, Provenance]:
    """Return forecast aggregates for the field.

    `rainForecastMm` is tomorrow's total, not a rolling 24h window — the S2
    advisory copy reads "rain 22mm tomorrow", so the number must match the claim.
    """
    payload = get_json(
        ENDPOINT,
        {
            "latitude": lat,
            "longitude": lng,
            "daily": ",".join(DAILY_VARIABLES),
            "forecast_days": days,
            "timezone": "auto",
        },
    )

    daily = payload.get("daily", {})
    dates = daily.get("time", [])
    precipitation = _numeric(daily.get("precipitation_sum"), len(dates))
    max_temps = _numeric(daily.get("temperature_2m_max"), len(dates))
    min_temps = _numeric(daily.get("temperature_2m_min"), len(dates))
    et0 = _numeric(daily.get("et0_fao_evapotranspiration"), len(dates))

    temp_forecast = [
        {"date": dates[i], "maxC": max_temps[i], "minC": min_temps[i]}
        for i in range(len(dates))
    ]

    # index 0 is today; tomorrow is what the advisory speaks about
    tomorrow_rain = precipitation[1] if len(precipitation) > 1 else precipitation[0] if precipitation else None

    result = {
        "rainForecastMm": tomorrow_rain,
        "rainForecast7dMm": round(sum(p for p in precipitation if p is not None), 1) if precipitation else None,
        "tempForecast": temp_forecast,
        "et0SumMm": round(sum(e for e in et0 if e is not None), 1) if et0 else None,
    }

    return result, Provenance(source="Open-Meteo forecast API", status=LIVE)


def _numeric(values: list | None, expected: int) -> list:
    """Open-Meteo uses null for gaps; keep positional alignment with the dates."""
    if not values:
        return [None] * expected
    return values
