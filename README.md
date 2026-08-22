# AgriSetu

AI copilot for smallholder farmers, rolling the same intelligence up from one
field to a federated BRICS network. Prototype build against the specs in this
repo.

Specs: `AgriSetu_Build_Brief.docx` (what to build) · `AgriSetu_Tech_Spec.docx`
(contracts) · `AgriSetu_Data_Model_Spec.md` (datasets and model ids).

## Status

| Module | Screens | State |
|---|---|---|
| **M0 Field intelligence** | S1, S2 | **Live** — all six signals, NDVI included |
| **M1 AI Farmer Copilot** | S2 | **Live** — Gemini chooses, rules fall back. Voice deferred (#10) |
| App shell | S1–S10 | Navigable end to end; runtime language switching (en / hi / pt) |
| M2–M8 | S3–S10 | Not started — every screen is a stub naming its module and GitHub issue |

New here? [CONTRIBUTING.md](CONTRIBUTING.md) has setup, credentials, module
order and the branch workflow. Picking up mid-build? [HANDOFF.md](HANDOFF.md)
is the state of play in one file.

## Layout

    backend/            Python, stdlib + earthengine-api
      m0_field/         M0: sources, geometry, health rules, contract
      m1_advisory/      M1: signals, growth stage, doses, products,
                            templates, rules, Gemini chooser
      main.py           Cloud Function entrypoints (m0_field, m1_advisory)
      dev_server.py     local /m0 and /m1, no GCP needed
      run_local.py      CLI: build a profile, write the seed fallback
      trace_advisory.py CLI: every step from signal to sentence
      check_ee.py       CLI: Earth Engine credential preflight
      tests/            203 unit tests, offline
    app/                Flutter client
      lib/core/         shell: routes, language, build-time config
      lib/features/     one folder per module
    data/seed/          seeded/fallback data

## Run it

Terminal 1 — the M0 endpoint. Source `.env` and use the venv python, or NDVI
silently falls back (the system python has no `earthengine-api`):

    source .env && .venv/bin/python backend/dev_server.py    # localhost:8787/m0

Terminal 2 — the app:

    export PATH="$HOME/development/flutter/bin:$PATH"
    cd app && flutter run -d chrome

Or build one profile straight to stdout, with no app and no server:

    source .env && .venv/bin/python backend/run_local.py --verbose

Check Earth Engine credentials on their own:

    source .env && .venv/bin/python backend/check_ee.py

## Tests

    .venv/bin/python -m unittest discover -s backend/tests -t backend/tests   # 203
    cd app && flutter analyze && flutter test                                  # 131

## Configuration

All tunables are build-time defines in `app/lib/core/config.dart`:

    flutter run -d chrome \
      --dart-define=M0_ENDPOINT=https://...cloudfunctions.net/m0_field \
      --dart-define=MAPS_KEY=... \
      --dart-define=GEMINI_MODEL=gemini-2.5-flash

`GEMINI_MODEL` is deliberately one value: `gemini-2.5-flash` shuts down 16–20
October 2026, so anything running past mid-October switches to
`gemini-3.1-flash-lite`.

## What M0 produces

One cached field profile per field — the substrate M1, M3 and M5 all read:

    { fieldId, polygon, centroid, areaHa, ndvi,
      soil: { ph, n, p, k, cec, moisture, soc, clay },
      rainForecastMm, rainForecast7dMm, tempForecast[], radiationScore,
      healthChip: GREEN|YELLOW|RED, sources: { <signal>: {...} }, generatedAt }

`sources` carries per-signal provenance (`live` / `cached` / `seeded` /
`unavailable`) so the app — and anyone watching the demo — can tell which
numbers are real. Every source degrades independently: one failure marks one
signal unavailable instead of blanking the home screen.

### Data sources

| Signal | Source | Key needed |
|---|---|---|
| Soil pH, N, CEC, SOC, clay | ISRIC SoilGrids v2.0 | no |
| Rain + temperature forecast | Open-Meteo | no |
| Root-zone moisture, radiation | NASA POWER | no |
| NDVI | Sentinel-2 via Earth Engine | **yes** — configured, project `brics-agrin` |
| Advisory template choice | Gemini 2.5 Flash via Vertex AI (`asia-south1`) | **yes** — degrades to rules |

## M0 is complete

Every signal is live or explicitly seeded, both capture modes work, and the map
is the real thing.

| Signal | Source | Status |
|---|---|---|
| Boundary | farmer pin or drawn polygon | live |
| NDVI | Sentinel-2 via Earth Engine | live |
| Soil pH, N, CEC, SOC, clay | ISRIC SoilGrids v2.0 | live |
| Root-zone moisture, radiation | NASA POWER | live |
| Rain + temperature forecast | Open-Meteo | live |
| Phosphorus, potassium | farmer's soil card, else district survey | reported / seeded (no remote source exists) |

### Any crop, any country

M0 is not tied to Haryana or to wheat. Every data source is global, and the
parts that were region-specific have been generalised:

- **Health is relative, not absolute.** The chip ranks the field's NDVI against
  surrounding cropland (masked to farmland with ESA WorldCover) instead of
  comparing it to a fixed wheat threshold. "Behind most farms nearby" means the
  same thing for a rice paddy, a mango orchard and a wheat plot, and it
  self-corrects for season, drought and growth stage because the neighbours are
  living through the same ones. Absolute thresholds remain only as a fallback.
- **Fallow guard.** When the whole neighbourhood is below bare-soil NDVI the
  region is between crops, so the chip reports `no_active_crop` rather than
  ranking noise. Without this, every field in Mato Grosso reads RED in August.
- **32-crop registry** in `app/assets/crops.json`, searchable in English, Hindi
  and Portuguese, with free text accepted for anything unlisted.

Measured across three continents, same code, no per-country configuration:

| Location | NDVI | Percentile | Chip |
|---|---|---|---|
| Narwana, Haryana (wheat) | 0.579 | 0.598 | GREEN — healthy |
| Sorriso, Mato Grosso (soy, off-season) | 0.15 | 0.068 | YELLOW — no active crop |
| Pearl River delta, Guangdong (rice) | 0.541 | 0.647 | GREEN — healthy |

Soil pH came back 7.9 alkaline for Haryana and 4.9 acidic for the Cerrado,
which is exactly right for both — useful evidence the pipeline is sound.

Capture modes on S1:

- **Drop a pin** — a 1.5 ha square is derived from it. Fastest path, no typing.
- **Draw boundary** — tap each corner; undo and clear are available, and the
  area updates as the ring closes. The polygon is sent to M0 verbatim.

Run with the real map:

    source .env
    cd app && flutter run -d chrome --dart-define=MAPS_KEY=$MAPS_KEY

### Climate, water balance and terrain

Beyond NDVI, M0 reads the Earth Engine catalog for signals the point APIs
cannot resolve. Datasets were chosen by *measured* latency, not reputation —
probed 2026-08-19 at the demo field:

| Dataset | Resolution | Behind today | Gives |
|---|---|---|---|
| GPM IMERG v07 | 11 km | 1 day | observed rainfall |
| MODIS MOD11A1 | **1 km** | 2 days | measured land surface temperature |
| ERA5-Land | 11 km | 6–8 days | soil water at 3 depths, radiation, ET₀, dewpoint |
| SRTM | 30 m | static | elevation, slope, aspect |

Rejected after measuring, despite being the obvious picks:
**SMAP** soil moisture is 418 days stale, **MODIS phenology** 961 days, and
**CHIRPS** — named in the Tech Spec — runs 19 days behind, which is fine for
seasonal normals and wrong for "did it rain last week".

The point of this is the **water balance**: rain received minus ET₀. The demo
field took 200 mm over 30 days yet ran a deficit in the last 7 — 3.7 mm of rain
against 5.39 mm/day of demand. Rainfall alone cannot say that, and an
irrigation call turns on exactly that number.

Same code in Brazil, no configuration, showing the inverse water profile of a
dry season against a monsoon:

| | Haryana (monsoon) | Mato Grosso (dry season) |
|---|---|---|
| VPD | 0.92 kPa | 2.42 kPa |
| ET₀ | 5.39 mm/day | 10.53 mm/day |
| Rain, 7 days | 3.7 mm | 0 mm |
| Soil water 0–7 cm | 0.342 | 0.241 |
| Soil water 28–100 cm | 0.148 | 0.326 |
| Soil pH | 7.9 (alkaline) | 4.9 (acidic) |

India is wet at the surface and dry below; Brazil is the exact opposite. Nobody
configured that — it falls out of the data.

**One coarse-pixel trap worth knowing:** an 11 km pixel dwarfs a 1.5 ha field,
so no pixel centroid lands inside it and `reduceRegion` returns null. Every
coarse read is taken over the centroid buffered to at least one pixel.

### What "live" actually means

Only NDVI is a measurement of *your* field. The rest are freshly fetched, which
is what `live` means — not field-sampled:

| Signal | True resolution | What it is |
|---|---|---|
| NDVI | 10 m | Genuine measurement of this field |
| Soil pH, N, CEC | 250 m | Global model prediction, not a sample |
| Moisture, radiation | ~50 km | Regional reanalysis |
| Rain, temperature | ~10 km | Forecast model |
| P, K | field or district | Farmer's soil card, else district average |

**Soil values are predictions, and M0 now says how uncertain.** SoilGrids
publishes a 90% interval alongside its mean, and it is wide: pH at the demo
field is mean 7.9 with an interval of **6.2–10.3** — spanning slightly acidic
to strongly alkaline, which is opposite agronomic advice. S2 shows
"7.9 (likely 6.2-10.3)" rather than implying precision the model lacks. Brazil,
by contrast, comes back 4.9 with a tight 4.1–5.9, so the interval carries real
information about where the model is confident.

Known limits, none blocking:

- `google_maps_flutter` has no macOS implementation, so the desktop target
  always uses the schematic renderer. The loader accounts for this deliberately.
- The full S1 to S2 click-through in a browser has not been exercised
  end-to-end; each widget, the HTTP endpoint and both boundary modes are
  verified separately.
- MODIS day-time land surface temperature is often cloud-masked in monsoon
  season, so S2 falls back to the night reading under the same label. The value
  is real either way, but day and night differ by more than the label admits.

Closed since: drawn boundaries are now rejected if they cross themselves. A
bow-tie does not merely under-report area — the two lobes wind in opposite
directions and the shoelace sum cancels to **0.0 ha**, which every per-hectare
figure downstream would then divide by. `is_simple` guards it in
`backend/m0_field/geometry.py`, `isSimple` mirrors it in Dart so S1 disables
Confirm and says "Lines cross", and `build_field_profile` refuses it with a 400
regardless of which client calls.

## M1 is live

The advisory card on S2. One field profile in, one situation line and up to two
actions out, in English, Hindi or Portuguese.

### The model picks; it never writes

    signals → eligible templates → a chooser picks from them → render

Gemini sees only the templates the data already supports and returns ids from
that list. It is never asked what the farmer should do, only which of the
applicable, human-written recommendations fits best. The consequences are the
point:

- **A hallucinated template id is a no-op.** Anything outside the eligible set
  is discarded rather than corrected, and the rules chooser decides instead.
- **Hindi and Portuguese are written by a person**, so the agricultural
  register is right. A machine translation of "top dressing" or "tillering" is
  confidently wrong in both.
- **The rendered text is deterministic**, so every line can be pre-cached for
  TTS, and a test asserts which template was chosen rather than how a sentence
  came out.
- **Rules are a complete fallback, not a sanity check.** With Gemini disabled,
  unreachable or returning nonsense, the same rules choose from the same
  templates and the farmer still gets a card. On a bad day they *are* M1.

Five tests drive a deliberately misbehaving chooser — inventing an id, naming
an ineligible one, raising, pairing two templates on the same topic, pairing
two that contradict each other — and assert the card survives each.

Gemini earns its place on the ties. On the demo field the rules picked
`topdress_window + irrigation.watch`, a tie broken by file order. Gemini picked
`topdress_window + soil.alkaline`, pairing the urea instruction with the
placement advice that stops pH 7.9 soil wasting it: *"the crop is in its main
growth phase and needs fertilizer, and the soil pH requires a specific
application method."*

### Absence is the eligibility test

A signal whose M0 source came back `unavailable` is not carried forward as
null — it is **absent**, and any template requiring it is ineligible before its
condition is even evaluated. There is no null check anywhere, because presence
in the signal dict *is* the check.

The same mechanism does agronomic work. Legumes fix their own nitrogen, so the
urea dose signal is simply withheld for soybean, chickpea, lentil, groundnut,
pigeon pea, green gram and common bean — and every template that quotes a dose
becomes ineligible through exactly the path a missing satellite reading takes.
That caught a template nobody was thinking about: `soil.alkaline`, whose advice
is about how to place urea, which a chickpea grower cannot use.

### Advice is a quantity, not a verb

"Plan a nitrogen top-dressing" is not an instruction. The card says *"spread 85
kg of urea per hectare, then irrigate lightly to wash it in"*, and every number
is arithmetic over a named rate — urea is 46% nitrogen, wheat wants 120 kg N/ha
for the season, the vegetative split is a third of it. Rates are published
extension figures, marked `seeded`, and the copy says so.

### Sowing date decides what may be said

`stage.py` holds a 21-crop calendar and places the crop in one of
establishment / vegetative / reproductive / filling / maturity. It gates what
is sayable, which fixed three real defects:

- Nitrogen at grain fill delays maturity and costs grain quality, and the thin
  canopy that would have triggered it is ordinary senescence rather than
  hunger. Dose templates are now vegetative-only.
- A ripening field was being flagged as failing against its neighbours.
- At maturity the card could say "stop irrigating, harvest in 6 days" and
  "irrigate 25 mm" at once. Templates now declare conflicts by id or topic, and
  a contradictory pair is dropped whether the rules or the model chose it.

### It remembers what the field has already had

S1 optionally asks what has already been applied and when the field was last
watered — the two facts no satellite can supply. Products differ enormously:
two bags an acre of urea is 102 kg N/ha, most of a wheat season, while two bags
of DAP is 40 kg and covers the phosphorus too.

The input is a ladder, and every rung is a legitimate place to stop:

| Answered | Bought |
|---|---|
| a date | the next dose is held back 21 days |
| + a product | potash stops triggering that hold; phosphorus advice is withheld where DAP went on |
| + a quantity | the season's remaining nitrogen is arithmetic, not a general rate |

"Don't remember" is a real answer at every rung and degrades to the one below.
Manure has no quantity path at all — it is spread by the trolley and its
analysis depends on what the animals ate, so a figure from it would be a guess
in the costume of an analysis. A farmer who skips the control entirely gets
exactly the advisory they got before it existed.

Suppression alone would be half a job, so each withheld recommendation becomes
advice instead of silence:

    no log            → "Spread 85 kg of urea per hectare"
    DAP 1 bag/acre    → "22 of roughly 120 kg … spread 85 kg"
    urea 2 bags/acre  → "102 of roughly 120 kg … spread 40 kg"
    urea 3 bags/acre  → "Do not buy more urea for this crop"
    urea 9 days ago   → "next split due in about 12 days"
    watered yesterday → "Do not irrigate again yet. Dig to spade depth first"

### Tracing one card

Every step from raw signal to rendered sentence, in one command:

    .venv/bin/python backend/trace_advisory.py --sown 2026-06-20 \
        --fertilised 2026-08-12:urea:1 --irrigated 2026-08-20 --language hi

Eight sections: input, sources, signals, derived, gates, choice, rendered, and
what the advice rests on. `--pin lat,lng` builds a fresh profile instead of
reading the fixture.

### Known limits

- **Voice is deferred** (#10). The Build Brief asks for a speaker button and a
  mic; M1 ships text-only. The templates are deterministic precisely so the TTS
  clips can be pre-cached when voice lands.
- **No free-form Q&A, deliberately.** Cut for grounding risk — mandi prices we
  do not have, pesticide doses that can cause real harm — and for the six
  seconds of dead air a full STT → LLM → TTS round trip costs on stage.
- **Season nitrogen rates are general.** They are the published figures an
  extension service starts from, not a prescription for one field, and variety,
  previous crop and organic matter all move them. Everything derived from them
  is marked `seeded` and the copy repeats it.

## NDVI: which reading to show

    .venv/bin/python backend/run_local.py                  # live, last 30 days
    .venv/bin/python backend/run_local.py --season rabi    # peak wheat canopy
    .venv/bin/python backend/run_local.py --ndvi-start 2026-02-01 --ndvi-end 2026-03-01

Wheat in Haryana is Rabi (sown Nov, harvested Apr), so an August reading
measures whatever is in the ground now — not wheat. `RABI_PEAK_WINDOW` in
`backend/m0_field/sources/earth_engine.py` holds the demo window.
