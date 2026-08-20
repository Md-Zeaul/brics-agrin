"""Cloud Function entrypoint for M0 — field intelligence.

Deploy:
    gcloud functions deploy m0_field \
        --gen2 --runtime=python311 --region=asia-south1 \
        --source=backend --entry-point=m0_field_http \
        --trigger-http --allow-unauthenticated

The app calls this once per field and caches the result to Firestore; every
later screen reads the cache, so this is not on the hot path.
"""

from __future__ import annotations

import json
import os

from m0_field import build_field_profile
from m0_field.seed import seeded_soil_for

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
        )
    except ValueError as error:
        return (json.dumps({"error": str(error)}), 400, _JSON)

    return (json.dumps(profile.to_dict()), 200, _JSON)


_JSON = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
