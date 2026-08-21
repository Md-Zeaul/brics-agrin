# AgriSetu

AI copilot for smallholder farmers, rolling the same intelligence up from one
field to a federated BRICS network. Prototype build against the specs in this
repo.

Specs: `AgriSetu_Build_Brief.docx` (what to build) · `AgriSetu_Tech_Spec.docx`
(contracts) · `AgriSetu_Data_Model_Spec.md` (datasets and model ids).

## Status

| Module | State |
|---|---|
| **M0 Field intelligence** | **Built and fully live** — all six signals, NDVI included |
| App shell | S1–S10 navigable; runtime language switching (en / hi / pt) |
| M1–M8 | Not started — S3–S10 are stubs naming the module and its owner |

New here? [CONTRIBUTING.md](CONTRIBUTING.md) has setup, credentials, who owns
which module, and the branch workflow.

## Layout

    backend/            M0 field intelligence (Python, stdlib + earthengine-api)
      m0_field/         package: sources, geometry, health rules, contract
      main.py           Cloud Function entrypoint
      dev_server.py     local M0 endpoint, no GCP needed
      run_local.py      CLI: build a profile, write the seed fallback
      tests/            77 unit tests, offline
    app/                Flutter client
      lib/core/         shell: routes, language, build-time config
      lib/features/     one folder per module, owned whole
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

## NDVI: which reading to show

    .venv/bin/python backend/run_local.py                  # live, last 30 days
    .venv/bin/python backend/run_local.py --season rabi    # peak wheat canopy
    .venv/bin/python backend/run_local.py --ndvi-start 2026-02-01 --ndvi-end 2026-03-01

Wheat in Haryana is Rabi (sown Nov, harvested Apr), so an August reading
measures whatever is in the ground now — not wheat. `RABI_PEAK_WINDOW` in
`backend/m0_field/sources/earth_engine.py` holds the demo window.
