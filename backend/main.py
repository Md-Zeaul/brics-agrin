"""Cloud Function entrypoints — M0 field intelligence and M1 advisory.

Deploy:
    gcloud functions deploy m0_field \
        --gen2 --runtime=python311 --region=asia-south1 \
        --source=backend --entry-point=m0_field_http \
        --trigger-http --allow-unauthenticated

    gcloud functions deploy m1_advisory \
        --gen2 --runtime=python311 --region=asia-south1 \
        --source=backend --entry-point=m1_advisory_http \
        --trigger-http --allow-unauthenticated

The app calls M0 once per field and caches the result; every later screen reads
the cache, so it is not on the hot path. M1 takes that cached profile back and
returns the day's advisory — which is why the model key lives here and never in
the Flutter bundle. The app is a web build in a public repo; a key it could
read is a key anyone can.
"""

from __future__ import annotations

import json
import os

from m0_field import build_field_profile
from m0_field.seed import seeded_soil_for
from m1_advisory.advisory import RULES_SOURCE, build_advisory
from m1_advisory.gemini import GeminiChooser, gemini_available

# Fallback NDVI for the demo field while Earth Engine access is pending.
FALLBACK_NDVI = float(os.environ.get("FALLBACK_NDVI", "0.62"))


def m0_field_http(request):
    """HTTP handler. Accepts {"pin": {...}} or {"polygon": [...]}."""
    try:
        body = request.get_json(silent=True) or {}
    except Exception:
        body = {}

    pin = body.get("pin")
    polygon = body.get("polygon")
    if not pin and not polygon:
        return (json.dumps({"error": "provide a pin {lat,lng} or a polygon"}), 400, _JSON)

    seeded = body.get("seededSoil")
    if seeded is None:
        if polygon:
            lat = sum(p[0] for p in polygon) / len(polygon)
            lng = sum(p[1] for p in polygon) / len(polygon)
        else:
            lat, lng = pin["lat"], pin["lng"]
        seeded = seeded_soil_for(lat, lng)

    window = body.get("ndviWindow")
    if not (isinstance(window, (list, tuple)) and len(window) == 2):
        window = None

    try:
        profile = build_field_profile(
            pin=pin,
            polygon=polygon,
            field_id=body.get("fieldId", "field-demo"),
            fallback_ndvi=body.get("fallbackNdvi", FALLBACK_NDVI),
            seeded_soil=seeded,
            ndvi_window=tuple(window) if window else None,
            crop=body.get("crop"),
            sowing_date=body.get("sowingDate"),
        )
    except ValueError as error:
        return (json.dumps({"error": str(error)}), 400, _JSON)

    return (json.dumps(profile.to_dict()), 200, _JSON)


def m1_advisory_http(request):
    """HTTP handler. Accepts {"profile": {...}, "language", "sowingDate"}.

    Takes the profile rather than a pin: rebuilding one costs twenty seconds of
    satellite and reanalysis calls, the caller already holds it, and passing it
    back guarantees the advice describes the reading the farmer is looking at
    rather than a fresher one they have not seen.
    """
    try:
        body = request.get_json(silent=True) or {}
    except Exception:
        body = {}

    profile = body.get("profile")
    if not isinstance(profile, dict):
        return (json.dumps({"error": "provide a 'profile' object from M0"}), 400, _JSON)

    chooser = GeminiChooser() if gemini_available() else None
    advisory = build_advisory(
        profile,
        language=body.get("language", "en"),
        sowing_date=body.get("sowingDate"),
        chooser=chooser,
        chooser_source=chooser.source if chooser else None,
    )

    # Say so in the payload when the model was tried and did not answer. A demo
    # claiming live AI while quietly running on rules is worse than one running
    # on rules openly, and from outside the two look the same.
    if chooser is not None and chooser.last_error and (
        advisory.chosen_by.source == RULES_SOURCE
    ):
        advisory.chosen_by.note = (
            f"{advisory.chosen_by.note} — model unavailable: {chooser.last_error}"
        )

    return (json.dumps(advisory.to_dict()), 200, _JSON)


_JSON = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
