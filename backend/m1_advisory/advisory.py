"""Building one advisory from one field profile.

The orchestration is deliberately thin, because the interesting decision is
structural rather than procedural: *who chooses* the template is swappable, and
*what may be chosen* is not.

    signals -> eligible templates -> a chooser picks from them -> render

Gemini plugs in as a chooser. It sees the eligible list and returns ids from it;
anything else is rejected and the rules chooser decides instead. That inversion
is what keeps a language model from inventing advice: it is not asked what the
farmer should do, only which of the applicable, human-written recommendations
fits best. A model that hallucinates a template id changes nothing about what
the farmer reads.
"""

from __future__ import annotations

from datetime import date
from typing import Callable, Protocol

from m0_field.contract import LIVE, Provenance, SEEDED

from . import rules
from .signals import Signal, extract
from .stage import UNKNOWN, growth_stage
from .templates import INSUFFICIENT_DATA, Template

RULES_SOURCE = "M1 rule set"


class Chooser(Protocol):
    """Picks a primary and optional secondary from the eligible templates."""

    def __call__(
        self,
        eligible: list[Template],
        signals: dict[str, Signal],
        context: dict,
    ) -> tuple[str | None, str | None]:
        ...


def build_advisory(
    profile: dict,
    language: str = "en",
    sowing_date: str | None = None,
    today: date | None = None,
    chooser: Chooser | None = None,
    chooser_source: str | None = None,
):
    """Turn an M0 profile into an Advisory. Never raises for missing signals."""
    from .contract import Advisory  # local: contract imports back for typing

    signals = extract(profile, today)
    crop = profile.get("crop") or {}
    sowing = sowing_date or profile.get("sowingDate")
    stage, days = growth_stage(crop.get("id"), sowing, today)

    candidates = rules.eligible(signals, stage, days)
    primary = secondary = None
    source = RULES_SOURCE

    if chooser and candidates:
        picked = _ask(chooser, candidates, signals, {
            "stage": stage, "daysAfterSowing": days,
            "crop": crop.get("id"), "language": language,
        })
        if picked:
            primary, secondary = picked
            source = chooser_source or "model"

    if primary is None:
        primary, secondary = rules.choose(signals, stage, days)
        source = RULES_SOURCE

    if primary is None:
        # Nothing was eligible at all. Say so rather than reaching for a
        # cheerful default; that is the whole point of the design.
        return Advisory(
            language=language,
            **_render(INSUFFICIENT_DATA, None, {}, {}, language),
            urgency=INSUFFICIENT_DATA.urgency,
            template_ids=[INSUFFICIENT_DATA.id],
            signals_used=[],
            stage=stage,
            days_after_sowing=days,
            chosen_by=Provenance(
                source=RULES_SOURCE, status=LIVE,
                note="no signal supported any advisory",
            ),
        )

    primary_slots = rules.render_slots(primary, signals, days, language)
    secondary_slots = (
        rules.render_slots(secondary, signals, days, language) if secondary else {}
    )

    used = _signals_behind(primary, secondary, signals, stage)

    return Advisory(
        language=language,
        **_render(primary, secondary, primary_slots, secondary_slots, language),
        urgency=primary.urgency,
        template_ids=[t.id for t in (primary, secondary) if t],
        signals_used=used,
        stage=stage,
        days_after_sowing=days,
        chosen_by=Provenance(
            source=source, status=LIVE,
            note=f"chose {primary.id}"
                 + (f" and {secondary.id}" if secondary else ""),
        ),
    )


def _ask(chooser, candidates, signals, context) -> tuple | None:
    """Run a chooser and validate what it returns.

    Anything outside the eligible set is discarded rather than corrected. A
    chooser that returns a template whose signals were never fetched is exactly
    the failure this validation exists to catch, and quietly substituting a
    neighbour would hide it.
    """
    by_id = {t.id: t for t in candidates}
    try:
        primary_id, secondary_id = chooser(candidates, signals, context)
    except Exception:  # a model call is allowed to fail; the card is not
        return None

    primary = by_id.get(primary_id)
    if primary is None:
        return None

    secondary = by_id.get(secondary_id)
    if secondary is not None and secondary.topic == primary.topic:
        secondary = None  # two irrigation actions is one action, said twice
    if secondary is not None and secondary.primary_only:
        secondary = None
    if secondary is not None and primary.conflicts_with(secondary):
        # The model is choosing, not authoring, but it can still pair two
        # recommendations that contradict each other. The pairing rule is not
        # its to override.
        secondary = None
    return primary, secondary


def _render(primary, secondary, primary_slots, secondary_slots, language) -> dict:
    copy = primary.render(language, primary_slots)
    actions = [copy["action"]]
    if secondary is not None:
        actions.append(secondary.render(language, secondary_slots)["action"])
    return {
        "headline": copy["situation"],
        "actions": actions,
        "reason": copy["reason"],
    }


def _signals_behind(primary, secondary, signals, stage) -> list[dict]:
    """Every signal the chosen advice rests on, with its status.

    This is the list a test checks against M0's provenance, and the list the
    card shows when a farmer asks where the advice came from. Growth stage is
    included as `seeded` because it is arithmetic over an indicative calendar,
    not something anybody measured.
    """
    names: list[str] = []
    for template in (primary, secondary):
        if template is None:
            continue
        for name in template.requires:
            if name not in names:
                names.append(name)
        if template.stages and stage != UNKNOWN:
            if "cropStage" not in names:
                names.append("cropStage")

    used = []
    for name in names:
        if name == "cropStage":
            used.append({"name": "cropStage", "status": SEEDED})
        elif name in signals:
            used.append({"name": name, "status": signals[name].status})
    return used
