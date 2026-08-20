"""External data sources behind M0.

Each module exposes one fetch function returning (value, Provenance) so the
orchestrator can degrade any single source without losing the whole profile.
"""
