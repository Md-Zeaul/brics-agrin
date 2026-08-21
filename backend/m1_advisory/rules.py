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

from . import doses, products
from .signals import Signal, value
from .stage import VEGETATIVE
from .templates import TEMPLATES, Template, days_phrase

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

# How long a nitrogen application stays "recent". Three weeks is the interval
# between splits in the standard schedule, and roughly how long it takes a
# broadcast urea dose to be taken up or lost. Inside it, a second dose is not
# a smaller version of the right advice — it is the wrong advice, because the
# crop cannot use it and the farmer pays for the bag twice.
NITROGEN_LOCKOUT_DAYS = 21

# How long a fresh irrigation keeps the root zone supplied. Shorter than the
# nitrogen window and for a different reason: soil-water reanalysis lags by
# several days, so a field watered on Monday still reads dry on Wednesday and
# the deficit rule would fire on a field that is already wet.
IRRIGATION_LOCKOUT_DAYS = 4


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


def _nitrogen_is_recent(signals) -> bool:
    """Did nitrogen go on the field recently enough to hold the next dose back?

    False when the farmer told us nothing. Silence is not evidence that a field
    was fertilised, and treating it as such would withhold advice from every
    farmer who skipped the question — which is most of them, most of the time.
    """
    days = _n(signals, "daysSinceNitrogen")
    return days is not None and days < NITROGEN_LOCKOUT_DAYS


def _irrigation_is_recent(signals) -> bool:
    days = _n(signals, "daysSinceIrrigation")
    return days is not None and days < IRRIGATION_LOCKOUT_DAYS


def _season_nitrogen_spent(signals) -> bool:
    """Has the crop already had its whole season's nitrogen budget?"""
    applied = _n(signals, "nitrogenAppliedKgPerHa")
    season = _n(signals, "seasonNitrogenKgPerHa")
    return applied is not None and season is not None and applied >= season


CONDITIONS: dict[str, Condition] = {
    "irrigation.hold":
        lambda s: (_n(s, "waterBalance7dMm") or 0) >= SURPLUS_MM,
    # The farmer's own record overrides the reanalysis here. It is `reported`
    # rather than measured, and it is still the better evidence: they were
    # standing in the field.
    "irrigation.apply":
        lambda s: (_n(s, "waterBalance7dMm") or 0) <= DEFICIT_ACT_MM
                  and (_n(s, "topsoilWater") or 1.0) < DRY_TOPSOIL
                  and not _irrigation_is_recent(s),
    # Fires exactly where `irrigation.apply` would have. Suppressing the wrong
    # advice is only half the job — a card that goes quiet leaves the farmer
    # with the same question they opened the app to answer.
    "irrigation.recent":
        lambda s: _irrigation_is_recent(s)
                  and (_n(s, "waterBalance7dMm") or 0) <= DEFICIT_WATCH_MM,
    "irrigation.watch":
        lambda s: (_n(s, "waterBalance7dMm") or 0) <= DEFICIT_WATCH_MM,
    "fertiliser.hold_rain":
        lambda s: (_n(s, "rainForecastMm") or 0) >= LEACHING_RAIN_MM,
    "fertiliser.nitrogen_low":
        lambda s: (_n(s, "soilNitrogen") or 99) < LOW_NITROGEN
                  and (_n(s, "ndviPercentile") or 1.0) < 0.40
                  and not _nitrogen_is_recent(s),
    # The unadjusted rate, for a farmer who has not told us what they applied.
    # The dose signal is absent for legumes and for crops with no published
    # rate, so this is already ineligible for them; the nitrogen check stops it
    # firing on a field that has plenty.
    # It stands down the moment a quantity is known, so the two dose templates
    # can never both be eligible and the card can never quote two rates.
    "fertiliser.topdress_window":
        lambda s: (_n(s, "soilNitrogen") or 99) < HIGH_NITROGEN
                  and not _nitrogen_is_recent(s)
                  and "nitrogenAppliedKgPerHa" not in s,
    "fertiliser.next_split_due":
        lambda s: _nitrogen_is_recent(s) and not _season_nitrogen_spent(s),
    "fertiliser.topdress_adjusted":
        lambda s: not _nitrogen_is_recent(s)
                  and (_n(s, "ureaRemainingKgPerHa") or 0) > 0,
    # The budget is spent. Said whatever the stage, because "stop buying urea"
    # does not stop being true at grain fill.
    "fertiliser.season_n_complete":
        lambda s: _season_nitrogen_spent(s),
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
    # The stage gate is the whole condition: at maturity this is always the
    # right advice, whatever the weather is doing.
    "harvest.dry_down":
        lambda s: True,
    "canopy.healthy":
        lambda s: (_n(s, "ndviPercentile") or 0) >= AHEAD_OF_NEIGHBOURS,
}

