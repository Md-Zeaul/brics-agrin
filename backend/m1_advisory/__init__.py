"""M1 — the AI farmer copilot.

Turns an M0 field profile into one spoken-language advisory. The model chooses
*which* advice; human-written templates supply the words in each language, so
the Hindi and Portuguese are correctly registered, the rendered text is
deterministic enough to pre-cache its audio, and a failed model call degrades to
the same templates chosen by rules instead of to nothing.
"""
