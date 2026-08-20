"""M0 unit tests — offline and deterministic (no network, no credentials).

    python3 -m unittest discover -s backend/tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from m0_field import geometry, health  # noqa: E402
from m0_field.contract import (  # noqa: E402
    CACHED,
    REPORTED,
    SEEDED,
    UNAVAILABLE,
    FieldProfile,
    Soil,
)
from m0_field.sources import nasa_power, soilgrids  # noqa: E402


class TestGeometry(unittest.TestCase):
    def test_square_polygon_has_requested_area(self):
        polygon = geometry.square_polygon_around(29.61, 76.11, area_ha=1.5)
        self.assertAlmostEqual(geometry.area_ha(polygon), 1.5, delta=0.02)

    def test_polygon_is_closed(self):
        polygon = geometry.square_polygon_around(29.61, 76.11)
        self.assertEqual(polygon[0], polygon[-1])

    def test_centroid_returns_to_the_pin(self):
        polygon = geometry.square_polygon_around(29.61, 76.11, area_ha=2.0)
        centroid = geometry.centroid_of(polygon)
        self.assertAlmostEqual(centroid["lat"], 29.61, places=4)
        self.assertAlmostEqual(centroid["lng"], 76.11, places=4)

    def test_area_scales_with_request(self):
        small = geometry.area_ha(geometry.square_polygon_around(29.61, 76.11, 1.0))
        large = geometry.area_ha(geometry.square_polygon_around(29.61, 76.11, 4.0))
        self.assertAlmostEqual(large / small, 4.0, delta=0.05)

    def test_geojson_is_lng_lat_and_closed(self):
        polygon = geometry.square_polygon_around(29.61, 76.11)
        ring = geometry.to_geojson(polygon)["coordinates"][0]
        self.assertEqual(ring[0], ring[-1])
        # Earth Engine expects [lng, lat]; longitude is the larger value here.
        self.assertAlmostEqual(ring[0][0], 76.11, delta=0.01)
        self.assertAlmostEqual(ring[0][1], 29.61, delta=0.01)

    def test_accepts_an_already_open_ring(self):
        closed = geometry.square_polygon_around(29.61, 76.11, 1.5)
        self.assertAlmostEqual(geometry.area_ha(closed[:-1]), 1.5, delta=0.02)


class TestBoundaryModeAndCrop(unittest.TestCase):
    """A pinned area is an assumption; a drawn one is a measurement."""

    SQUARE = [[29.610, 76.110], [29.610, 76.114], [29.607, 76.114], [29.607, 76.110]]

    def test_pin_is_marked_as_a_default_not_a_measurement(self):
        with _MockedSources():
            from m0_field.profile import build_field_profile

            profile = build_field_profile(pin={"lat": 29.61, "lng": 76.11})
        self.assertEqual(profile.boundary_mode, "pin")
        self.assertIn("not a measurement", profile.sources["boundary"]["note"])

    def test_drawn_boundary_is_marked_measured(self):
        with _MockedSources():
            from m0_field.profile import build_field_profile

            profile = build_field_profile(polygon=self.SQUARE)
        self.assertEqual(profile.boundary_mode, "drawn")
        self.assertEqual(profile.to_dict()["boundaryMode"], "drawn")

    def test_pin_area_is_the_default_echoed_back(self):
        with _MockedSources():
            from m0_field.profile import build_field_profile

            profile = build_field_profile(pin={"lat": 29.61, "lng": 76.11}, plot_ha=1.5)
        self.assertAlmostEqual(profile.area_ha, 1.5, places=2)

    def test_drawn_area_is_computed_not_defaulted(self):
        with _MockedSources():
            from m0_field.profile import build_field_profile

            profile = build_field_profile(polygon=self.SQUARE)
        # The drawn square is far larger than the 1.5 ha default.
        self.assertGreater(profile.area_ha, 10.0)

    def test_crop_is_recorded_and_attributed_to_the_farmer(self):
        with _MockedSources():
            from m0_field.profile import build_field_profile

            profile = build_field_profile(
                pin={"lat": 29.61, "lng": 76.11},
                crop={"id": "wheat", "label": "\u0917\u0947\u0939\u0942\u0901"},
            )
        self.assertEqual(profile.crop["id"], "wheat")
        self.assertEqual(profile.sources["crop"]["status"], REPORTED)
        self.assertEqual(profile.to_dict()["crop"]["id"], "wheat")

    def test_no_crop_leaves_no_phantom_source(self):
        with _MockedSources():
            from m0_field.profile import build_field_profile

            profile = build_field_profile(pin={"lat": 29.61, "lng": 76.11})
        self.assertIsNone(profile.crop)
        self.assertNotIn("crop", profile.sources)

    def test_crop_does_not_change_the_health_chip(self):
        """M0's rule is crop-neutral by design; recording must not alter it."""
        with _MockedSources():
            from m0_field.profile import build_field_profile

            plain = build_field_profile(pin={"lat": 29.61, "lng": 76.11})
            with_crop = build_field_profile(
                pin={"lat": 29.61, "lng": 76.11}, crop={"id": "sugarcane"}
            )
        self.assertEqual(plain.health_chip, with_crop.health_chip)


