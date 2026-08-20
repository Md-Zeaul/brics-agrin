"""Earth Engine preflight — does M0 have everything it needs for live NDVI?

    GCP_PROJECT=my-project GCP_SA_JSON=~/.config/agrisetu/gcp-sa.json \
        .venv/bin/python backend/check_ee.py

Runs the same call path M0 uses and reports the first thing that is wrong, so a
credential problem is diagnosed in one step instead of surfacing as a silent
fallback to cached NDVI.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

DEMO_PIN = (29.61, 76.11)

OK = "  ok  "
FAIL = " FAIL "


def report(status: str, message: str) -> None:
    print(f"[{status}] {message}")


def main() -> int:
    print("Earth Engine preflight for M0\n")

    project = os.environ.get("GCP_PROJECT")
    key_path = os.environ.get("GCP_SA_JSON") or os.environ.get(
        "GOOGLE_APPLICATION_CREDENTIALS"
    )

    if not project:
        report(FAIL, "GCP_PROJECT is not set")
        return 1
    report(OK, f"GCP_PROJECT = {project}")

    if not key_path:
        report(FAIL, "GCP_SA_JSON is not set (path to the service-account JSON key)")
        return 1

    key_file = Path(key_path).expanduser()
    if not key_file.exists():
        report(FAIL, f"key file not found: {key_file}")
        return 1
    report(OK, f"key file found: {key_file}")

    try:
        key = json.loads(key_file.read_text())
    except json.JSONDecodeError as error:
        report(FAIL, f"key file is not valid JSON: {error}")
        return 1

    if key.get("type") != "service_account":
        report(FAIL, f"key type is {key.get('type')!r}, expected 'service_account' "
                     "— this looks like an OAuth client, not a service account")
        return 1
    report(OK, f"service account: {key.get('client_email')}")

    if key.get("project_id") and key["project_id"] != project:
        report(FAIL, f"key belongs to project {key['project_id']!r} "
                     f"but GCP_PROJECT is {project!r}")
        return 1

    try:
        import ee
    except ImportError:
        report(FAIL, "earthengine-api not installed — pip install earthengine-api")
        return 1
    report(OK, f"earthengine-api {ee.__version__}")

    # Everything below exercises the real M0 call path.
    os.environ["GCP_SA_JSON"] = str(key_file)
    from m0_field.geometry import square_polygon_around
    from m0_field.sources.earth_engine import EarthEngineUnavailable, fetch_ndvi

    polygon = square_polygon_around(*DEMO_PIN, area_ha=1.5)

    try:
        ndvi, provenance = fetch_ndvi(polygon)
    except EarthEngineUnavailable as error:
        report(FAIL, str(error))
        print("\n" + _diagnose(str(error)))
        return 1

    report(OK, f"NDVI = {ndvi}  ({provenance.source})")
    print("\nEarth Engine is live. Run the profile with the same env vars set:")
    print("    .venv/bin/python backend/run_local.py")
    return 0


def _diagnose(error: str) -> str:
    lowered = error.lower()
    if "not registered" in lowered or "register" in lowered:
        return ("The project is not registered for Earth Engine. Register it at\n"
                "https://code.earthengine.google.com/register  — enabling the API\n"
                "is a separate step and is not sufficient on its own.")
    if "permission" in lowered or "403" in lowered or "forbidden" in lowered:
        return ("The service account lacks Earth Engine access. Grant it\n"
                "  Earth Engine Resource Viewer   (roles/earthengine.viewer)\n"
                "at project level in IAM. If the error mentions serviceusage, also add\n"
                "  Service Usage Consumer         (roles/serviceusage.serviceUsageConsumer)")
    if "no cloud-free" in lowered:
        return ("Credentials work — there were simply no cloud-free Sentinel-2 pixels\n"
                "in the window. Widen LOOKBACK_DAYS or raise MAX_CLOUD_PCT in\n"
                "backend/m0_field/sources/earth_engine.py")
    return "Unexpected failure — rerun with the full traceback for detail."


if __name__ == "__main__":
    raise SystemExit(main())
