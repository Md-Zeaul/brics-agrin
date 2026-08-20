"""M0 — Field intelligence.

Turns a dropped pin into a cached field profile: boundary, NDVI, soil,
rainfall and temperature. Every other module reads this output.
"""

from .contract import FieldProfile, Provenance, Soil
from .profile import build_field_profile

__all__ = ["FieldProfile", "Provenance", "Soil", "build_field_profile"]