class TestSelfIntersection(unittest.TestCase):
    """A crossed boundary shoelaces to ~0 ha — it must be refused, not priced."""

    SQUARE = [[29.610, 76.110], [29.610, 76.114], [29.607, 76.114], [29.607, 76.110]]
    BOWTIE = [[29.610, 76.110], [29.610, 76.114], [29.607, 76.110], [29.607, 76.114]]

    def test_square_is_simple(self):
        self.assertTrue(geometry.is_simple(self.SQUARE))

    def test_closed_ring_is_simple(self):
        self.assertTrue(geometry.is_simple([*self.SQUARE, self.SQUARE[0]]))

    def test_triangle_cannot_cross(self):
        self.assertTrue(geometry.is_simple(self.SQUARE[:3]))

    def test_concave_l_shape_stays_valid(self):
        # Concave is legitimate — many real fields are. Only crossing is not.
        self.assertTrue(geometry.is_simple([[0, 0], [0, 3], [2, 3], [2, 2], [1, 2], [1, 0]]))

    def test_bowtie_is_rejected(self):
        self.assertFalse(geometry.is_simple(self.BOWTIE))

    def test_bowtie_area_is_zero_which_is_why_we_guard(self):
        self.assertEqual(geometry.area_ha(self.BOWTIE), 0.0)

    def test_build_refuses_a_crossed_boundary(self):
        from m0_field.profile import build_field_profile

        with self.assertRaises(ValueError) as caught:
            build_field_profile(polygon=self.BOWTIE)
        self.assertIn("crosses itself", str(caught.exception))

    def test_build_refuses_fewer_than_three_corners(self):
        from m0_field.profile import build_field_profile

        with self.assertRaises(ValueError) as caught:
            build_field_profile(polygon=[[29.610, 76.110], [29.610, 76.114]])
        self.assertIn("three corners", str(caught.exception))


class TestHealthChip(unittest.TestCase):
    def test_healthy_canopy_is_green(self):
        self.assertEqual(health.health_chip(0.72, 0.45)[0], health.GREEN)

    def test_low_ndvi_is_red(self):
        chip, driver = health.health_chip(0.20, 0.45)
        self.assertEqual(chip, health.RED)
        self.assertEqual(driver, "canopy_stress")

    def test_middling_ndvi_is_yellow(self):
        self.assertEqual(health.health_chip(0.45, 0.45)[0], health.YELLOW)

    def test_dry_root_zone_pulls_a_healthy_canopy_down(self):
        chip, driver = health.health_chip(0.72, 0.20)
        self.assertEqual(chip, health.YELLOW)
        self.assertEqual(driver, "soil_drying")

    def test_critical_moisture_is_red_even_with_good_canopy(self):
        self.assertEqual(health.health_chip(0.72, 0.10)[0], health.RED)

    def test_missing_ndvi_degrades_to_yellow_not_green(self):
        chip, driver = health.health_chip(None, 0.45)
        self.assertEqual(chip, health.YELLOW)
        self.assertEqual(driver, "ndvi_unavailable")

    def test_moisture_is_optional(self):
        self.assertEqual(health.health_chip(0.72, None)[0], health.GREEN)