SLOTS: dict[str, Slots] = {
    "irrigation.hold":
        lambda s: {"rainMm": round(_n(s, "rainForecast7dMm") or 0)},
    "irrigation.apply":
        lambda s: {
            "depthMm": doses.irrigation_depth_mm(_n(s, "waterBalance7dMm") or 0),
            "volumePerHaM3": doses.irrigation_volume_m3(
                doses.irrigation_depth_mm(_n(s, "waterBalance7dMm") or 0), 1.0),
            "topsoilPct": round((_n(s, "topsoilWater") or 0) * 100),
        },
    "irrigation.recent":
        lambda s: {"sinceDays": days_phrase(
            int(_n(s, "daysSinceIrrigation") or 0), s["__language__"])},
    "irrigation.watch":
        lambda s: {
            "deficitMm": abs(round(_n(s, "waterBalance7dMm") or 0)),
            "depthMm": doses.irrigation_depth_mm(_n(s, "waterBalance7dMm") or 0),
        },
    "fertiliser.hold_rain":
        lambda s: {"rainTomorrowMm": round(_n(s, "rainForecastMm") or 0)},
    "fertiliser.nitrogen_low":
        lambda s: {
            "behindPct": 100 - _pct_behind(s),
            "ureaKgPerHa": int(_n(s, "ureaTopdressKgPerHa") or 0),
        },
    "fertiliser.topdress_window":
        lambda s: {
            "days": days_phrase(s["__days__"] or 0, s["__language__"]),
            "ureaKgPerHa": int(_n(s, "ureaTopdressKgPerHa") or 0),
            "cropLabel": value(s, "cropLabel", "your crop"),
        },
    "fertiliser.next_split_due":
        lambda s: {
            "sinceDays": days_phrase(
                int(_n(s, "daysSinceNitrogen") or 0), s["__language__"]),
            "dueInDays": days_phrase(
                max(1, NITROGEN_LOCKOUT_DAYS - int(_n(s, "daysSinceNitrogen") or 0)),
                s["__language__"]),
            "product": products.label_in_sentence(
                value(s, "lastFertiliserProduct"), s["__language__"]),
        },
    "fertiliser.topdress_adjusted":
        lambda s: {
            "ureaKgPerHa": int(_n(s, "ureaRemainingKgPerHa") or 0),
            "appliedN": round(_n(s, "nitrogenAppliedKgPerHa") or 0),
            "seasonN": int(_n(s, "seasonNitrogenKgPerHa") or 0),
            "cropLabel": value(s, "cropLabel", "your crop"),
        },
    "fertiliser.season_n_complete":
        lambda s: {
            "appliedN": round(_n(s, "nitrogenAppliedKgPerHa") or 0),
            "seasonN": int(_n(s, "seasonNitrogenKgPerHa") or 0),
            "cropLabel": value(s, "cropLabel", "your crop"),
        },
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
    "harvest.dry_down":
        lambda s: {"days": days_phrase(s["__days__"] or 0, s["__language__"])},
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
    context["__language__"] = "en"

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
    secondary = next(
        (t for t in ranked[1:]
         if t.topic != primary.topic
         and not t.primary_only
         and not primary.conflicts_with(t)),
        None,
    )
    return primary, secondary


def render_slots(template: Template, signals, days_after_sowing=None,
                 language: str = "en") -> dict:
    context = dict(signals)
    context["__days__"] = days_after_sowing
    context["__language__"] = language
    return SLOTS[template.id](context)
