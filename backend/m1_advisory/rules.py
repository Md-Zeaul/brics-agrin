"""When each template applies, and what fills its slots.

Two things live here that deliberately do not live in `templates.py`: the copy
is an asset a product owner can rewrite without touching code, and this is the
code. Keeping them apart means a wording change never risks a logic change.

These rules are also the fallback. When Gemini is unavailable, disabled, or
returns something that fails validation, the same rules choose the template and
the farmer still gets an advisory. That is why they are written to stand alone
rather than as a sanity check on the model: on a bad day they *are* M1.

Thresholds are shared with M0 where M0 already has an opinion — the bare-soil
NDVI cutoff and the soil bands are imported, not restated, so the card and the
chip can never disagree about whether a field is fallow.
"""

from __future__ import annotations

from typing import Callable

from m0_field.health import BARE_SOIL_NDVI

from .signals import Signal, value
from .stage import VEGETATIVE
from .templates import TEMPLATES, Template

# --- Thresholds -------------------------------------------------------------

# Water balance over the coming week: forecast rain minus reference
# evapotranspiration, in mm. Positive means the sky covers the crop's demand.
SURPLUS_MM = 8.0        # comfortably more rain than the crop will use
DEFICIT_WATCH_MM = -3.0  # slightly short — worth a look, not an action
DEFICIT_ACT_MM = -15.0   # short enough to matter within days

DRY_TOPSOIL = 0.20      # volumetric water content, 0-1, in the top 7 cm

# Nitrogen washes off before uptake if heavy rain follows application.
LEACHING_RAIN_MM = 10.0

# Bands agreed with the app's own soil labelling, so the card and the profile
# never call the same number by two different names.
ALKALINE_PH = 7.8
LOW_NITROGEN = 1.0      # total N, g/kg
HIGH_NITROGEN = 2.0

# Heat that costs yield, paired with air dry enough to make it bite.
HEAT_STRESS_C = 35.0
DRY_AIR_KPA = 1.8

# A canopy that stays wet in warm weather is a fungal invitation.
WET_CANOPY = 0.55
FUNGAL_MIN_C = 18.0
FUNGAL_MAX_C = 32.0

BEHIND_NEIGHBOURS = 0.15   # bottom 15% of nearby cropland
AHEAD_OF_NEIGHBOURS = 0.50


def _n(signals, name, default=None):
    """A signal's value as a float, or `default` when absent."""
    raw = value(signals, name)
    return float(raw) if isinstance(raw, (int, float)) else default


# --- Conditions -------------------------------------------------------------

Condition = Callable[[dict], bool]
Slots = Callable[[dict], dict]


def _pct_behind(signals) -> int:
    """How many nearby farms this field is ahead of, as a percentage."""
    return round((_n(signals, "ndviPercentile") or 0.0) * 100)


CONDITIONS: dict[str, Condition] = {
    "irrigation.hold":
        lambda s: (_n(s, "waterBalance7dMm") or 0) >= SURPLUS_MM,
    "irrigation.apply":
        lambda s: (_n(s, "waterBalance7dMm") or 0) <= DEFICIT_ACT_MM
                  and (_n(s, "topsoilWater") or 1.0) < DRY_TOPSOIL,
    "irrigation.watch":
        lambda s: (_n(s, "waterBalance7dMm") or 0) <= DEFICIT_WATCH_MM,
    "fertiliser.hold_rain":
        lambda s: (_n(s, "rainForecastMm") or 0) >= LEACHING_RAIN_MM,
    "fertiliser.nitrogen_low":
        lambda s: (_n(s, "soilNitrogen") or 99) < LOW_NITROGEN
                  and (_n(s, "ndviPercentile") or 1.0) < 0.40,
    "fertiliser.topdress_window":
        lambda s: (_n(s, "soilNitrogen") or 99) < HIGH_NITROGEN,
    "protection.heat_stress":
        lambda s: (_n(s, "airTempMaxC") or 0) >= HEAT_STRESS_C
                  and (_n(s, "vpdKpa") or 0) >= DRY_AIR_KPA,
    "protection.disease_watch":
        lambda s: (_n(s, "surfaceWetness") or 0) >= WET_CANOPY
                  and FUNGAL_MIN_C <= (_n(s, "airTempMaxC") or 0) <= FUNGAL_MAX_C,
    "canopy.behind_neighbours":
        lambda s: (_n(s, "ndviPercentile") or 1.0) <= BEHIND_NEIGHBOURS,
    "canopy.no_active_crop":
        lambda s: (_n(s, "neighbourhoodMedianNdvi") or 1.0) < BARE_SOIL_NDVI,
    "soil.alkaline":
        lambda s: (_n(s, "soilPh") or 0) > ALKALINE_PH,
    "canopy.healthy":
        lambda s: (_n(s, "ndviPercentile") or 0) >= AHEAD_OF_NEIGHBOURS,
}

