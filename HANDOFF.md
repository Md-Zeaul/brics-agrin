# AgriSetu — state of play

Written 2026-08-22, at commit `c5710e8`. Read this first in a fresh session;
[CONTRIBUTING.md](CONTRIBUTING.md) has the setup detail, [README.md](README.md)
has what M0 and M1 actually do.

**Where things stand.** M0 (field intelligence) and M1 (advisory) are built and
live on real data. The S1–S10 spine navigates end to end. M2–M8 have not been
started — every one of their screens is a stub that names its module and its
GitHub issue. 203 Python tests and 131 Dart tests pass; `flutter analyze` is
clean.

---

## Start here

Two terminals, from the repo root.

    # 1 — backend: /m0 and /m1
    source .env && .venv/bin/python backend/dev_server.py       # :8787

    # 2 — app
    export PATH="$HOME/development/flutter/bin:$PATH"
    cd app && flutter run -d chrome

Confirm nothing rotted before writing code:

    source .env && .venv/bin/python backend/check_ee.py
    .venv/bin/python -m unittest discover -s backend/tests -t backend/tests
    cd app && flutter analyze && flutter test

One advisory, decided step by step, with no app and no browser — the fastest
way to see whether a change did what you meant:

    .venv/bin/python backend/trace_advisory.py --sown 2026-06-20 --language hi

---

## Five environment facts that will cost you an hour each

**Flutter is not on `PATH`.** It lives at `~/development/flutter`. Every
Flutter command needs `export PATH="$HOME/development/flutter/bin:$PATH"`
first. Web and macOS are the only configured targets.

**Use `.venv/bin/python`, never `python3`.** The system Python has no
`earthengine-api`, and its absence does not raise — NDVI degrades to
`unavailable`, the health chip still renders off the other signals, and nothing
tells you the satellite was never asked.

**Bytecode caching will lie to you.** This venv is built on macOS's system
Python, which sets `sys.pycache_prefix`, so `.pyc` files live in
`~/Library/Caches/com.apple.python$PWD` and deleting `__pycache__` in the repo
does nothing. Python invalidates on source size and mtime, and mtime has
one-second resolution — a scripted edit changing neither (`bag_kg=45` to
`bag_kg=50`) is invisible, and the old code keeps running while the file reads
correctly on disk. If an edit seems not to take effect:

    rm -rf ~/Library/Caches/com.apple.python$PWD

**`gcloud auth application-default login` sets no environment variable.** It
writes `~/.config/gcloud/application_default_credentials.json` and says
nothing. `earth_engine_ready()` checks that file for exactly this reason.

**An enabled API is not a permission.** Two separate switches. Enabling
`aiplatform.googleapis.com` without granting `roles/aiplatform.user` fails as
`403 aiplatform.endpoints.predict denied`, which reads like a billing problem
and is not one. Both are set for Vertex today; TTS and STT are enabled for
neither, which is why #10 is blocked.

---

## The four ideas the codebase is built on

Preserve these in anything new. They are not stylistic — each one is load
bearing and each was arrived at by hitting the alternative.

**1 · Per-signal provenance with independent degradation.** Every number
carries `live` / `cached` / `reported` / `seeded` / `unavailable`, and one
source failing marks one signal unavailable rather than blanking a screen. A
number with no source behind it is a claim, not a finding.

**2 · Absence is the eligibility test.** A signal whose source came back
`unavailable` is *omitted* from the extracted dict, not set to null. Templates
declaring it become ineligible through the data structure rather than through a
null check — there is no null check anywhere. The same mechanism does agronomic
work: legumes fix their own nitrogen, so the urea dose signal is simply withheld
for them, and every dose-quoting template goes ineligible by the same path a
missing satellite reading takes.

**3 · The model chooses; it never authors.** Build the eligible set from the
data, let Gemini pick from it, discard anything outside it. A hallucinated
template id is a no-op. This is why a weaker or cheaper model would still be
safe here, and why the Hindi and Portuguese are correctly registered — a person
wrote them.

