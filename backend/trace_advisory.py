"""Why did the card say that? — the whole chain, in one screen.

    .venv/bin/python backend/trace_advisory.py                     # cached demo field
    .venv/bin/python backend/trace_advisory.py --pin 29.61,76.11   # live, ~20s
    .venv/bin/python backend/trace_advisory.py --sown 2026-04-13 --language hi

Every number on S2 can be walked back to a satellite pass, a reanalysis grid,
an extension rate table or something the farmer typed. This prints that walk:
which sources answered, which signals survived, which recommendations were
therefore permitted, which one was chosen and by whom.

Built for two audiences. Ours, when the card says something surprising and the
question is whether the rule or the reading is wrong. And a judge's, when the
question is whether any of this is real.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from m1_advisory import rules  # noqa: E402
from m1_advisory.advisory import RULES_SOURCE, build_advisory  # noqa: E402
from m1_advisory.gemini import GeminiChooser, gemini_available  # noqa: E402
from m1_advisory.signals import extract  # noqa: E402
from m1_advisory.stage import growth_stage  # noqa: E402
from m1_advisory.templates import TEMPLATES  # noqa: E402

FIXTURE = Path(__file__).parent / "tests" / "fixtures" / "live_profile_narwana.json"


def rule(title: str) -> None:
    print(f"\n\033[1m{title}\033[0m\n" + "─" * 78)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=FIXTURE,
                        help="an M0 profile JSON (default: the captured demo field)")
    parser.add_argument("--pin", help="lat,lng — build a fresh profile instead (~20s)")
    parser.add_argument("--crop", default="wheat")
    parser.add_argument("--sown", default="2026-06-20", help="ISO sowing date")
    parser.add_argument("--language", default="en", choices=["en", "hi", "pt"])
    parser.add_argument("--today", help="ISO date to evaluate as, for stage arithmetic")
    parser.add_argument(
        "--fertilised", metavar="DATE[:PRODUCT[:BAGS_PER_ACRE]]", action="append",
        default=[],
        help="an entry in the fertiliser log, repeatable. "
             "e.g. --fertilised 2026-07-20:urea:1",
    )
    parser.add_argument("--irrigated", help="ISO date the field was last watered")
    args = parser.parse_args()

    today = date.fromisoformat(args.today) if args.today else date.today()

    log = []
    for raw in args.fertilised:
        parts = raw.split(":")
        entry = {"date": parts[0]}
        if len(parts) > 1 and parts[1]:
            entry["product"] = parts[1]
        if len(parts) > 2 and parts[2]:
            entry["bagsPerAcre"] = float(parts[2])
        log.append(entry)

    rule("1 · INPUT — what the farmer gave us")
    if args.pin:
        lat, lng = (float(v) for v in args.pin.split(","))
        from m0_field import build_field_profile
        print(f"   pin           {lat}, {lng}   (building live, ~20s)")
        profile = build_field_profile(
            pin={"lat": lat, "lng": lng},
            crop={"id": args.crop, "label": args.crop.title()},
            sowing_date=args.sown,
            fertiliser_log=log or None,
            last_irrigation=args.irrigated,
        ).to_dict()
    else:
        profile = json.loads(args.profile.read_text())
        profile["crop"] = {"id": args.crop, "label": args.crop.title()}
        # A cached profile predates these answers; splice them in so the trace
        # shows the same advisory a fresh capture would produce.
        if log:
            profile["fertiliserLog"] = log
            profile.setdefault("sources", {})["fertiliserLog"] = {
                "source": "farmer's own record of what they applied",
                "status": "reported",
            }
        if args.irrigated:
            profile["lastIrrigation"] = args.irrigated
            profile.setdefault("sources", {})["lastIrrigation"] = {
                "source": "farmer", "status": "reported",
            }
        print(f"   profile       {args.profile}")
    print(f"   crop          {args.crop}")
    print(f"   sown          {args.sown}")
    for entry in log:
        print(f"   fertilised    {entry.get('date')}  {entry.get('product', '(not said)')}"
              f"  {entry.get('bagsPerAcre', '?')} bags/acre")
    if args.irrigated:
        print(f"   irrigated     {args.irrigated}")
    print(f"   language      {args.language}")
    print(f"   evaluated as  {today}")

    rule("2 · SOURCES — who answered, and how well")
    for name, entry in sorted(profile.get("sources", {}).items()):
        status = entry.get("status", "?")
        mark = "  " if status in ("live", "cached") else "! "
        print(f" {mark}{name:14} {status:12} {entry.get('source', '')}")

    rule("3 · SIGNALS — what survived, and what a template may therefore use")
    signals = extract(profile, today)
    for name in sorted(signals):
        signal = signals[name]
        print(f"   {name:26} {str(signal.value):>10}   [{signal.status}]")
    print(f"\n   {len(signals)} usable. A signal whose source was unavailable is")
    print("   absent here, not null — absence IS the eligibility test.")

    rule("4 · DERIVED — three things M0 does not compute")
    stage, days = growth_stage(args.crop, args.sown, today)
    balance = signals.get("waterBalance7dMm")
    if balance:
        rain = signals["rainForecast7dMm"].value
        et0 = signals["et0Forecast7dMm"].value
        print(f"   water balance  {rain} mm rain − {et0} mm ET₀ = {balance.value} mm")
    print(f"   growth stage   {args.sown} → {days} days → {stage}   [seeded]")
    urea = signals.get("ureaTopdressKgPerHa")
    print(f"   urea rate      {urea.value} kg/ha  [seeded]" if urea
          else "   urea rate      not offered for this crop")

    rule("5 · GATES — every template, and why it passed or did not")
    context = dict(signals)
    context["__days__"] = days
    eligible = []
    for template in TEMPLATES:
        missing = [n for n in template.requires if n not in signals]
        if missing:
            verdict = f"no signal: {missing[0]}"
        elif template.stages and stage not in template.stages:
            verdict = f"wrong stage (needs {'/'.join(template.stages)})"
        elif not rules.CONDITIONS[template.id](context):
            verdict = "rule false"
        else:
            verdict = "ELIGIBLE"
            eligible.append(template)
        mark = "\033[1m→\033[0m" if verdict == "ELIGIBLE" else " "
        print(f" {mark} {template.id:30} {template.urgency:9} {verdict}")

    rule("6 · CHOICE — which of the eligible ones, and by whom")
    by_rules = rules.choose(signals, stage, days)
    print(f"   rules would choose   {by_rules[0].id if by_rules[0] else '—'}"
          f"  +  {by_rules[1].id if by_rules[1] else '—'}")
    print("   (rank by urgency, then by declaration order — a tie broken by file order)")

    chooser = GeminiChooser() if gemini_available() else None
    advisory = build_advisory(
        profile, language=args.language, sowing_date=args.sown, today=today,
        chooser=chooser, chooser_source=chooser.source if chooser else None,
    )
    print(f"\n   actually chosen      {'  +  '.join(advisory.template_ids)}")
    print(f"   by                   {advisory.chosen_by.source}")
    if chooser and chooser.last_reason:
        print(f"   its reason           {chooser.last_reason}")
    if chooser and chooser.last_error:
        print(f"   model unavailable    {chooser.last_error[:120]}")
    if advisory.chosen_by.source == RULES_SOURCE and not (chooser and chooser.last_error):
        print("   (no model configured — rules decided)")

    rule(f"7 · RENDERED — the card, in {args.language}")
    print(f"   {advisory.headline}")
    for action in advisory.actions:
        print(f"     → {action}")
    print(f"   {advisory.reason}")

    rule("8 · WHAT IT RESTS ON")
    for used in advisory.signals_used:
        print(f"   {used['name']:26} [{used['status']}]")
    print(f"\n   rests on measurements: {advisory.rests_on_measurements}")
    if not advisory.rests_on_measurements:
        print("   → the card shows the district-averages caveat")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