SLOTS: dict[str, Slots] = {
    "irrigation.hold":
        lambda s: {"rainMm": round(_n(s, "rainForecast7dMm") or 0)},
    "irrigation.apply":
        lambda s: {
            "deficitMm": abs(round(_n(s, "waterBalance7dMm") or 0)),
            "topsoilPct": round((_n(s, "topsoilWater") or 0) * 100),
        },
    "irrigation.watch":
        lambda s: {"deficitMm": abs(round(_n(s, "waterBalance7dMm") or 0))},
    "fertiliser.hold_rain":
        lambda s: {"rainTomorrowMm": round(_n(s, "rainForecastMm") or 0)},
    "fertiliser.nitrogen_low":
        lambda s: {"behindPct": 100 - _pct_behind(s)},
    "fertiliser.topdress_window":
        lambda s: {"days": s["__days__"]},
    "protection.heat_stress":
        lambda s: {"tmaxC": round(_n(s, "airTempMaxC") or 0)},
    "protection.disease_watch":
        lambda s: {},
    "canopy.behind_neighbours":
        lambda s: {"behindPct": 100 - _pct_behind(s)},
    "canopy.no_active_crop":
        lambda s: {},
    "soil.alkaline":
        lambda s: {"ph": round(_n(s, "soilPh") or 0, 1)},
    "canopy.healthy":
        lambda s: {"aheadPct": _pct_behind(s)},
}


# --- Selection --------------------------------------------------------------

def eligible(
    signals: dict[str, Signal],
    stage: str,
    days_after_sowing: int | None = None,
) -> list[Template]:
    """Every template whose signals exist, stage matches, and condition holds.

    Signals first, deliberately. A template whose required signal was never
    fetched is out before its condition is even evaluated — which is what stops
    the advisory asserting anything a source does not support.
    """
    context = dict(signals)
    context["__days__"] = days_after_sowing

    found = []
    for template in TEMPLATES:
        if any(name not in signals for name in template.requires):
            continue
        if template.stages and stage not in template.stages:
            continue
        condition = CONDITIONS.get(template.id)
        if condition is None or not condition(context):
            continue
        found.append(template)
    return found


def choose(
    signals: dict[str, Signal],
    stage: str,
    days_after_sowing: int | None = None,
) -> tuple[Template | None, Template | None]:
    """Pick the primary advisory, and one secondary from a different topic.

    The S2 card holds a situation line and up to two actions, so two is the
    honest capacity. Ranking is by urgency, then by the order templates are
    declared in — which puts water before nutrition before observation, the
    order a farmer would act in anyway.
    """
    ranked = sorted(
        eligible(signals, stage, days_after_sowing),
        key=lambda t: (-t.rank, TEMPLATES.index(t)),
    )
    if not ranked:
        return None, None

    primary = ranked[0]
    secondary = next((t for t in ranked[1:] if t.topic != primary.topic), None)
    return primary, secondary


def render_slots(template: Template, signals, days_after_sowing=None) -> dict:
    context = dict(signals)
    context["__days__"] = days_after_sowing
    return SLOTS[template.id](context)