**4 · Rules are a complete fallback, not a sanity check.** With the model
disabled, unreachable, or returning nonsense, the same rules choose from the
same templates and the farmer still gets a card. On a bad day they *are* M1.
When the model was tried and did not answer, the payload says so — a demo
claiming live AI while quietly running on rules is worse than one running on
rules openly, and from outside the two look identical.

---

## What is left, in the order I would do it

Estimates are focused hours, and assume the patterns above are reused rather
than reinvented.

| # | Module | Screens | Est. | Note |
|---|---|---|---|---|
| #1 | `data/seed-data.json` | — | 3–4 h | **Tightest blocker.** Four modules read it; everything else outstanding is one module deep |
| #3 | M2 Disease Diagnostic | S3, S4 | 1.5 d | Largest single risk — see below |
| #4 | M3 Regenerative Advisor | S5 | 4 h | Reuses `signals.py`, `stage.py`, `doses.py` wholesale |
| #5 | M4 Seed Intelligence | S5 | 2 h | Pure lookup over #1's rows |
| #9 | M8 Farm Digital Twin | S6 | 2 h | Sliders re-running M3 |
| #6 | M5 Nervous System | S7, S8 | 3–4 h | Seeded tiles + one live signal |
| #7 | M6 Economic Engine | S9 | 2 h | Seeded scenario |
| #8 | M7 Federated Agri-DPI | S10 | 2–3 h | 20% of the score. The Portuguese flip already works |
| #10 | M1b Voice | S2 | 3 h | Blocked on two disabled APIs |

**M2 is the schedule.** Vertex AutoML Vision means sourcing a dataset,
uploading, training for hours on the critical path where nothing else can
proceed, deploying an endpoint, then debugging it. A cheaper route exists and
was **considered and declined on 2026-08-21** — sending the leaf photo to
Gemini 2.5 Flash with a closed list of diseases plausible for that crop, which
is the same chooser inversion M1 already runs, costs about two hours, works on
crops you never trained on, and reuses `gemini.py` nearly wholesale. It loses
the offline TFLite path. Do not re-propose this unless asked; it is recorded
here so the reasoning is not rediscovered from scratch.

---

## Decisions already taken — do not relitigate

| Decision | Where it lives |
|---|---|
| **Flutter**, not React PWA | offline persistence, camera, on-device TFLite |
| **`gemini-2.5-flash`** in a single config value | shuts down 16–20 Oct 2026 → `gemini-3.1-flash-lite` |
| Gemini runs **server-side only** | app is web and the repo is public; a browser key is a committed key |
| Model returns **structure, never prose** | `{templateId, slots, urgency, signalsUsed}` |
| **No free-form Q&A** | grounding risk + 6 s of dead air on stage |
| **Voice deferred**, text-only for now | #10 |
| Advisory copy lives in `templates.py`, **not** the asset pack | a template declares its required signals, stages and conflicts; splitting copy from those lets them drift silently |
| **Sole developer** | all issues assigned to Md-Zeaul; stubs name their issue, not a person |
| **Nothing dropped from scope** | confirmed 2026-08-21 |

### Parked, discussed but not decided

A local **Gemma 3 via Ollama** as a second `Chooser` implementation — a Google
model, multilingual unlike CropSeek, roughly two hours, and safe because the
existing guardrails make a bad pick a no-op rather than bad advice. It would
give a three-tier story: Vertex Gemini (cloud) → local Gemma (edge node) →
deterministic rules (nothing at all), demonstrable by turning wifi off on
stage, and it makes M7's "the model travels to the data" claim literal.

Fine-tuning was argued **against**: a day minimum, it lands on the selection
step which is not the bottleneck, it degrades the JSON adherence M1 actually
depends on, and it could not be honestly evaluated in the time available. The
machine would take it — M2, 24 GB, 325 GB free — but no decision was taken.

---

## Traps already hit, so you do not hit them twice

