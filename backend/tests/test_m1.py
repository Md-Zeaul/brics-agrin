"""M1 unit tests — offline and deterministic (no network, no model, no keys).

    python3 -m unittest discover -s backend/tests -t backend/tests

The advisory is deliberately built so that everything worth asserting is
assertable without a model call: which template was chosen, which signals it
rests on, and what happens when a chooser misbehaves.
"""

from __future__ import annotations

import json
import os
import re
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from m1_advisory import doses, gemini, products, rules  # noqa: E402
from m1_advisory.advisory import RULES_SOURCE, build_advisory  # noqa: E402
from m1_advisory.signals import extract, value  # noqa: E402
from m1_advisory.stage import (  # noqa: E402
    UNKNOWN,
    VEGETATIVE,
    days_after_sowing,
    growth_stage,
)
from m1_advisory.templates import (  # noqa: E402
    days_phrase,
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
    # Present unconditionally so a test only has to supply the data. Nothing is
    # extracted from a provenance entry with no payload behind it.
    base["sources"]["fertiliserLog"] = {"source": "farmer", "status": "reported"}
    base["sources"]["lastIrrigation"] = {"source": "farmer", "status": "reported"}

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


class TestGeminiResponseHandling(unittest.TestCase):
    """A 200 is not the same as an answer."""

    def test_thinking_is_off(self):
        # Measured: 10.9s with it on, 1.6s with it off. And `maxOutputTokens`
        # counts thinking tokens, so leaving it on spent the whole budget
        # reasoning and returned a response carrying no answer at all.
        self.assertEqual(
            gemini.GENERATION_CONFIG["thinkingConfig"]["thinkingBudget"], 0)

    def test_a_good_payload_is_read(self):
        chooser = gemini.GeminiChooser(project="p")
        payload = {"candidates": [{"content": {"parts": [
            {"text": '{"primary": "soil.alkaline", "why": "pH is high"}'}]}}]}
        self.assertEqual(chooser._parse(payload)["primary"], "soil.alkaline")

    def test_a_response_with_no_content_names_the_finish_reason(self):
        # This is what a truncated response actually looks like: HTTP 200, one
        # candidate, no parts. Indexing into it raises KeyError('parts'), which
        # says nothing about why — the least useful thing to find in a log the
        # night before a demo.
        chooser = gemini.GeminiChooser(project="p")
        with self.assertRaises(ValueError) as caught:
            chooser._parse({"candidates": [{"finishReason": "MAX_TOKENS"}]})
        self.assertIn("MAX_TOKENS", str(caught.exception))
        self.assertIn("token budget", str(caught.exception))

    def test_an_empty_response_is_reported_not_indexed(self):
        chooser = gemini.GeminiChooser(project="p")
        with self.assertRaises(ValueError):
            chooser._parse({})

    def test_the_models_justification_is_kept_for_debugging(self):
        # Never shown to the farmer — the template already carries a reason —
        # but it is the only way to answer "why did the card say that?".
        chooser = gemini.GeminiChooser(project="p")
        self.assertIsNone(chooser.last_reason)
        self.assertIn("last_reason", vars(chooser))


class TestStageChangesTheAdvice(unittest.TestCase):
    """The sowing date is not decoration — it decides what may be said."""

    def _advice(self, days_after_sowing, **overrides):
        from datetime import timedelta
        sown = (TODAY - timedelta(days=days_after_sowing)).isoformat()
        p = profile(**overrides)
        return build_advisory(p, language="en", sowing_date=sown, today=TODAY)

    def _eligible(self, days_after_sowing, **overrides):
        from datetime import timedelta
        sown = (TODAY - timedelta(days=days_after_sowing)).isoformat()
        signals = extract(profile(**overrides))
        stage, days = growth_stage("wheat", sown, TODAY)
        return {t.id for t in rules.eligible(signals, stage, days)}, stage

    def test_nitrogen_is_offered_during_growth(self):
        eligible, stage = self._eligible(40, **{"soil.n": 0.6}, ndviPercentile=0.1)
        self.assertEqual(stage, VEGETATIVE)
        self.assertIn("fertiliser.nitrogen_low", eligible)

    def test_nitrogen_is_never_offered_at_grain_fill(self):
        # The crop can no longer take it up, it delays maturity and costs grain
        # quality — and the thin canopy that triggers the rule is, by then,
        # ordinary senescence rather than hunger.
        eligible, stage = self._eligible(110, **{"soil.n": 0.6}, ndviPercentile=0.1)
        self.assertEqual(stage, "filling")
        self.assertNotIn("fertiliser.nitrogen_low", eligible)

    def test_nitrogen_is_never_offered_when_the_stage_is_unknown(self):
        eligible, stage = self._eligible(400, **{"soil.n": 0.6}, ndviPercentile=0.1)
        self.assertEqual(stage, UNKNOWN)
        self.assertNotIn("fertiliser.nitrogen_low", eligible)

    def test_a_ripening_field_is_not_flagged_as_a_failing_one(self):
        eligible, stage = self._eligible(130, ndviPercentile=0.05)
        self.assertEqual(stage, "maturity")
        self.assertNotIn("canopy.behind_neighbours", eligible)

    def test_harvest_advice_appears_only_at_maturity(self):
        at_maturity, _ = self._eligible(130)
        self.assertIn("harvest.dry_down", at_maturity)
        mid_season, _ = self._eligible(62)
        self.assertNotIn("harvest.dry_down", mid_season)

    def test_the_advice_actually_changes_across_the_season(self):
        # If every stage gave the same card, the date would be decoration.
        seen = {tuple(self._advice(d).template_ids) for d in (40, 110, 130)}
        self.assertGreater(len(seen), 1)


class TestTheCardNeverContradictsItself(unittest.TestCase):
    """Two actions on one card have to be doable together."""

    def test_stop_irrigating_never_shares_a_card_with_irrigate(self):
        from datetime import timedelta
        sown = (TODAY - timedelta(days=130)).isoformat()
        advisory = build_advisory(
            profile(), language="en", sowing_date=sown, today=TODAY)
        self.assertIn("harvest.dry_down", advisory.template_ids)
        for template_id in advisory.template_ids:
            self.assertNotEqual(BY_ID[template_id].topic, "irrigation")

    def test_conflict_is_symmetric(self):
        # Declared on one side only; it must bind from either direction.
        harvest = BY_ID["harvest.dry_down"]
        watch = BY_ID["irrigation.watch"]
        self.assertTrue(harvest.conflicts_with(watch))
        self.assertTrue(watch.conflicts_with(harvest))

    def test_hold_irrigation_never_shares_a_card_with_when_to_irrigate(self):
        hold = BY_ID["irrigation.hold"]
        heat = BY_ID["protection.heat_stress"]
        self.assertTrue(hold.conflicts_with(heat))

    def test_nothing_needs_doing_is_never_a_second_line(self):
        # "Stop irrigating now" followed by "no change this week" reads as an
        # app arguing with itself.
        self.assertTrue(BY_ID["canopy.healthy"].primary_only)
        from datetime import timedelta
        for days in (11, 40, 80, 110, 130):
            sown = (TODAY - timedelta(days=days)).isoformat()
            advisory = build_advisory(
                profile(), language="en", sowing_date=sown, today=TODAY)
            if len(advisory.template_ids) > 1:
                self.assertNotIn("canopy.healthy", advisory.template_ids[1:],
                                 f"at {days} days")

    def test_a_model_pairing_a_contradiction_is_overruled(self):
        # The model chooses among eligible templates, but the pairing rule is
        # not its to override.
        from datetime import timedelta
        sown = (TODAY - timedelta(days=130)).isoformat()

        def chooser(eligible, signals, context):
            ids = [t.id for t in eligible]
            if "harvest.dry_down" in ids and "irrigation.watch" in ids:
                return "harvest.dry_down", "irrigation.watch"
            return ids[0], None

        advisory = build_advisory(
            profile(), language="en", sowing_date=sown, today=TODAY,
            chooser=chooser, chooser_source="test model")
        self.assertEqual(advisory.template_ids, ["harvest.dry_down"])


# --- What the farmer has already done to the field --------------------------

def days_ago(n: int) -> str:
    return (TODAY - timedelta(days=n)).isoformat()


def fertilised(days: int, product="urea", bags=None):
    entry = {"date": days_ago(days), "product": product}
    if bags is not None:
        entry["bagsPerAcre"] = bags
    return entry


class TestFertiliserProducts(unittest.TestCase):
    """The bag is the unit a farmer counts in; kilograms of N is the unit the
    agronomy is written in. Everything here is that conversion."""

    def test_the_same_quantity_of_different_products_is_not_the_same_dose(self):
        # This is the whole reason the log records a product. Same answer from
        # the farmer — "two bags an acre" — and a factor of two in nitrogen.
        urea = products.nitrogen_kg_per_ha("urea", 2)
        dap = products.nitrogen_kg_per_ha("dap", 2)
        self.assertGreater(urea, 100)
        self.assertLess(dap, 50)
        self.assertGreater(urea / dap, 2.0)

    def test_urea_bags_are_45_kg_not_50(self):
        # India cut the urea bag to 45 kg in 2018 while complexes stayed at 50.
        # Assuming 50 throughout overstates every urea application by 11%.
        self.assertEqual(products.PRODUCTS["urea"].bag_kg, 45)
        self.assertEqual(products.PRODUCTS["dap"].bag_kg, 50)

    def test_manure_is_recorded_but_never_quantified(self):
        # It is spread by the trolley and its analysis depends on what the
        # animals ate. A nitrogen figure from it would be a guess in the
        # costume of an analysis.
        self.assertIsNone(products.nitrogen_kg_per_ha("fym", 2))
        self.assertTrue(products.supplies_nitrogen("fym"))

    def test_not_remembering_is_an_answer_the_table_accepts(self):
        self.assertIsNone(products.nitrogen_kg_per_ha("unknown", 2))
        self.assertIsNotNone(products.label("unknown"))

    def test_an_unremembered_product_is_assumed_to_have_carried_nitrogen(self):
        # Withholding a dose the crop already had costs a bag. Repeating one it
        # never had costs a season. The conservative answer is the safe one.
        self.assertTrue(products.supplies_nitrogen("unknown"))
        self.assertTrue(products.supplies_nitrogen(None))

    def test_potash_carries_no_nitrogen_so_it_locks_nothing_out(self):
        self.assertFalse(products.supplies_nitrogen("mop"))
        self.assertFalse(products.supplies_nitrogen("ssp"))

    def test_every_product_is_labelled_in_every_language(self):
        for pid in products.PICKER_ORDER:
            for language in ("en", "hi", "pt"):
                self.assertTrue(
                    products.label(pid, language),
                    f"{pid} has no {language} label",
                )

    def test_the_picker_offers_exactly_what_the_table_holds(self):
        self.assertEqual(set(products.PICKER_ORDER), set(products.PRODUCTS))


class TestRemainingNitrogen(unittest.TestCase):
    def test_a_full_season_already_applied_leaves_nothing(self):
        self.assertEqual(doses.remaining_topdress_kg_per_ha("wheat", 130), 0)

    def test_dap_at_sowing_still_leaves_a_normal_split_due(self):
        # 1 bag/acre of DAP is 22 kg N against a 120 kg season. Nearly all of
        # the budget is unspent, so the next dose is a normal one.
        applied = products.nitrogen_kg_per_ha("dap", 1)
        self.assertEqual(
            doses.remaining_topdress_kg_per_ha("wheat", applied),
            doses.urea_topdress_kg_per_ha("wheat"),
        )

    def test_a_heavy_urea_application_shrinks_the_next_dose(self):
        applied = products.nitrogen_kg_per_ha("urea", 2)   # 102 of 120 kg N
        adjusted = doses.remaining_topdress_kg_per_ha("wheat", applied)
        self.assertGreater(adjusted, 0)
        self.assertLess(adjusted, doses.urea_topdress_kg_per_ha("wheat"))

    def test_an_unspent_budget_is_still_never_given_in_one_go(self):
        # The reason nitrogen is split is that a crop cannot take up a season's
        # worth at once. Having applied nothing does not change that.
        self.assertEqual(
            doses.remaining_topdress_kg_per_ha("wheat", 0),
            doses.urea_topdress_kg_per_ha("wheat"),
        )

    def test_a_legume_is_refused_an_adjusted_dose_as_well_as_a_standard_one(self):
        # The legume guard has to hold on every path to a dose, not just the
        # first one that was written.
        self.assertIsNone(doses.remaining_topdress_kg_per_ha("chickpea", 0))
        self.assertIsNone(doses.urea_topdress_kg_per_ha("chickpea"))


class TestHistorySignals(unittest.TestCase):
    def test_a_date_alone_is_enough_to_fix_the_timing(self):
        signals = extract(profile(fertiliserLog=[{"date": days_ago(5)}]), TODAY)
        self.assertEqual(value(signals, "daysSinceFertiliser"), 5)
        # No product named, so nitrogen is assumed and the lockout applies.
        self.assertEqual(value(signals, "daysSinceNitrogen"), 5)
        # But no quantity can be invented from it.
        self.assertNotIn("nitrogenAppliedKgPerHa", signals)

    def test_a_product_without_a_quantity_names_the_nutrients_only(self):
        signals = extract(profile(fertiliserLog=[fertilised(5, "dap")]), TODAY)
        self.assertEqual(value(signals, "lastFertiliserProduct"), "dap")
        self.assertEqual(value(signals, "phosphorusApplied"), "yes")
        self.assertNotIn("nitrogenAppliedKgPerHa", signals)

    def test_a_quantity_turns_the_remaining_dose_into_arithmetic(self):
        signals = extract(
            profile(fertiliserLog=[fertilised(30, "urea", 2)]), TODAY)
        self.assertAlmostEqual(
            value(signals, "nitrogenAppliedKgPerHa"), 102.3, places=1)
        self.assertIn("ureaRemainingKgPerHa", signals)
        self.assertLess(
            value(signals, "ureaRemainingKgPerHa"),
            value(signals, "ureaTopdressKgPerHa"),
        )

    def test_the_adjusted_dose_is_seeded_not_reported(self):
        # The farmer's figure went into the subtraction, but what it was
        # subtracted from is still a published season rate. Claiming the result
        # is `reported` would launder a general recommendation into a
        # measurement of this field.
        signals = extract(
            profile(fertiliserLog=[fertilised(30, "urea", 2)]), TODAY)
        self.assertEqual(signals["ureaRemainingKgPerHa"].status, "seeded")
        self.assertEqual(signals["nitrogenAppliedKgPerHa"].status, "reported")

    def test_one_unquantified_entry_voids_the_whole_total(self):
        # A partial sum understates what is in the ground, and the error runs
        # in the direction that costs the farmer a bag.
        signals = extract(profile(fertiliserLog=[
            fertilised(40, "dap", 1),
            fertilised(30, "urea"),          # no quantity
        ]), TODAY)
        self.assertNotIn("nitrogenAppliedKgPerHa", signals)
        self.assertNotIn("ureaRemainingKgPerHa", signals)

    def test_two_applications_are_summed_which_is_the_real_indian_pattern(self):
        # DAP at sowing, urea at first irrigation.
        signals = extract(profile(fertiliserLog=[
            fertilised(60, "dap", 1),
            fertilised(30, "urea", 1),
        ]), TODAY)
        expected = (products.nitrogen_kg_per_ha("dap", 1)
                    + products.nitrogen_kg_per_ha("urea", 1))
        self.assertAlmostEqual(
            value(signals, "nitrogenAppliedKgPerHa"), expected, places=1)

    def test_days_since_nitrogen_ignores_an_application_that_had_none(self):
        # Potash three days ago is not a reason to withhold urea.
        signals = extract(profile(fertiliserLog=[
            fertilised(40, "urea", 1),
            fertilised(3, "mop", 1),
        ]), TODAY)
        self.assertEqual(value(signals, "daysSinceFertiliser"), 3)
        self.assertEqual(value(signals, "daysSinceNitrogen"), 40)

    def test_a_future_date_is_rejected_rather_than_counted_backwards(self):
        future = (TODAY + timedelta(days=3)).isoformat()
        signals = extract(profile(fertiliserLog=[{"date": future}]), TODAY)
        self.assertNotIn("daysSinceFertiliser", signals)

    def test_an_unparseable_date_does_not_take_the_advisory_down(self):
        signals = extract(profile(fertiliserLog=[{"date": "last Tuesday"}]), TODAY)
        self.assertNotIn("daysSinceFertiliser", signals)

    def test_an_unavailable_source_drops_the_history_like_any_other_signal(self):
        p = profile(fertiliserLog=[fertilised(5, "urea", 1)])
        p["sources"]["fertiliserLog"] = {"source": "x", "status": "unavailable"}
        self.assertNotIn("daysSinceFertiliser", extract(p, TODAY))

    def test_irrigation_date_becomes_a_day_count(self):
        signals = extract(profile(lastIrrigation=days_ago(2)), TODAY)
        self.assertEqual(value(signals, "daysSinceIrrigation"), 2)
        self.assertEqual(signals["daysSinceIrrigation"].status, "reported")


class TestTheEngineRemembersWhatWasAlreadyDone(unittest.TestCase):
    """The point of collecting any of this: advice that does not repeat itself."""

    DRY = {"climate.soilWater": {"0_7cm": 0.12, "7_28cm": 0.2, "28_100cm": 0.15},
           "rainForecast7dMm": 2.0}

    def advise(self, **overrides):
        return build_advisory(
            profile(**overrides), sowing_date=days_ago(50), today=TODAY)

    def test_without_a_log_the_advice_is_what_it_always_was(self):
        # The whole feature has to be invisible to a farmer who skips it.
        ids = self.advise().template_ids
        self.assertNotIn("fertiliser.next_split_due", ids)
        self.assertNotIn("irrigation.recent", ids)

    def test_a_recent_dose_is_not_repeated(self):
        ids = self.advise(fertiliserLog=[fertilised(9, "urea", 1)]).template_ids
        self.assertNotIn("fertiliser.topdress_window", ids)
        self.assertNotIn("fertiliser.topdress_adjusted", ids)
        self.assertNotIn("fertiliser.nitrogen_low", ids)

    def test_the_suppression_is_turned_into_advice_rather_than_silence(self):
        advisory = self.advise(fertiliserLog=[fertilised(9, "urea", 1)])
        self.assertIn("fertiliser.next_split_due", advisory.template_ids)
        text = " ".join(advisory.actions)
        self.assertIn("12", text, "should say when the next split is due")

    def test_the_window_reopens_once_the_crop_can_use_the_next_dose(self):
        advisory = self.advise(fertiliserLog=[fertilised(25, "urea", 1)])
        self.assertNotIn("fertiliser.next_split_due", advisory.template_ids)
        self.assertIn("fertiliser.topdress_adjusted", advisory.template_ids)

    def test_potash_last_week_does_not_hold_back_nitrogen(self):
        ids = self.advise(fertiliserLog=[fertilised(4, "mop", 1)]).template_ids
        self.assertNotIn("fertiliser.next_split_due", ids)

    def test_a_spent_budget_says_stop_buying_rather_than_wait(self):
        # Applied everything, and recently. "The next split is due in 12 days"
        # would be true of the calendar and wrong about the crop.
        advisory = self.advise(fertiliserLog=[fertilised(5, "urea", 3)])
        self.assertIn("fertiliser.season_n_complete", advisory.template_ids)
        self.assertNotIn("fertiliser.next_split_due", advisory.template_ids)

    def test_the_card_never_quotes_two_different_urea_rates(self):
        advisory = self.advise(fertiliserLog=[fertilised(30, "urea", 2)])
        self.assertNotIn("fertiliser.topdress_window", advisory.template_ids)
        self.assertIn("fertiliser.topdress_adjusted", advisory.template_ids)

    def test_a_field_watered_yesterday_is_not_told_to_water(self):
        ids = self.advise(lastIrrigation=days_ago(1), **self.DRY).template_ids
        self.assertNotIn("irrigation.apply", ids)

    def test_and_is_told_why_instead_of_being_told_nothing(self):
        advisory = self.advise(lastIrrigation=days_ago(1), **self.DRY)
        self.assertIn("irrigation.recent", advisory.template_ids)

    def test_a_field_watered_a_week_ago_is_still_told_to_water(self):
        ids = self.advise(lastIrrigation=days_ago(8), **self.DRY).template_ids
        self.assertIn("irrigation.apply", ids)
        self.assertNotIn("irrigation.recent", ids)

    def test_a_legume_grower_is_never_given_an_adjusted_dose_either(self):
        advisory = self.advise(
            **{"crop": {"id": "chickpea", "label": "Chickpea"},
               "fertiliserLog": [fertilised(30, "urea", 1)]})
        for template_id in advisory.template_ids:
            self.assertFalse(
                template_id.startswith("fertiliser.topdress"),
                f"{template_id} quotes urea to a nitrogen-fixing legume",
            )

    def test_what_the_farmer_reported_is_named_in_the_provenance(self):
        # The card has to be able to answer "how do you know?" with the
        # farmer's own answer, marked as theirs rather than as a measurement.
        advisory = self.advise(fertiliserLog=[fertilised(9, "urea", 1)])
        used = {s["name"]: s["status"] for s in advisory.signals_used}
        self.assertEqual(used.get("daysSinceNitrogen"), "reported")

    def test_every_new_template_renders_in_every_language(self):
        cases = {
            "fertiliser.next_split_due": {"fertiliserLog": [fertilised(9, "urea", 1)]},
            "fertiliser.topdress_adjusted": {"fertiliserLog": [fertilised(30, "urea", 2)]},
            "fertiliser.season_n_complete": {"fertiliserLog": [fertilised(5, "urea", 3)]},
            "irrigation.recent": dict(lastIrrigation=days_ago(1), **self.DRY),
        }
        for template_id, overrides in cases.items():
            for language in ("en", "hi", "pt"):
                advisory = build_advisory(
                    profile(**overrides), language=language,
                    sowing_date=days_ago(50), today=TODAY)
                self.assertIn(template_id, advisory.template_ids,
                              f"{template_id} not chosen for {language}")
                rendered = " ".join([advisory.headline, advisory.reason,
                                     *advisory.actions])
                self.assertNotIn("{", rendered, f"unfilled slot in {language}")
                self.assertTrue(rendered.strip())


class TestTheProductListsCannotDrift(unittest.TestCase):
    """The picker is in Dart and the nutrient analysis is in Python.

    A product added to one and not the other fails in the worst way available:
    the app offers an id the backend does not recognise, `nitrogen_kg_per_ha`
    returns None for it, and the advisory silently drops to a general rate
    without anything looking broken. Cheaper to catch here.
    """

    DART = (Path(__file__).resolve().parents[2] / "app" / "lib" / "features"
            / "field" / "domain" / "field_history.dart")

    def dart_ids(self) -> list[str]:
        source = self.DART.read_text()
        block = source.split("kFertiliserProducts = [")[1].split("];")[0]
        return re.findall(r"id: '([a-z0-9_]+)'", block)

    def test_the_app_offers_exactly_what_the_backend_can_price(self):
        self.assertTrue(self.DART.is_file(), f"{self.DART} moved")
        self.assertEqual(self.dart_ids(), list(products.PICKER_ORDER))

    def test_the_app_disables_quantity_for_exactly_what_cannot_be_weighed(self):
        source = self.DART.read_text()
        block = source.split("kUnquantifiableProducts = {")[1].split("}")[0]
        dart = set(re.findall(r"'([a-z0-9_]+)'", block))
        backend = {pid for pid in products.PICKER_ORDER
                   if not products.PRODUCTS[pid].is_quantifiable}
        self.assertEqual(dart, backend)


class TestDayCountsReadLikeSentences(unittest.TestCase):
    """"You irrigated 1 days ago" is the default case of the irrigation card,
    not an edge one — irrigated yesterday is exactly when it fires."""

    def test_one_day_is_singular_in_every_language(self):
        self.assertEqual(days_phrase(1, "en"), "1 day")
        self.assertEqual(days_phrase(1, "pt"), "1 dia")
        # Hindi does not inflect दिन here; the entry exists so the lookup is
        # total, not because it says something.
        self.assertEqual(days_phrase(1, "hi"), "1 दिन")

    def test_more_than_one_is_plural(self):
        self.assertEqual(days_phrase(9, "en"), "9 days")
        self.assertEqual(days_phrase(9, "pt"), "9 dias")

    def test_zero_is_plural_which_is_what_english_does(self):
        self.assertEqual(days_phrase(0, "en"), "0 days")

    def test_an_unknown_language_falls_back_rather_than_raising(self):
        self.assertEqual(days_phrase(3, "zz"), "3 days")

    def test_the_card_never_says_one_days(self):
        for language in ("en", "hi", "pt"):
            advisory = build_advisory(
                profile(lastIrrigation=days_ago(1),
                        **{"climate.soilWater": {"0_7cm": 0.12, "7_28cm": 0.2,
                                                 "28_100cm": 0.15},
                           "rainForecast7dMm": 2.0}),
                language=language, sowing_date=days_ago(50), today=TODAY,
            )
            self.assertIn("irrigation.recent", advisory.template_ids)
            self.assertNotIn("1 days", advisory.headline)
            self.assertNotIn("1 dias", advisory.headline)
