"""Flattening an M0 profile into the signals an advisory can reason over.

Two jobs, and the second is the one that matters.

**Flatten.** M0's profile is nested — soil chemistry here, climate there, a
water balance implied by two numbers in different places. An advisory rule
wants `waterBalance7dMm`, not a path through three dictionaries.

**Carry provenance forward.** Every M0 signal knows where it came from and
whether it is live, seeded or missing entirely. That knowledge has to survive
the flattening, because the whole point of M1's design is that the advisory
cannot assert something grounded in a signal that was never fetched. A signal
whose source is `unavailable` is not a signal with a null value here — it is
absent, and any template requiring it is ineligible.
"""

from __future__ import annotations

from dataclasses import dataclass

from .doses import urea_topdress_kg_per_ha

UNAVAILABLE = "unavailable"
SEEDED = "seeded"
REPORTED = "reported"


@dataclass(frozen=True)
class Signal:
    """One number the advisory may use, and how much it can be trusted."""

    name: str
    value: float | str
    source: str     # the M0 provenance key it came from
    status: str     # live / cached / reported / seeded / unavailable

    @property
    def is_measured(self) -> bool:
        """False for values a human typed or a district default supplied."""
        return self.status in ("live", "cached")


def _status(profile: dict, key: str) -> str:
    entry = profile.get("sources", {}).get(key)
    return entry.get("status", UNAVAILABLE) if entry else UNAVAILABLE


def extract(profile: dict) -> dict[str, Signal]:
    """Every usable signal in the profile, keyed by name.

    A signal is omitted entirely when its value is missing or its source is
    `unavailable`. Callers therefore never have to null-check: presence in this
    dict *is* the eligibility test.
    """
    climate = profile.get("climate") or {}
    soil = profile.get("soil") or {}
    terrain = profile.get("terrain") or {}
    found: dict[str, Signal] = {}

    def add(name, value, source):
        if value is None:
            return
        status = _status(profile, source)
        if status == UNAVAILABLE:
            return
        found[name] = Signal(name=name, value=value, source=source, status=status)

    # Canopy — the satellite's view, and how it ranks among the neighbours.
    add("ndvi", profile.get("ndvi"), "ndvi")
    add("ndviPercentile", profile.get("ndviPercentile"), "ndvi")
    add("neighbourhoodMedianNdvi", profile.get("neighbourhoodMedianNdvi"), "ndvi")

    # Water: what is coming, what the crop will ask for, what is in the ground.
    add("rainForecastMm", profile.get("rainForecastMm"), "forecast")
    add("rainForecast7dMm", profile.get("rainForecast7dMm"), "forecast")
    add("et0Forecast7dMm", climate.get("et0Forecast7dMm"), "forecast")
    add("et0MmPerDay", climate.get("et0MmPerDay"), "climate")
    add("observedRain7dMm", climate.get("observedRain7dMm"), "climate")
    add("observedRain30dMm", climate.get("observedRain30dMm"), "agroclimate")
    add("surfaceWetness", climate.get("surfaceWetness"), "agroclimate")

    water = climate.get("soilWater") or {}
    add("topsoilWater", water.get("0_7cm"), "climate")
    add("rootzoneWater", water.get("7_28cm"), "climate")
    add("subsoilWater", water.get("28_100cm"), "climate")

    # Atmosphere — heat and evaporative demand.
    add("airTempMaxC", climate.get("airTempMaxC"), "climate")
    add("airTempMinC", climate.get("airTempMinC"), "climate")
    add("soilTempC", climate.get("soilTempC"), "climate")
    add("vpdKpa", climate.get("vpdKpa"), "climate")
    add("radiationScore", profile.get("radiationScore"), "climate")

    # Soil chemistry. N, P and K are district defaults, not measurements —
    # `is_measured` is False for them and the card says so.
    add("soilPh", soil.get("ph"), "soil")
    add("soilCec", soil.get("cec"), "soil")
    add("soilOrganicCarbon", soil.get("soc"), "soil")
    add("soilClay", soil.get("clay"), "soil")
    add("soilNitrogen", soil.get("n"), "soilNPK")

    add("slopeDeg", terrain.get("slopeDeg"), "boundary")
    add("areaHa", profile.get("areaHa"), "boundary")

    crop = profile.get("crop") or {}
    if crop.get("label"):
        found["cropLabel"] = Signal(
            name="cropLabel", value=crop["label"], source="crop",
            status=_status(profile, "crop") or REPORTED,
        )

    # The rate for one vegetative top-dressing, kg of urea per hectare.
    #
    # Absent rather than zero for a legume or a crop with no published rate,
    # so every template that quotes a dose becomes ineligible by the same
    # mechanism as any other missing signal. Telling a chickpea grower to
    # spread urea is not a smaller mistake than telling them nothing.
    rate = urea_topdress_kg_per_ha(crop.get("id"))
    if rate:
        found["ureaTopdressKgPerHa"] = Signal(
            name="ureaTopdressKgPerHa", value=rate,
            source="extension rate table", status=SEEDED,
        )

    # Derived. The single most useful number M0 does not itself compute: over
    # the coming week, does the sky supply more water than the crop spends?
    if "rainForecast7dMm" in found and "et0Forecast7dMm" in found:
        balance = float(found["rainForecast7dMm"].value) - float(
            found["et0Forecast7dMm"].value
        )
        found["waterBalance7dMm"] = Signal(
            name="waterBalance7dMm",
            value=round(balance, 1),
            source="forecast",
            status=found["rainForecast7dMm"].status,
        )

    chip = profile.get("healthChip")
    if chip:
        found["healthChip"] = Signal(
            name="healthChip", value=chip, source="healthChip",
            status=_status(profile, "healthChip"),
        )

    return found


def value(signals: dict[str, Signal], name: str, default=None):
    """Read a signal's value, or `default` when it was never available."""
    signal = signals.get(name)
    return signal.value if signal else default