**Gemini thinking mode.** `maxOutputTokens` counts thinking tokens, so with
thinking on the model returns HTTP 200 with no `parts` at all, having spent the
whole budget reasoning. `thinkingConfig: {thinkingBudget: 0}` is load bearing:
10.9 s → 1.6 s.

**Flutter web CanvasKit fonts.** Roboto carries no Devanagari, and CanvasKit
fetches Noto from `fonts.gstatic.com` at runtime — so offline Hindi renders as
empty boxes. Noto Sans Devanagari is bundled in `app/assets/fonts/` and
verified by a test that parses the TrueType cmap directly.

**`Scaffold.bottomNavigationBar` passes loose constraints.** A `Center` inside
it expands to full screen height and leaves the body with none. Give it an
explicit height.

**`CrossAxisAlignment.stretch` inside a scroll view** forces infinite height and
throws.

**A coarse pixel dwarfs a small field.** An 11 km ERA5 pixel over a 1.5 ha plot
means no pixel centroid lands inside it and `reduceRegion` returns null. Every
coarse read buffers the centroid to at least one pixel.

**A self-crossing polygon does not merely under-report area.** The two lobes
wind in opposite directions and the shoelace sum cancels to 0.0 ha, which every
per-hectare figure downstream would divide by. Guarded in three places.

**`Provenance` must be stored as `.to_dict()`.** It serialises fine in Python
and raises at the endpoint.

---

## Where things are

    backend/m0_field/        M0 — sources/, geometry, health, seed, contract
    backend/m1_advisory/     M1 — signals, stage, doses, products, templates,
                                  rules, advisory, gemini, contract
    backend/tests/           203 tests; fixtures/live_profile_narwana.json is a
                             captured real M0 response
    backend/trace_advisory.py  every step from signal to sentence
    backend/check_ee.py        credential preflight
    app/lib/core/            routes, l10n, theme, config, module_stub
    app/lib/features/field/  S1 capture, S2 home
    app/lib/features/copilot/  the advisory card and its client/cache
    app/test/                131 tests across 7 files

17 templates × 3 languages; 30 signals extracted from the live demo field.

**Test runner is `unittest`, not pytest.**

    .venv/bin/python -m unittest discover -s backend/tests -t backend/tests

---

## The demo is the acceptance test

Eight steps, and every one must be reachable. S1 → S2 work today; S3 onward are
stubs.

1. **S1** — drop a pin or draw a boundary, pick a crop, set the sowing date
2. **S2** — health chip, live signals with provenance, today's advisory
3. **S3/S4** — photograph a leaf, get a diagnosis (M2)
4. **S5** — ranked crop options with a seed variety (M3 + M4)
5. **S6** — move a slider, watch the ranking change (M8)
6. **S7/S8** — district risk map, drill into a region (M5)
7. **S9** — national food-security scenario (M6)
8. **S10** — flip to Portuguese, show the Brazil node (M7)

**Rubric weights**, which is why the order above is what it is: AI/Technical
Execution 25%, Problem–Solution Fit 20%, Cross-Border 20%, Deployability 20%,
Impact 10%, Presentation 5%.

---

## Open, unactioned

- **The two `.docx` specs are in public git history** (`AgriSetu_Build_Brief.docx`,
  `AgriSetu_Tech_Spec.docx`). Flagged several times, deliberately not actioned —
  removing them means rewriting history on a public repo. Your call.
- **A world-readable service-account key** sits at
  `/Users/mdzea/Downloads/brics-agrin-59462b27134b.json`, mode 644, outside the
  repo. Deletion was recommended and not executed; it is your credential. The
  copy in use is at `~/.config/agrisetu/gcp-sa.json`, mode 600. Nothing in the
  repo references either — ADC is the path in use.
- **M5's drought rule is uncomputable** without CHIRPS or TerraClimate normals.
  Deferred; the seeded tiles cover it for the demo.
- **The full S1 → S2 click-through has not been exercised in a browser** end to
  end. Every widget, both boundary modes and the HTTP endpoints are verified
  separately.