class TestRelativeHealth(unittest.TestCase):
    """Ranking against neighbours is what makes one rule work for any crop."""

    NEIGHBOURS_GREEN = 0.5  # a neighbourhood with an active crop

    def test_bottom_of_the_neighbourhood_is_red(self):
        chip, driver = health.health_chip(
            0.3, 0.45, percentile=0.05, neighbourhood_median=self.NEIGHBOURS_GREEN
        )
        self.assertEqual(chip, health.RED)
        self.assertEqual(driver, "below_neighbours")

    def test_trailing_the_neighbourhood_is_yellow(self):
        chip, driver = health.health_chip(
            0.5, 0.45, percentile=0.25, neighbourhood_median=self.NEIGHBOURS_GREEN
        )
        self.assertEqual(chip, health.YELLOW)
        self.assertEqual(driver, "trailing_neighbours")

    def test_ahead_of_the_neighbourhood_is_green(self):
        chip, _ = health.health_chip(
            0.6, 0.45, percentile=0.7, neighbourhood_median=self.NEIGHBOURS_GREEN
        )
        self.assertEqual(chip, health.GREEN)

    def test_a_low_absolute_ndvi_can_still_be_green_for_a_sparse_crop(self):
        """The point of ranking: 0.35 beats its neighbours in an arid region."""
        chip, _ = health.health_chip(
            0.35, 0.45, percentile=0.8, neighbourhood_median=0.30
        )
        self.assertEqual(chip, health.GREEN)

    def test_percentile_takes_priority_over_absolute_thresholds(self):
        # 0.72 would be GREEN on absolute rules, but it trails its neighbours.
        chip, driver = health.health_chip(
            0.72, 0.45, percentile=0.05, neighbourhood_median=0.85
        )
        self.assertEqual(chip, health.RED)
        self.assertEqual(driver, "below_neighbours")

    def test_falls_back_to_absolute_when_no_comparison_exists(self):
        chip, driver = health.health_chip(0.20, 0.45, percentile=None)
        self.assertEqual(chip, health.RED)
        self.assertEqual(driver, "canopy_stress")


class TestFallowGuard(unittest.TestCase):
    """A region between seasons must not read as a region of sick fields."""

    def test_bare_neighbourhood_reports_no_active_crop(self):
        # Sorriso, Mato Grosso in August: soy is not planted until September.
        chip, driver = health.health_chip(
            0.15, 0.52, percentile=0.068, neighbourhood_median=0.178
        )
        self.assertEqual(chip, health.YELLOW)
        self.assertEqual(driver, "no_active_crop")

    def test_a_bare_field_among_green_neighbours_is_still_red(self):
        chip, driver = health.health_chip(
            0.12, 0.45, percentile=0.02, neighbourhood_median=0.62
        )
        self.assertEqual(chip, health.RED)
        self.assertEqual(driver, "below_neighbours")

    def test_guard_only_applies_when_a_comparison_exists(self):
        chip, driver = health.health_chip(0.15, 0.45)
        self.assertEqual(driver, "canopy_stress")


class TestSoilGridsParsing(unittest.TestCase):
    """Values below are a real SoilGrids response for the demo field."""

    PAYLOAD = {
        "properties": {
            "layers": [
                {
                    "name": "phh2o",
                    "unit_measure": {"d_factor": 10},
                    "depths": [{"label": "0-5cm", "values": {"mean": 79}}],
                },
                {
                    "name": "nitrogen",
                    "unit_measure": {"d_factor": 100},
                    "depths": [{"label": "0-5cm", "values": {"mean": 133}}],
                },
                {
                    "name": "cec",
                    "unit_measure": {"d_factor": 10},
                    "depths": [{"label": "0-5cm", "values": {"mean": 128}}],
                },
            ]
        }
    }

    def test_applies_d_factor_per_property(self):
        soil = soilgrids.parse_soil_payload(self.PAYLOAD)
        self.assertEqual(soil.ph, 7.9)      # pH*10 -> pH
        self.assertEqual(soil.n, 1.33)      # cg/kg -> g/kg
        self.assertEqual(soil.cec, 12.8)    # mmol(c)/kg -> cmol(c)/kg

    def test_phosphorus_and_potassium_stay_none(self):
        soil = soilgrids.parse_soil_payload(self.PAYLOAD)
        self.assertIsNone(soil.p)
        self.assertIsNone(soil.k)

    def test_ignores_other_depths(self):
        payload = {
            "properties": {
                "layers": [
                    {
                        "name": "phh2o",
                        "unit_measure": {"d_factor": 10},
                        "depths": [{"label": "5-15cm", "values": {"mean": 81}}],
                    }
                ]
            }
        }
        self.assertIsNone(soilgrids.parse_soil_payload(payload, depth="0-5cm").ph)

    def test_empty_response_raises(self):
        with self.assertRaises(Exception):
            soilgrids.parse_soil_payload({"properties": {"layers": []}})


