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
from datetime import date

from . import products
from .doses import (
    NITROGEN_KG_PER_HA,
    remaining_topdress_kg_per_ha,
    urea_topdress_kg_per_ha,
)

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


def _days_since(iso: str | None, today: date) -> int | None:
    """Whole days from an ISO date to today. None for absent or unparseable."""
    if not iso:
        return None
    try:
        then = date.fromisoformat(str(iso)[:10])
    except ValueError:
        return None
    days = (today - then).days
    return days if days >= 0 else None


def extract(profile: dict, today: date | None = None) -> dict[str, Signal]:
    """Every usable signal in the profile, keyed by name.

    A signal is omitted entirely when its value is missing or its source is
    `unavailable`. Callers therefore never have to null-check: presence in this
    dict *is* the eligibility test.

    `today` is injected rather than read from the clock so that "eleven days
    since you fertilised" is a testable statement.
    """
    today = today or date.today()
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

    # The season's whole nitrogen budget, so the card can say what a dose is a
    # fraction *of* rather than quoting a bare number. Withheld for legumes by
    # the same rule as the dose itself.
    season_n = NITROGEN_KG_PER_HA.get((crop.get("id") or "").lower())
    if season_n and rate:
        found["seasonNitrogenKgPerHa"] = Signal(
            name="seasonNitrogenKgPerHa", value=season_n,
            source="extension rate table", status=SEEDED,
        )

    _add_history(found, profile, today, crop.get("id"))

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


def _add_history(found: dict[str, Signal], profile: dict, today: date, crop_id) -> None:
    """Signals from what the farmer says they have already done to the field.

    All `reported`: nobody measured any of it, and the card says so. They earn
    their place anyway, because they are the only source for two facts no
    satellite can supply — that a dose has already been given, and that water
    is already in the ground.

    The design is a ladder, and every rung is a legitimate place to stop:

      a date alone      -> timing is right; the rate stays a general figure
      + a product       -> we know which nutrients went in, so P advice can
                           be withheld and a non-nitrogen product does not
                           trigger the nitrogen lockout
      + a quantity      -> the season's remaining nitrogen is arithmetic
                           rather than an assumption

    Nothing forces the farmer up the ladder. What is never done is inventing
    the rung above the one they answered.
    """
    reported_status = _status(profile, "fertiliserLog")

    entries = [e for e in (profile.get("fertiliserLog") or []) if isinstance(e, dict)]
    dated = [(days, e) for e in entries
             if (days := _days_since(e.get("date"), today)) is not None]

    if dated and reported_status != UNAVAILABLE:
        dated.sort(key=lambda pair: pair[0])
        newest_days, newest = dated[0]
        status = reported_status or REPORTED

        def report(name, value):
            if value is not None:
                found[name] = Signal(name=name, value=value,
                                     source="fertiliserLog", status=status)

        report("daysSinceFertiliser", newest_days)

        # The id, not the label. Which language it is spoken in is not a
        # property of what the farmer put on the field.
        report("lastFertiliserProduct", newest.get("product") or products.UNKNOWN)

        # Days since nitrogen specifically. A bag of muriate of potash three
        # days ago is not a reason to withhold urea; a bag of DAP is.
        nitrogen_days = [d for d, e in dated
                         if products.supplies_nitrogen(e.get("product"))]
        if nitrogen_days:
            report("daysSinceNitrogen", min(nitrogen_days))

        if any(products.supplies_phosphorus(e.get("product")) for _, e in dated):
            report("phosphorusApplied", "yes")

        # Sum only the entries we can actually quantify. A season where one
        # application was measured and another was a shrug gives no total at
        # all — a partial sum would understate what is in the ground, and the
        # error runs in the direction that costs the farmer a bag.
        amounts = [products.nitrogen_kg_per_ha(e.get("product"), e.get("bagsPerAcre"))
                   for _, e in dated]
        if amounts and all(a is not None for a in amounts):
            applied = round(sum(amounts), 1)
            report("nitrogenAppliedKgPerHa", applied)
            remaining = remaining_topdress_kg_per_ha(crop_id, applied)
            if remaining is not None:
                # `seeded`, not `reported`. The subtraction used the farmer's
                # own figure, but what it was subtracted from is still a
                # published season rate rather than this field's requirement.
                found["ureaRemainingKgPerHa"] = Signal(
                    name="ureaRemainingKgPerHa", value=remaining,
                    source="extension rate table", status=SEEDED,
                )

    irrigation_days = _days_since(profile.get("lastIrrigation"), today)
    if irrigation_days is not None and _status(profile, "lastIrrigation") != UNAVAILABLE:
        found["daysSinceIrrigation"] = Signal(
            name="daysSinceIrrigation", value=irrigation_days,
            source="lastIrrigation",
            status=_status(profile, "lastIrrigation") or REPORTED,
        )


def value(signals: dict[str, Signal], name: str, default=None):
    """Read a signal's value, or `default` when it was never available."""
    signal = signals.get(name)
    return signal.value if signal else default
