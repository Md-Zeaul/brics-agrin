"""Tiny HTTP helper: stdlib-only JSON GET with timeout and retries.

Deliberately dependency-free so the Cloud Function cold-starts fast and the
package runs on a bare Python with no pip install.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_TIMEOUT_S = 30
DEFAULT_RETRIES = 2


class FetchError(RuntimeError):
    """Raised when a source cannot be reached or returns unusable content."""


def get_json(
    url: str,
    params: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT_S,
    retries: int = DEFAULT_RETRIES,
) -> dict:
    """GET `url` and parse JSON. Retries on transient failures with backoff.

    `params` values that are lists are expanded into repeated keys, which is
    how SoilGrids expects multiple `property=` / `depth=` selectors.
    """
    if params:
        pairs: list[tuple[str, str]] = []
        for key, value in params.items():
            if isinstance(value, (list, tuple)):
                pairs.extend((key, str(v)) for v in value)
            else:
                pairs.append((key, str(value)))
        url = f"{url}?{urllib.parse.urlencode(pairs)}"

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(
                url, headers={"Accept": "application/json", "User-Agent": "AgriSetu/0.1"}
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as error:
            last_error = error
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))

    raise FetchError(f"GET {url} failed after {retries + 1} attempts: {last_error}")
