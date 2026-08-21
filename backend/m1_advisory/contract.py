"""The M1 output contract — what S2's advisory card reads.

Mirrors M0's shape on purpose: camelCase JSON, a `sources` entry saying how the
advice was arrived at, and every claim traceable to a signal with a status. The
card can then render M1 with the same provenance affordance it already renders
M0 with, and a judge asking "is that live?" gets the same answer in both halves
of the screen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from m0_field.contract import Provenance, utc_now_iso


@dataclass
class Advisory:
    """One day's advice for one field, in one language."""

    language: str
    headline: str          # what is true right now
    actions: list[str]     # one or two things to do, most urgent first
    reason: str            # why, including what we are unsure of
    urgency: str
    template_ids: list[str]
    signals_used: list[dict]   # [{name, status}] — checkable against provenance
    stage: str
    days_after_sowing: int | None
    chosen_by: Provenance
    generated_at: str = field(default_factory=utc_now_iso)

    @property
    def rests_on_measurements(self) -> bool:
        """False when every signal behind this advice was seeded or reported.

        Worth surfacing: advice built entirely on district defaults is still
        reasonable advice, but it is not a finding about *this* field, and the
        card should not let it look like one.
        """
        return any(s["status"] in ("live", "cached") for s in self.signals_used)

    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "headline": self.headline,
            "actions": list(self.actions),
            "reason": self.reason,
            "urgency": self.urgency,
            "templateIds": list(self.template_ids),
            "signalsUsed": list(self.signals_used),
            "stage": self.stage,
            "daysAfterSowing": self.days_after_sowing,
            "restsOnMeasurements": self.rests_on_measurements,
            "generatedAt": self.generated_at,
            "sources": {"advisory": self.chosen_by.to_dict()},
        }
