"""Turning a recommendation into a quantity a farmer can act on.

"Plan a nitrogen top-dressing" is not an instruction. "Spread 90 kg of urea per
hectare, then irrigate lightly" is. This module holds the arithmetic that gets
from one to the other, and the three honesty constraints around it.

**The rates are general, and marked `seeded` wherever they surface.** They are
the widely-published season recommendations extension services start from, not
a prescription for one field. Variety, previous crop, organic matter and what
was already applied all move them. The copy that renders them says so, and the
card repeats it whenever the advice rests on defaults.

**Legumes are never told to top-dress nitrogen.** Soybean, chickpea, lentil,
groundnut and the rest fix their own through root nodules; urea on them wastes
the farmer's money and suppresses the nodulation they already paid for in seed.
They are excluded by name rather than by a low number, so the rule cannot be
weakened by editing a table.

**A total is only offered for a measured boundary.** A pinned field's area is a
1.5 ha default echoed back, so "spread 130 kg across your field" would be a
confident number derived from an assumption. Per-hectare rates are safe either
way; totals are gated on the farmer having actually drawn their boundary.
"""

from __future__ import annotations

# Season nitrogen recommendation, kg N per hectare. Indian state-university
# and FAO extension figures for irrigated conditions, rounded.
NITROGEN_KG_PER_HA: dict[str, int] = {
    "wheat": 120,
    "rice": 120,
    "maize": 120,
    "barley": 60,
    "sorghum": 80,
    "pearl_millet": 60,
    "finger_millet": 50,
    "mustard": 80,
    "sunflower": 80,
    "sesame": 50,
    "cotton": 100,
    "potato": 150,
    "onion": 100,
    "tomato": 120,
    "sugarcane": 250,
}

# Crops that make their own nitrogen. Urea here is money spent to suppress
# nodulation — the opposite of the intended effect.
FIXES_OWN_NITROGEN = frozenset({
    "soybean", "chickpea", "lentil", "green_gram", "common_bean",
    "pigeon_pea", "groundnut",
})

# Share of the season's nitrogen given at the vegetative top-dressing. The
# common split is a third at sowing, a third at first irrigation, a third at
# tillering; this is that middle third.
TOPDRESS_FRACTION = 1 / 3

# Urea is 46% nitrogen by mass — the one number here that is a fact rather
# than a recommendation.
UREA_N_FRACTION = 0.46

# A single irrigation smaller than this cannot be applied evenly by flood or
# furrow, and one larger runs off or drains past the root zone.
MIN_IRRIGATION_MM = 25
MAX_IRRIGATION_MM = 60


def _round_to(value: float, step: int) -> int:
    return int(round(value / step) * step)


def urea_topdress_kg_per_ha(crop_id: str | None) -> int | None:
    """Urea for one vegetative top-dressing, kg/ha. None when inapplicable.

    None means "do not offer this advice", not "offer it with no number" — a
    crop we have no rate for, and every nitrogen-fixing legume, both return it.
    """
    crop = (crop_id or "").lower()
    if crop in FIXES_OWN_NITROGEN:
        return None
    season_n = NITROGEN_KG_PER_HA.get(crop)
    if season_n is None:
        return None
    urea = (season_n * TOPDRESS_FRACTION) / UREA_N_FRACTION
    return _round_to(urea, 5)


def total_kg(kg_per_ha: int, area_ha: float) -> int:
    """What to actually carry to the field, rounded to a practical 5 kg."""
    return _round_to(kg_per_ha * area_ha, 5)


def irrigation_depth_mm(deficit_mm: float) -> int:
    """How deep to irrigate, from the week's water deficit.

    Clamped at both ends: below the minimum an irrigation cannot be spread
    evenly, above the maximum the extra drains past the roots and takes
    dissolved nitrogen with it.
    """
    depth = _round_to(abs(deficit_mm), 5)
    return max(MIN_IRRIGATION_MM, min(MAX_IRRIGATION_MM, depth))


def irrigation_volume_m3(depth_mm: int, area_ha: float) -> int:
    """Cubic metres for that depth over that area. 1 mm over 1 ha is 10 m³."""
    return _round_to(depth_mm * area_ha * 10, 5)
