"""Local M0 endpoint — stdlib only, no GCP, no pip install.

    python3 backend/dev_server.py            # serves on http://localhost:8787

Mirrors the Cloud Function in main.py so the Flutter app can be developed and
demoed against a real M0 endpoint before Cloud Functions is provisioned. The
app points at this in dev and at the deployed function in prod; the JSON is
byte-for-byte the same shape.
"""

from __future__ import annotations

import json
import logging
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from m0_field import build_field_profile  # noqa: E402
from m0_field.seed import seeded_soil_for  # noqa: E402

PORT = 8787
DEMO_PIN = {"lat": 29.61, "lng": 76.11}

log = logging.getLogger("m0.dev")


def _district_seed(body: dict) -> dict | None:
    """Fill phosphorus/potassium from district data, which no source provides."""
    if body.get("polygon"):
        ring = body["polygon"]
        lat = sum(p[0] for p in ring) / len(ring)
        lng = sum(p[1] for p in ring) / len(ring)
    elif body.get("pin"):
        lat, lng = body["pin"]["lat"], body["pin"]["lng"]
    else:
        return None
    return seeded_soil_for(lat, lng)


def _window(body: dict) -> tuple | None:
    """Optional NDVI date window: {"ndviWindow": ["2026-01-15", "2026-03-15"]}."""
    window = body.get("ndviWindow")
    if isinstance(window, (list, tuple)) and len(window) == 2:
        return tuple(window)
    return None


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):  # noqa: N802 - BaseHTTPRequestHandler naming
        self._send(204, b"")

    def do_GET(self):  # noqa: N802
        """GET /m0 builds the demo field, so a browser can hit it directly."""
        if self.path.split("?")[0] not in ("/m0", "/"):
            return self._json(404, {"error": "not found"})
        return self._build({"pin": DEMO_PIN})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._json(400, {"error": "body must be JSON"})
        return self._build(body)

    def _build(self, body: dict):
        if not body.get("pin") and not body.get("polygon"):
            body["pin"] = DEMO_PIN
        try:
            profile = build_field_profile(
                pin=body.get("pin"),
                polygon=body.get("polygon"),
                field_id=body.get("fieldId", "field-demo-narwana"),
                plot_ha=body.get("plotHa", 1.5),
                fallback_ndvi=body.get("fallbackNdvi"),
                seeded_soil=body.get("seededSoil") or _district_seed(body),
                ndvi_window=_window(body),
                crop=body.get("crop"),
            )
        except ValueError as error:
            return self._json(400, {"error": str(error)})
        except Exception as error:  # never leave the app hanging
            log.exception("profile build failed")
            return self._json(500, {"error": str(error)})

        return self._json(200, profile.to_dict())

    def _json(self, status: int, payload: dict):
        self._send(status, json.dumps(payload).encode("utf-8"))

    def _send(self, status: int, body: bytes):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def log_message(self, fmt, *args):
        log.info("%s - %s", self.address_string(), fmt % args)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(f"M0 dev server on http://localhost:{PORT}/m0")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
