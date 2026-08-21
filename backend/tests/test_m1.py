"""M1 unit tests — offline and deterministic (no network, no model, no keys).

    python3 -m unittest discover -s backend/tests -t backend/tests

The advisory is deliberately built so that everything worth asserting is
assertable without a model call: which template was chosen, which signals it
rests on, and what happens when a chooser misbehaves.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from m1_advisory import doses, gemini, rules  # noqa: E402
from m1_advisory.advisory import RULES_SOURCE, build_advisory  # noqa: E402
from m1_advisory.signals import extract, value  # noqa: E402
from m1_advisory.stage import (  # noqa: E402
    UNKNOWN,
    VEGETATIVE,
    days_after_sowing,
    growth_stage,
)
from m1_advisory.templates import (  # noqa: E402
    BY_ID,
    INSUFFICIENT_DATA,
    LANGUAGES,
    TEMPLATES,
)

FIXTURE = Path(__file__).parent / "fixtures" / "live_profile_narwana.json"
TODAY = date(2026, 8, 21)


def live_profile() -> dict:
    """A real M0 response, captured from the running endpoint on 2026-08-21."""
    return json.loads(FIXTURE.read_text())


def profile(**overrides) -> dict:
    """A minimal profile whose every signal is live unless overridden."""
    base = {
        "healthChip": "GREEN",
        "ndvi": 0.58,
        "ndviPercentile": 0.61,
        "neighbourhoodMedianNdvi": 0.52,
        "rainForecastMm": 0.9,
        "rainForecast7dMm": 25.3,
        "crop": {"id": "wheat", "label": "Wheat"},
        "soil": {"ph": 7.2, "n": 1.5, "cec": 12.8},
        "climate": {
            "et0Forecast7dMm": 30.3,
            "soilWater": {"0_7cm": 0.35, "7_28cm": 0.30, "28_100cm": 0.15},
            "airTempMaxC": 32.4,
            "vpdKpa": 0.86,
            "surfaceWetness": 0.4,
        },
        "terrain": {},
        "sources": {
            key: {"source": "test", "status": "live"}
            for key in ("boundary", "soil", "forecast", "climate",
                        "agroclimate", "ndvi", "healthChip")
        },
    }
    base["sources"]["soilNPK"] = {"source": "district default", "status": "seeded"}
    base["sources"]["crop"] = {"source": "farmer", "status": "reported"}

    for path, val in overrides.items():
        target = base
        parts = path.split(".")
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = val
    return base


class TestSignals(unittest.TestCase):
    def test_a_signal_with_no_source_is_absent_not_null(self):
        # Presence in the dict is the eligibility test, so an unavailable
        # source must remove the signal rather than leave a None behind.
        p = profile()
        p["sources"]["ndvi"] = {"source": "none", "status": "unavailable"}
        signals = extract(p)
        self.assertNotIn("ndvi", signals)
        self.assertNotIn("ndviPercentile", signals)

    def test_a_missing_value_is_absent_even_when_the_source_is_live(self):
        signals = extract(profile(ndvi=None))
        self.assertNotIn("ndvi", signals)
        self.assertIn("ndviPercentile", signals)

    def test_provenance_survives_the_flattening(self):
        signals = extract(profile())
        self.assertEqual(signals["soilNitrogen"].status, "seeded")
        self.assertFalse(signals["soilNitrogen"].is_measured)
        self.assertTrue(signals["ndvi"].is_measured)

    def test_water_balance_is_derived_from_supply_minus_demand(self):
        signals = extract(profile())
        self.assertAlmostEqual(value(signals, "waterBalance7dMm"), -5.0, places=1)

    def test_water_balance_needs_both_halves(self):
        p = profile()
        del p["climate"]["et0Forecast7dMm"]
        self.assertNotIn("waterBalance7dMm", extract(p))

    def test_the_live_profile_yields_the_signals_the_rules_expect(self):
        signals = extract(live_profile())
        for name in ("ndviPercentile", "waterBalance7dMm", "soilPh",
                     "topsoilWater", "airTempMaxC"):
            self.assertIn(name, signals, name)


class TestGrowthStage(unittest.TestCase):
    def test_wheat_mid_season_is_vegetative(self):
        self.assertEqual(growth_stage("wheat", "2026-06-20", TODAY)[0], VEGETATIVE)

    def test_a_crop_with_no_calendar_is_unknown_not_guessed(self):
        stage, days = growth_stage("mango", "2026-01-01", TODAY)
        self.assertEqual(stage, UNKNOWN)
        self.assertEqual(days, 232)

    def test_no_sowing_date_is_unknown(self):
        self.assertEqual(growth_stage("wheat", None, TODAY)[0], UNKNOWN)

    def test_an_unparseable_date_does_not_raise(self):
        self.assertIsNone(days_after_sowing("not a date"))
        self.assertEqual(growth_stage("wheat", "20/06/2026", TODAY)[0], UNKNOWN)

    def test_a_future_sowing_date_is_reported_as_negative_not_hidden(self):
        stage, days = growth_stage("wheat", "2026-12-01", TODAY)
        self.assertEqual(stage, UNKNOWN)
        self.assertLess(days, 0)

    def test_running_past_the_calendar_is_unknown_rather_than_maturity(self):
        # Usually means the field was harvested and re-sown without anyone
        # updating the date. Claiming "maturity" would be worse than silence.
        self.assertEqual(growth_stage("wheat", "2024-01-01", TODAY)[0], UNKNOWN)


class TestTemplates(unittest.TestCase):
    def test_every_template_is_complete_in_every_language(self):
        for template in TEMPLATES + (INSUFFICIENT_DATA,):
            for language in LANGUAGES:
                copy = template.text.get(language)
                self.assertIsNotNone(copy, f"{template.id} has no {language}")
                for part in ("situation", "action", "reason"):
                    self.assertTrue(copy.get(part), f"{template.id}.{language}.{part}")

    def test_hindi_and_portuguese_are_not_english_left_in_place(self):
        for template in TEMPLATES:
            self.assertNotEqual(
                template.text["hi"]["action"], template.text["en"]["action"],
                f"{template.id} Hindi looks copied from English",
            )
            self.assertTrue(
                any(0x0900 <= ord(c) <= 0x097F for c in template.text["hi"]["action"]),
                f"{template.id} Hindi has no Devanagari",
            )

    def test_every_declared_slot_appears_in_every_languages_copy(self):
        # A slot present in English and forgotten in Hindi renders a sentence
        # missing its number, which reads as a bug to a farmer and to a judge.
        for template in TEMPLATES:
            for slot in template.slots:
                for language in LANGUAGES:
                    joined = " ".join(template.text[language].values())
                    self.assertIn("{" + slot + "}", joined,
                                  f"{template.id}.{language} never uses {slot}")

    def test_every_template_has_a_condition_and_a_slot_builder(self):
        for template in TEMPLATES:
            self.assertIn(template.id, rules.CONDITIONS, template.id)
            self.assertIn(template.id, rules.SLOTS, template.id)

    def test_no_orphan_rules(self):
        for template_id in list(rules.CONDITIONS) + list(rules.SLOTS):
            self.assertIn(template_id, BY_ID, f"{template_id} has no template")

    def test_an_untranslated_language_falls_back_to_english(self):
        template = BY_ID["canopy.healthy"]
        self.assertEqual(
            template.render("zz", {"aheadPct": 61}),
            template.render("en", {"aheadPct": 61}),
        )


class TestRules(unittest.TestCase):
    def fired(self, p, sowing="2026-06-20"):
        signals = extract(p)
        stage, days = growth_stage(
            (p.get("crop") or {}).get("id"), sowing, TODAY)
        return {t.id for t in rules.eligible(signals, stage, days)}

    def test_surplus_rain_holds_irrigation(self):
        self.assertIn("irrigation.hold", self.fired(profile(rainForecast7dMm=60.0)))

    def test_a_deficit_with_dry_topsoil_asks_for_water_now(self):
        fired = self.fired(profile(
            rainForecast7dMm=2.0, **{"climate.soilWater": {"0_7cm": 0.10, "7_28cm": 0.12}}))
        self.assertIn("irrigation.apply", fired)

    def test_a_deficit_with_wet_topsoil_does_not(self):
        fired = self.fired(profile(rainForecast7dMm=2.0))
        self.assertNotIn("irrigation.apply", fired)
        self.assertIn("irrigation.watch", fired)

    def test_rain_tomorrow_blocks_nitrogen(self):
        self.assertIn("fertiliser.hold_rain", self.fired(profile(rainForecastMm=18.0)))

    def test_low_nitrogen_needs_a_lagging_canopy_too(self):
        # Low N on a thriving canopy is not evidence the crop is short of it.
        self.assertNotIn("fertiliser.nitrogen_low",
                         self.fired(profile(**{"soil.n": 0.6})))
        self.assertIn("fertiliser.nitrogen_low",
                      self.fired(profile(**{"soil.n": 0.6}, ndviPercentile=0.2)))

    def test_heat_stress_needs_both_heat_and_dry_air(self):
        self.assertNotIn("protection.heat_stress",
                         self.fired(profile(**{"climate.airTempMaxC": 38.0})))
        self.assertIn("protection.heat_stress", self.fired(profile(
            **{"climate.airTempMaxC": 38.0, "climate.vpdKpa": 2.4})))

    def test_a_bare_neighbourhood_says_the_area_is_between_crops(self):
        self.assertIn("canopy.no_active_crop",
                      self.fired(profile(neighbourhoodMedianNdvi=0.12)))

    def test_alkaline_soil_uses_the_same_threshold_as_the_profile_card(self):
        self.assertNotIn("soil.alkaline", self.fired(profile(**{"soil.ph": 7.5})))
        self.assertIn("soil.alkaline", self.fired(profile(**{"soil.ph": 7.9})))

    def test_a_stage_template_is_ineligible_without_a_stage(self):
        self.assertNotIn("fertiliser.topdress_window",
                         self.fired(profile(), sowing=None))
        self.assertIn("fertiliser.topdress_window", self.fired(profile()))

    def test_the_two_chosen_templates_never_share_a_topic(self):
        signals = extract(profile(rainForecast7dMm=60.0, rainForecastMm=18.0))
        primary, secondary = rules.choose(signals, VEGETATIVE, 62)
        self.assertIsNotNone(secondary)
        self.assertNotEqual(primary.topic, secondary.topic)

    def test_urgency_outranks_declaration_order(self):
        signals = extract(profile(rainForecastMm=18.0))
        primary, _ = rules.choose(signals, VEGETATIVE, 62)
        self.assertEqual(primary.urgency, "urgent")


class TestAdvisory(unittest.TestCase):
    def build(self, p=None, **kwargs):
        kwargs.setdefault("sowing_date", "2026-06-20")
        kwargs.setdefault("today", TODAY)
        return build_advisory(p or profile(), **kwargs)

    def test_it_never_cites_a_signal_that_was_never_fetched(self):
        # The guarantee the whole module is built around. Strip Earth Engine
        # and the advisory must stop mentioning anything derived from it.
        p = profile()
        p["sources"]["ndvi"] = {"source": "none", "status": "unavailable"}
        advisory = self.build(p)
        cited = {s["name"] for s in advisory.signals_used}
        self.assertFalse(
            cited & {"ndvi", "ndviPercentile", "neighbourhoodMedianNdvi"},
            f"cited an unavailable signal: {cited}",
        )

    def test_every_cited_signal_matches_the_profiles_own_provenance(self):
        p = live_profile()
        advisory = self.build(p)
        signals = extract(p)
        for cited in advisory.signals_used:
            if cited["name"] == "cropStage":
                self.assertEqual(cited["status"], "seeded")
                continue
            self.assertIn(cited["name"], signals)
            self.assertEqual(cited["status"], signals[cited["name"]].status)

    def test_advice_resting_only_on_defaults_says_so(self):
        p = profile(**{"soil.n": 0.6}, ndviPercentile=0.2)
        p["sources"]["ndvi"] = {"source": "none", "status": "unavailable"}
        p["sources"]["forecast"] = {"source": "none", "status": "unavailable"}
        p["sources"]["climate"] = {"source": "none", "status": "unavailable"}
        p["sources"]["agroclimate"] = {"source": "none", "status": "unavailable"}
        advisory = self.build(p)
        self.assertFalse(advisory.rests_on_measurements)

    def test_a_field_with_no_signals_at_all_admits_it(self):
        p = profile()
        p["sources"] = {k: {"source": "none", "status": "unavailable"}
                        for k in p["sources"]}
        advisory = self.build(p)
        self.assertEqual(advisory.template_ids, [INSUFFICIENT_DATA.id])
        self.assertEqual(advisory.signals_used, [])
        self.assertIn("Not enough", advisory.headline)

    def test_the_card_carries_at_most_two_actions(self):
        advisory = self.build(live_profile())
        self.assertGreaterEqual(len(advisory.actions), 1)
        self.assertLessEqual(len(advisory.actions), 2)

    def test_language_reaches_the_rendered_text(self):
        hindi = self.build(language="hi")
        english = self.build(language="en")
        self.assertNotEqual(hindi.headline, english.headline)
        self.assertTrue(any(0x0900 <= ord(c) <= 0x097F for c in hindi.headline))

    def test_the_same_profile_gives_the_same_advisory(self):
        # Determinism is what makes pre-cached demo audio possible.
        first, second = self.build(), self.build()
        self.assertEqual(first.to_dict()["headline"], second.to_dict()["headline"])
        self.assertEqual(first.template_ids, second.template_ids)

    def test_the_dict_shape_is_what_the_card_reads(self):
        d = self.build().to_dict()
        for key in ("language", "headline", "actions", "reason", "urgency",
                    "templateIds", "signalsUsed", "stage", "daysAfterSowing",
                    "restsOnMeasurements", "generatedAt", "sources"):
            self.assertIn(key, d)
        self.assertIn("advisory", d["sources"])


class TestChooserIsUntrusted(unittest.TestCase):
    """A model chooses among eligible templates; it cannot introduce one."""

    def build(self, chooser):
        return build_advisory(
            profile(), language="en", sowing_date="2026-06-20", today=TODAY,
            chooser=chooser, chooser_source="test model",
        )

    def test_a_valid_choice_is_honoured(self):
        def chooser(eligible, signals, context):
            return eligible[-1].id, None
        advisory = self.build(chooser)
        self.assertEqual(advisory.chosen_by.source, "test model")

    def test_a_template_that_is_not_eligible_is_refused(self):
        # The signals behind irrigation.apply are not in this profile's range.
        def chooser(eligible, signals, context):
            return "irrigation.apply", None
        advisory = self.build(chooser)
        self.assertEqual(advisory.chosen_by.source, RULES_SOURCE)
        self.assertNotIn("irrigation.apply", advisory.template_ids)

    def test_an_invented_template_id_is_refused(self):
        advisory = self.build(lambda e, s, c: ("spray.more.urea", None))
        self.assertEqual(advisory.chosen_by.source, RULES_SOURCE)

    def test_a_chooser_that_raises_does_not_break_the_card(self):
        def chooser(eligible, signals, context):
            raise RuntimeError("model unavailable")
        advisory = self.build(chooser)
        self.assertEqual(advisory.chosen_by.source, RULES_SOURCE)
        self.assertTrue(advisory.headline)

    def test_a_second_action_from_the_same_topic_is_dropped(self):
        def chooser(eligible, signals, context):
            same = [t for t in eligible if t.topic == eligible[0].topic]
            return (same[0].id, same[1].id) if len(same) > 1 else (same[0].id, None)
        advisory = self.build(chooser)
        topics = [BY_ID[i].topic for i in advisory.template_ids]
        self.assertEqual(len(topics), len(set(topics)))


if __name__ == "__main__":
    unittest.main()


class TestDoses(unittest.TestCase):
    """Advice a farmer can act on means a number, and the right number."""

    def test_urea_is_derived_from_the_season_rate_not_invented(self):
        # Wheat: 120 kg N/ha season, a third at this stage, urea is 46% N.
        self.assertEqual(doses.urea_topdress_kg_per_ha("wheat"), 85)
        self.assertEqual(doses.urea_topdress_kg_per_ha("pearl_millet"), 45)

    def test_legumes_are_never_given_a_nitrogen_dose(self):
        # They fix their own. Urea here costs money and suppresses the
        # nodulation the farmer already paid for in seed.
        for legume in doses.FIXES_OWN_NITROGEN:
            self.assertIsNone(doses.urea_topdress_kg_per_ha(legume), legume)

    def test_an_unknown_crop_gets_no_dose_rather_than_a_default(self):
        self.assertIsNone(doses.urea_topdress_kg_per_ha("dragonfruit"))
        self.assertIsNone(doses.urea_topdress_kg_per_ha(None))

    def test_irrigation_depth_is_clamped_at_both_ends(self):
        # Too little cannot be spread evenly; too much drains past the roots
        # and takes dissolved nitrogen with it.
        self.assertEqual(doses.irrigation_depth_mm(-2), doses.MIN_IRRIGATION_MM)
        self.assertEqual(doses.irrigation_depth_mm(-200), doses.MAX_IRRIGATION_MM)
        self.assertEqual(doses.irrigation_depth_mm(-40), 40)

    def test_a_millimetre_over_a_hectare_is_ten_cubic_metres(self):
        self.assertEqual(doses.irrigation_volume_m3(30, 1.0), 300)
        self.assertEqual(doses.irrigation_volume_m3(30, 2.0), 600)

    def test_quantities_round_to_something_a_farmer_can_measure(self):
        self.assertEqual(doses.total_kg(85, 1.5011) % 5, 0)
        self.assertEqual(doses.urea_topdress_kg_per_ha("wheat") % 5, 0)


class TestAdviceIsActionable(unittest.TestCase):
    """An advisory that names a problem without naming the response is not one."""

    def test_advice_to_apply_urea_always_states_the_amount(self):
        for template_id in ("fertiliser.nitrogen_low",
                            "fertiliser.topdress_window"):
            template = BY_ID[template_id]
            for language in LANGUAGES:
                self.assertIn(
                    "{ureaKgPerHa}", template.text[language]["action"],
                    f"{template_id}.{language} says to fertilise without saying "
                    "how much",
                )

    def test_advice_to_irrigate_always_states_the_depth(self):
        for template_id in ("irrigation.apply", "irrigation.watch"):
            template = BY_ID[template_id]
            for language in LANGUAGES:
                self.assertIn("{depthMm}", template.text[language]["action"])

    def test_a_legume_is_never_told_to_top_dress(self):
        p = profile(**{"crop": {"id": "chickpea", "label": "Chickpea"},
                       "soil.n": 0.5}, ndviPercentile=0.1)
        advisory = build_advisory(
            p, language="en", sowing_date="2026-06-20", today=TODAY)
        for template_id in advisory.template_ids:
            self.assertNotIn("urea", BY_ID[template_id].text["en"]["action"].lower(),
                             f"{template_id} recommends urea for a legume")

    def test_the_same_field_under_wheat_does_get_a_dose(self):
        # The guard has to be specific to legumes, not a blanket silence.
        p = profile(**{"soil.n": 0.5}, ndviPercentile=0.1)
        advisory = build_advisory(
            p, language="en", sowing_date="2026-06-20", today=TODAY)
        self.assertTrue(
            any("urea" in a.lower() for a in advisory.actions),
            advisory.actions,
        )

    def test_the_rendered_dose_is_a_real_number_not_a_placeholder(self):
        p = profile(**{"soil.n": 0.5}, ndviPercentile=0.1)
        advisory = build_advisory(
            p, language="en", sowing_date="2026-06-20", today=TODAY)
        joined = " ".join(advisory.actions)
        self.assertNotIn("{", joined)
        self.assertRegex(joined, r"\d+ kg")


class TestGeminiChooser(unittest.TestCase):
    """The prompt and the gating, without ever calling Vertex."""

    def setUp(self):
        self._saved = {k: os.environ.get(k)
                       for k in ("M1_DISABLE_GEMINI", "GCP_PROJECT", "VERTEX_REGION")}
        os.environ["GCP_PROJECT"] = "test-project"
        os.environ.pop("M1_DISABLE_GEMINI", None)

    def tearDown(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _candidates(self):
        signals = extract(profile())
        stage, days = growth_stage("wheat", "2026-06-20", TODAY)
        return rules.eligible(signals, stage, days), signals, stage, days

    def test_it_can_be_switched_off_without_touching_code(self):
        os.environ["M1_DISABLE_GEMINI"] = "1"
        self.assertFalse(gemini.gemini_available())

    def test_it_is_unavailable_without_a_project(self):
        os.environ.pop("GCP_PROJECT")
        self.assertFalse(gemini.gemini_available())

    def test_the_region_is_configurable_for_data_residency(self):
        # A BRICS demo whose selling point is that data stays in-country should
        # not quietly run its advisory through Iowa.
        os.environ["VERTEX_REGION"] = "southamerica-east1"
        chooser = gemini.GeminiChooser()
        self.assertIn("southamerica-east1-aiplatform", chooser.endpoint)
        self.assertIn("southamerica-east1", chooser.source)

    def test_the_prompt_offers_only_eligible_templates(self):
        candidates, signals, stage, days = self._candidates()
        prompt = gemini._prompt(
            candidates, signals,
            {"stage": stage, "daysAfterSowing": days, "crop": "wheat"},
        )
        for template in candidates:
            self.assertIn(template.id, prompt)
        offered = {t.id for t in TEMPLATES if t.id in prompt}
        self.assertEqual(offered, {t.id for t in candidates},
                         "the prompt leaked a template that is not eligible")

    def test_the_prompt_carries_provenance_not_just_numbers(self):
        # The model is told which readings are district defaults so it can
        # weigh them lower, which is the judgement rules cannot make.
        candidates, signals, stage, days = self._candidates()
        prompt = gemini._prompt(candidates, signals, {"stage": stage})
        self.assertIn("[seeded]", prompt)
        self.assertIn("[live]", prompt)

    def test_the_prompt_says_it_is_choosing_not_writing(self):
        candidates, signals, stage, days = self._candidates()
        prompt = gemini._prompt(candidates, signals, {"stage": stage})
        self.assertIn("NOT writing advice", prompt)
        self.assertIn("Do not invent", prompt)

    def test_temperature_is_zero_so_two_runs_agree(self):
        # Pre-cached demo audio depends on the same field advising the same way.
        self.assertEqual(gemini.GENERATION_CONFIG["temperature"], 0)

    def test_the_response_is_forced_into_the_schema(self):
        # Free text would need parsing, and a parse failure is a blank card.
        config = gemini.GENERATION_CONFIG
        self.assertEqual(config["responseMimeType"], "application/json")
        self.assertEqual(config["responseSchema"]["required"], ["primary"])

    def test_a_credential_failure_is_recorded_not_swallowed(self):
        # Token acquisition happens before the HTTP call, so an unrecorded
        # failure here would surface as a rules advisory with no sign that a
        # model was ever attempted.
        os.environ["GCP_SA_JSON"] = "/nonexistent/key.json"
        self.addCleanup(os.environ.pop, "GCP_SA_JSON", None)

        chooser = gemini.GeminiChooser()
        candidates, signals, stage, days = self._candidates()
        with self.assertRaises(Exception):
            chooser(candidates, signals, {"stage": stage})
        self.assertIsNotNone(chooser.last_error)
        self.assertIn("nonexistent", chooser.last_error)
