"""Which Google credential this machine has, if any.

Shared by M0's Earth Engine calls and M1's Vertex calls so the two cannot
disagree about whether the project is reachable — and so a collaborator who
authenticated once is authenticated for both.
"""

from __future__ import annotations

import os


def credentials_present() -> bool:
    from m0_field.sources.earth_engine import earth_engine_ready

    return earth_engine_ready() or bool(os.environ.get("GCP_SA_JSON"))