class TestNasaPowerFillValues(unittest.TestCase):
    """POWER back-fills unpublished days with -999; those must never reach the profile."""

    SERIES = {
        "20260812": 0.41,
        "20260813": 0.44,
        "20260814": 0.48,
        "20260815": -999.0,
        "20260816": -999.0,
    }

    def test_latest_valid_skips_the_fill_tail(self):
        value, day = nasa_power._latest_valid(self.SERIES)
        self.assertEqual(value, 0.48)
        self.assertEqual(day, "20260814")

    def test_mean_excludes_fill_values(self):
        self.assertAlmostEqual(nasa_power._mean_valid(self.SERIES), 0.443, places=3)

    def test_all_fill_returns_none(self):
        self.assertEqual(nasa_power._latest_valid({"20260815": -999.0}), (None, None))
        self.assertIsNone(nasa_power._mean_valid({"20260815": -999.0}))

    def test_radiation_score_is_clamped(self):
        self.assertEqual(nasa_power._radiation_score(2.0), 0.0)
        self.assertEqual(nasa_power._radiation_score(40.0), 1.0)
        self.assertIsNone(nasa_power._radiation_score(None))


class TestContract(unittest.TestCase):
    def test_serialises_to_the_camel_case_the_app_reads(self):
        profile = FieldProfile(
            field_id="f1",
            polygon=[[29.6, 76.1]],
            centroid={"lat": 29.6, "lng": 76.1},
            area_ha=1.5,
            soil=Soil(ph=7.9),
            ndvi=0.62,
            rain_forecast_mm=22.0,
        )
        payload = profile.to_dict()
        for key in ("fieldId", "rainForecastMm", "healthChip", "tempForecast", "sources"):
            self.assertIn(key, payload)
        self.assertEqual(payload["soil"]["ph"], 7.9)

    def test_status_vocabulary_is_distinct(self):
        self.assertNotEqual(CACHED, UNAVAILABLE)


class _MockedSources:
    """Patch every external source with realistic returns.

    Loose MagicMocks are not enough here: the health-chip rule compares moisture
    against a float, so a mock leaking into the profile raises rather than
    exercising the wiring under test.
    """

    def __init__(
        self,
        ndvi=0.813,
        percentile=0.75,
        neighbourhood_median=0.62,
        ndvi_error=None,
        soil=None,
    ):
        self.ndvi = ndvi
        self.percentile = percentile
        self.neighbourhood_median = neighbourhood_median
        self.ndvi_error = ndvi_error
        self.soil = soil if soil is not None else Soil(ph=7.9, n=1.33)

    def __enter__(self):
        from unittest.mock import patch

        from m0_field import profile as profile_module
        from m0_field.contract import LIVE, Provenance

        live = Provenance(source="test", status=LIVE)
        self._patches = [
            patch.object(profile_module, "fetch_ndvi"),
            patch.object(profile_module, "soilgrids"),
            patch.object(profile_module, "open_meteo"),
            patch.object(profile_module, "nasa_power"),
            patch.object(profile_module, "fetch_climate"),
        ]
        (
            self.fetch_ndvi,
            soilgrids_mock,
            open_meteo_mock,
            power_mock,
            climate_mock,
        ) = [patcher.start() for patcher in self._patches]

        climate_mock.return_value = (
            {
                "surfaceTempDayC": 34.1,
                "et0MmPerDay": 5.39,
                "vpdKpa": 0.92,
                "radiationScore": 0.475,
                "soilWater": {"0_7cm": 0.342, "7_28cm": 0.281},
                "terrain": {"elevationM": 227.9, "slopeDeg": 1.98},
            },
            live,
        )

        if self.ndvi_error is not None:
            self.fetch_ndvi.side_effect = self.ndvi_error
        else:
            self.fetch_ndvi.return_value = (
                {
                    "ndvi": self.ndvi,
                    "percentile": self.percentile,
                    "neighbourhoodMedian": self.neighbourhood_median,
                },
                live,
            )

        soilgrids_mock.fetch_soil.return_value = (self.soil, {}, live)
        open_meteo_mock.fetch_forecast.return_value = (
            {
                "rainForecastMm": 0.9,
                "rainForecast7dMm": 35.6,
                "tempForecast": [{"date": "2026-08-19", "maxC": 33.5, "minC": 27.0}],
                "et0SumMm": 31.2,
            },
            live,
        )
        power_mock.fetch_agroclimate.return_value = (
            {
                "moisture": 0.48,
                "radiationScore": 0.39,
                "surfaceWetness": 0.49,
                "observedRain30dMm": 200.1,
            },
            live,
        )
        return self

    def __exit__(self, *exc):
        for patcher in self._patches:
            patcher.stop()
        return False


