"""Crop growth stage, from a sowing date the farmer reported.

Stage is what makes fertiliser and irrigation advice specific: "hold nitrogen"
means something different at tillering than at grain fill. M0 measures nothing
that reveals it, so it comes from arithmetic on a date the farmer typed and an
indicative calendar for their crop.

**These calendars are approximate on purpose, and their provenance says so.**
Real duration swings with variety, sowing window, latitude and the season's own
heat — a wheat crop near Narwana and one in Rio Grande do Sul do not share a
number of days. They are good enough to say "this crop is in its vegetative
phase, not its grain fill", which is the granularity the advisory acts on, and
they are marked `seeded` so nothing downstream mistakes them for a measurement.

A crop with no calendar here returns `unknown` rather than a guess, and every
stage-dependent template is then ineligible. That is the intended behaviour: no
advice is better than advice resting on an invented stage.
"""

from __future__ import annotations

from datetime import date

ESTABLISHMENT = "establishment"  # sown, emerging, roots forming
VEGETATIVE = "vegetative"        # leaf and tiller growth
REPRODUCTIVE = "reproductive"    # booting, flowering, fruit set
FILLING = "filling"              # grain or fruit fill
MATURITY = "maturity"            # ripening through harvest
UNKNOWN = "unknown"

_ORDER = [ESTABLISHMENT, VEGETATIVE, REPRODUCTIVE, FILLING, MATURITY]

# Cumulative days after sowing at which each stage ends. Five boundaries per
# crop, in the order above; the last is the end of the season.
_CALENDARS: dict[str, tuple[int, int, int, int, int]] = {
    "wheat":         (21, 65, 95, 125, 145),
    "barley":        (20, 60, 88, 115, 130),
    "rice":          (20, 60, 85, 115, 135),
    "maize":         (15, 50, 70, 95, 110),
    "sorghum":       (15, 55, 75, 100, 115),
    "pearl_millet":  (12, 40, 55, 75, 85),
    "finger_millet": (15, 55, 75, 100, 110),
    "soybean":       (12, 45, 65, 90, 100),
    "mustard":       (15, 55, 80, 115, 130),
    "groundnut":     (12, 45, 70, 100, 115),
    "sunflower":     (12, 45, 65, 90, 100),
    "sesame":        (12, 40, 55, 78, 90),
    "chickpea":      (15, 55, 80, 105, 120),
    "lentil":        (15, 55, 78, 100, 115),
    "green_gram":    (10, 30, 42, 58, 65),
    "common_bean":   (10, 35, 50, 75, 85),
    "pigeon_pea":    (20, 90, 120, 165, 180),
    "cotton":        (15, 60, 100, 150, 170),
    "potato":        (20, 45, 65, 90, 100),
    "onion":         (20, 75, 100, 130, 140),
    "tomato":        (20, 50, 75, 105, 120),
}

# Crops whose cycle is not measured from a sowing date at all. Naming them
# explicitly separates "we chose not to" from "we forgot".
PERENNIAL = {
    "sugarcane", "banana", "mango", "citrus", "grape", "apple",
    "coffee", "tea", "cassava", "sweet_potato",
}


def days_after_sowing(sowing: str | None, today: date | None = None) -> int | None:
    """Whole days since sowing. None if the date is absent or unparseable.

    A future sowing date returns a negative number rather than None — the
    farmer has told us something true about a crop not yet in the ground, and
    the caller should treat that as its own case.
    """
    if not sowing:
        return None
    try:
        sown = date.fromisoformat(sowing[:10])
    except (ValueError, TypeError):
        return None
    return ((today or date.today()) - sown).days


def growth_stage(
    crop_id: str | None,
    sowing: str | None,
    today: date | None = None,
) -> tuple[str, int | None]:
    """Return (stage, days after sowing).

    `unknown` whenever the crop has no calendar, the date is missing, the crop
    is not yet sown, or the season has run past the calendar's end — the last
    of which usually means the field has been harvested and re-sown without
    anyone updating the date.
    """
    days = days_after_sowing(sowing, today)
    if days is None or days < 0:
        return UNKNOWN, days

    calendar = _CALENDARS.get((crop_id or "").lower())
    if calendar is None:
        return UNKNOWN, days

    for stage, boundary in zip(_ORDER, calendar):
        if days < boundary:
            return stage, days
    return UNKNOWN, days


def has_calendar(crop_id: str | None) -> bool:
    return (crop_id or "").lower() in _CALENDARS