def _build(mocks, **kwargs):
    from m0_field.profile import build_field_profile

    return build_field_profile(pin={"lat": 29.61, "lng": 76.11}, **kwargs)


class TestNdviWindowWiring(unittest.TestCase):
    """The window must reach Earth Engine, and a failure must still fall back."""

    def test_window_is_passed_through_to_earth_engine(self):
        window = ("2026-01-15", "2026-03-15")
        with _MockedSources() as mocks:
            profile = _build(mocks, ndvi_window=window)
        self.assertEqual(mocks.fetch_ndvi.call_args.kwargs["window"], window)
        self.assertEqual(profile.ndvi, 0.813)

    def test_no_window_means_the_live_reading(self):
        with _MockedSources() as mocks:
            _build(mocks)
        self.assertIsNone(mocks.fetch_ndvi.call_args.kwargs["window"])

    def test_rabi_canopy_reads_green(self):
        with _MockedSources(ndvi=0.813) as mocks:
            profile = _build(mocks)
        self.assertEqual(profile.health_chip, health.GREEN)

    def test_falls_back_to_cached_ndvi_when_earth_engine_fails(self):
        from m0_field.sources.earth_engine import EarthEngineUnavailable

        with _MockedSources(ndvi_error=EarthEngineUnavailable("no creds")) as mocks:
            profile = _build(mocks, fallback_ndvi=0.62)

        self.assertEqual(profile.ndvi, 0.62)
        self.assertEqual(profile.sources["ndvi"]["status"], CACHED)
        self.assertIsNone(
            profile.ndvi_percentile,
            "a cached NDVI has no neighbour comparison to offer",
        )

    def test_percentile_reaches_the_profile(self):
        with _MockedSources(percentile=0.42, neighbourhood_median=0.55) as mocks:
            profile = _build(mocks)
        self.assertEqual(profile.ndvi_percentile, 0.42)
        self.assertEqual(profile.neighbourhood_median_ndvi, 0.55)

    def test_without_a_fallback_ndvi_is_unavailable_not_zero(self):
        from m0_field.sources.earth_engine import EarthEngineUnavailable

        with _MockedSources(ndvi_error=EarthEngineUnavailable("no creds")) as mocks:
            profile = _build(mocks)

        self.assertIsNone(profile.ndvi)
        self.assertEqual(profile.sources["ndvi"]["status"], UNAVAILABLE)


class TestSeededNpk(unittest.TestCase):
    """Phosphorus and potassium arrive only from the seed, and are labelled."""

    SEED = {"p": 14.2, "k": 265.0}

    def test_seeded_values_fill_the_gap(self):
        with _MockedSources() as mocks:
            profile = _build(mocks, seeded_soil=self.SEED)
        self.assertEqual(profile.soil.p, 14.2)
        self.assertEqual(profile.soil.k, 265.0)

    def test_seeded_npk_is_marked_seeded_not_live(self):
        with _MockedSources() as mocks:
            profile = _build(mocks, seeded_soil=self.SEED)
        self.assertEqual(profile.sources["soilNPK"]["status"], SEEDED)

    def test_a_measured_value_is_never_overwritten_by_the_seed(self):
        with _MockedSources(soil=Soil(ph=7.9, p=99.0)) as mocks:
            profile = _build(mocks, seeded_soil=self.SEED)
        self.assertEqual(profile.soil.p, 99.0)   # measured wins
        self.assertEqual(profile.soil.k, 265.0)  # seed fills only the gap




class TestDistrictSeed(unittest.TestCase):
    """The seeded P/K lookup must be geographically honest."""

    def test_finds_jind_for_the_demo_field(self):
        from m0_field.seed import district_for

        district = district_for(29.61, 76.11)
        self.assertIsNotNone(district)
        self.assertEqual(district["district"], "Jind")

    def test_returns_p_and_k_in_the_expected_bands(self):
        from m0_field.seed import seeded_soil_for

        soil = seeded_soil_for(29.61, 76.11)
        self.assertTrue(10 <= soil["p"] <= 25, "P should sit in the medium band")
        self.assertGreater(soil["k"], 280, "K is rated high for Jind")

    def test_refuses_to_proxy_a_distant_location(self):
        from m0_field.seed import seeded_soil_for

        # Brazil — a seeded Haryana average must not follow the pin abroad.
        self.assertIsNone(seeded_soil_for(-15.79, -47.88))


if __name__ == "__main__":
    unittest.main()


class TestClimateUnits(unittest.TestCase):
    """Earth Engine speaks SI; the contract speaks agronomy. Conversions matter."""

    def test_kelvin_becomes_celsius(self):
        from m0_field.sources.ee_climate import _celsius

        self.assertAlmostEqual(_celsius(305.1213), 31.97, places=2)
        self.assertIsNone(_celsius(None))

    def test_joules_become_megajoules(self):
        from m0_field.sources.ee_climate import _scaled

        self.assertAlmostEqual(_scaled(14_753_810.0, 1e-6), 14.75, places=2)

    def test_et0_magnitude_survives_era5_sign_convention(self):
        """ERA5 signs fluxes downward-positive, so potential evaporation is
        negative; an agronomist expects a positive millimetre figure."""
        from m0_field.sources.ee_climate import _shape

        shaped = _shape({"potential_evaporation_sum": -0.0047})
        self.assertAlmostEqual(shaped["et0MmPerDay"], 4.7, places=2)

    def test_vpd_is_zero_when_air_is_saturated(self):
        from m0_field.sources.ee_climate import _vpd_kpa

        # Dewpoint equal to air temperature means 100% humidity.
        self.assertEqual(_vpd_kpa(25.0, 25.0, 25.0), 0.0)

    def test_vpd_rises_as_air_dries(self):
        from m0_field.sources.ee_climate import _vpd_kpa

        humid = _vpd_kpa(35.0, 25.0, 24.0)
        dry = _vpd_kpa(35.0, 25.0, 5.0)
        self.assertGreater(dry, humid)

    def test_vpd_needs_every_input(self):
        from m0_field.sources.ee_climate import _vpd_kpa

        self.assertIsNone(_vpd_kpa(35.0, 25.0, None))

    def test_missing_bands_do_not_raise(self):
        from m0_field.sources.ee_climate import _shape

        shaped = _shape({})
        self.assertIsNone(shaped["surfaceTempDayC"])
        self.assertIsNone(shaped["vpdKpa"])
        self.assertEqual(shaped["soilWater"]["0_7cm"], None)


class TestSoilUncertainty(unittest.TestCase):
    """SoilGrids is a prediction; the contract must be able to say how wide."""

    PAYLOAD = {
        "properties": {
            "layers": [
                {
                    "name": "phh2o",
                    "unit_measure": {"d_factor": 10},
                    "depths": [
                        {
                            "label": "0-5cm",
                            "values": {"mean": 79, "Q0.05": 62, "Q0.95": 103},
                        }
                    ],
                }
            ]
        }
    }

    def test_parses_the_90_percent_interval(self):
        spread = soilgrids.parse_soil_range(self.PAYLOAD)
        self.assertEqual(spread["ph"], {"low": 6.2, "high": 10.3})

    def test_mean_still_parses_alongside_quantiles(self):
        self.assertEqual(soilgrids.parse_soil_payload(self.PAYLOAD).ph, 7.9)

    def test_absent_quantiles_yield_no_range_rather_than_a_fake_one(self):
        payload = {
            "properties": {
                "layers": [
                    {
                        "name": "phh2o",
                        "unit_measure": {"d_factor": 10},
                        "depths": [{"label": "0-5cm", "values": {"mean": 79}}],
                    }
                ]
            }
        }
        self.assertEqual(soilgrids.parse_soil_range(payload), {})


class TestRecoveredSignals(unittest.TestCase):
    """Signals that were fetched and silently discarded before."""

    def test_forecast_et0_reaches_the_profile(self):
        with _MockedSources() as mocks:
            profile = _build(mocks)
        self.assertEqual(profile.climate["et0Forecast7dMm"], 31.2)

    def test_surface_wetness_and_observed_rain_reach_the_profile(self):
        with _MockedSources() as mocks:
            profile = _build(mocks)
        self.assertEqual(profile.climate["surfaceWetness"], 0.49)
        self.assertEqual(profile.climate["observedRain30dMm"], 200.1)

    def test_terrain_is_split_out_of_the_climate_block(self):
        with _MockedSources() as mocks:
            profile = _build(mocks)
        self.assertEqual(profile.terrain["slopeDeg"], 1.98)
        self.assertNotIn("terrain", profile.climate)

    def test_finer_radiation_supersedes_the_coarser_source(self):
        """ERA5-Land at 11 km beats NASA POWER at ~50 km when both are present."""
        with _MockedSources() as mocks:
            profile = _build(mocks)
        self.assertEqual(profile.radiation_score, 0.475)
