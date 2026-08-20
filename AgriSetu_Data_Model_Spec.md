# AgriSetu — data, model & scoring specification

Per-module build spec covering, for each of M0–M8: (1) user journey, (2) input sources and
formats with links, (3) processing needed, (4) exact models and where to get them, (5)
output format and relevance. Ends with how the build earns points against the six weighted
judging criteria.

Companion to `build-brief.md` (what to build) and `tech-spec.md` (contracts). This doc is
the *sourcing* layer — the real datasets, APIs, and model IDs.

## Model-version note — read first

Model IDs move fast. As of August 2026:

- Gemini 2.5 (`gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-2.5-flash-lite`) is the GA-stable
  baseline but is scheduled to shut down 16–20 October 2026.
- Gemini 3 is the current docs default; `gemini-3.1-flash-lite` is GA with a longer runway.

For a demo shipping now, build against `gemini-2.5-flash` (stable, multimodal, cheap). If
anything runs past mid-October, switch to `gemini-3.1-flash-lite`. Keep the model name in one
config value so it is a one-line change. Verify current IDs at
https://ai.google.dev/gemini-api/docs/models before locking.

---

# M0 — Field intelligence

**1. User journey.** Farmer opens the app, drops a pin (or draws a boundary) on the map. In
under 30 seconds the field is outlined and a profile — soil, recent rainfall, crop health —
is built with no typing. This runs once per field; every other module reads its cached output.

**2. Input sources & formats (with links).**
- Satellite imagery → `COPERNICUS/S2_SR_HARMONIZED` (Sentinel-2 L2A surface reflectance, 10 m,
  5-day revisit), via Earth Engine. https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED
- Rainfall → CHIRPS daily, `UCSB-CHG/CHIRPS/DAILY` in Earth Engine. https://developers.google.com/earth-engine/datasets/catalog/UCSB-CHG_CHIRPS_DAILY
- Soil → ISRIC SoilGrids (pH, N, CEC, clay, SOC at depth), REST API (GeoJSON/JSON) or the EE
  `projects/soilgrids-isric` assets. https://rest.isric.org/soilgrids/v2.0/docs · https://www.isric.org/explore/soilgrids
- Agro-climate (temp, radiation, ET₀) → NASA POWER API (JSON/CSV). https://power.larc.nasa.gov/api/
- Forecast → Open-Meteo (free, no key, JSON) and/or IMD. https://open-meteo.com/en/docs · https://mausam.imd.gov.in/
- Field boundary → farmer pin (lat/lng) + optional Sentinel-2 segmentation.
- Formats: imagery is raster in EE (server-side); APIs return JSON/CSV; the app stores a
  compact field profile document.

**3. Processing needed.** In an Earth Engine call (from a Cloud Function): filter S2 to the
last ~30 days, cloud-mask with the QA60 band / Cloud Score+, take the median, compute
`NDVI = (B8 − B4)/(B8 + B4)`, clip to the field polygon, reduce to a mean. Pull SoilGrids at
the centroid, CHIRPS/POWER for rainfall and temperature. Normalise everything into one field
profile and cache to Firestore so the home screen renders instantly and works offline.

**4. Exact models / services and where.**
- Google Earth Engine (compute + catalog). https://earthengine.google.com/ · register a project.
- Google Maps Platform (render the field + pin). https://developers.google.com/maps
- No ML model here — it is deterministic remote-sensing math. NDVI is a formula, not a model.

**5. Output — format & relevance.** JSON field profile:
`{ polygon, centroid, ndvi (0–1), soil:{ph, n, p, k, cec, moisture}, rainForecastMm,
tempForecast[], radiationScore, healthChip: GREEN|YELLOW|RED }`. Relevance: this is the
substrate for the whole platform — M1's advisory, M3's crop scoring, and M5's regional
aggregation all read these fields. NDVI is the single most reused signal.

---

# M1 — AI farmer copilot

**1. User journey.** The farmer lands on a home screen showing one clear action for today
("rain tomorrow — hold irrigation"), read aloud in their language. They can also ask a
free-text or voice question and get a plain-language answer with reasons.

**2. Input sources & formats (with links).**
- M0 field profile (JSON) — soil, moisture, NDVI, rain/temperature forecast.
- Farmer voice (audio, 16 kHz LINEAR16/FLAC) or typed text.
- Language preference (`hi`, `en`, `pt`).
- Prices for context → Agmarknet daily mandi prices via data.gov.in (JSON/CSV). https://www.data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi

**3. Processing needed.** Voice → text (STT). Assemble a compact, *annotated* context (not raw
numbers — e.g. "soil N: low", "rain next 24h: 22 mm") and prompt Gemini with a fixed system
role: agronomy advisor, one concrete action, explain the reason, reply in `{language}`,
≤60 words, return Hindi + English in one JSON object. Parse to `{textHi, textEn, action}`.
Translate to other BRICS languages as needed, render speech (TTS), and cache both text and
audio so a live-API blip cannot break the demo.

**4. Exact models / services and where.**
- Gemini `gemini-2.5-flash` (advisory + reasoning + explanation). Google AI Studio / Gemini
  API. https://ai.google.dev/gemini-api/docs/models
- Cloud Speech-to-Text (voice → text; `hi-IN`, `en-IN`, `pt-BR`). https://cloud.google.com/speech-to-text
- Cloud Text-to-Speech (spoken advisory; same locales). https://cloud.google.com/text-to-speech
- Cloud Translation v3 (BRICS languages). https://cloud.google.com/translate

**5. Output — format & relevance.** `{ textHi, textEn, action: hold_irrigation|irrigate|scan|
fertilize|..., spokenUrl }` → written as an `AdvisoryCard`. Relevance: this is the product the
farmer actually experiences daily. `action` is an enum so the UI can react (e.g. surface the
Scan button) without parsing free text.

---

# M2 — Crop disease diagnostic

**1. User journey.** The farmer photographs a suspicious leaf. On-device (works offline) they
get a diagnosis with a confidence score, a differential that separates look-alikes (disease
vs. nutrient deficiency vs. pest), and a treatment that recommends a bio-based option before a
chemical one.

**2. Input sources & formats (with links).**
- Input: a JPEG from camera or gallery.
- Training data (wheat, the demo crop):
  - CGIAR computer vision for crop disease — leaf rust, stem rust, healthy (Kaggle). https://www.kaggle.com/datasets/shadabhussain/cgiar-computer-vision-for-crop-disease
  - Wheat leaf dataset — stripe rust, septoria, healthy (Kaggle / Mendeley). https://www.kaggle.com/datasets/olyadgetch/wheat-leaf-dataset
  - IARI wheat: nitrogen-deficiency + leaf rust, rabi 2019–20, RGB field images — ideal for the
    differential and India-relevant (Mendeley). https://data.mendeley.com/datasets/th422bg4yd/1
  - Fallback crop maize → PlantVillage (common rust, gray leaf spot, northern leaf blight,
    healthy). https://www.kaggle.com/datasets/abdallahalidev/plantvillage-dataset

**3. Processing needed.** Curate 4–6 classes, ~a few hundred images each, augment. Train an
image classifier in Vertex AI Vision (AutoML). Serve the endpoint for the online path; export
a TFLite (Edge) model bundled in the app for the offline path. On a scan, run the classifier
for label + confidence, then pass the image + label to Gemini multimodal for a plain-language
explanation and the bio-first / chemical treatment. Write the scan (with consent) to Firestore
so M5 can detect outbreak clusters.

**4. Exact models / services and where.**
- Vertex AI Vision — AutoML image classification (train + serve + TFLite Edge export). https://cloud.google.com/vertex-ai/docs/image-data/classification/train-model
- Gemini `gemini-2.5-flash` (multimodal explanation + treatment). https://ai.google.dev/gemini-api/docs/models
- TensorFlow Lite (offline inference on device). https://ai.google.dev/edge/litert
- Treatment copy comes from the seeded `treatments` map (in `seed-data.json`), not the model.

**5. Output — format & relevance.** `{ label, confidence, differential:[{label, p}],
treatment:{ bio, chemical } }` in the farmer's language + a `DiseaseScan` document. Relevance:
this is the most demoable feature (a real photo → an instant answer), the offline path proves
low-connectivity readiness, and each scan is a live signal into M5.

---

# M3 — Regenerative crop & soil advisor

**1. User journey.** The farmer asks "what should I plant next season?" and gets a ranked
table (yield, income, water, risk, soil impact), a highlighted pick that balances return with
soil health, a specific seed variety, and a one-line reason.

**2. Input sources & formats (with links).**
- M0 field profile (soil `{ph, n, p, k, cec, moisture}`, NDVI) — JSON.
- Forecast rainfall + temperature (from M0 / Open-Meteo / NASA POWER).
- Prices → Agmarknet via data.gov.in. https://www.data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi
- Crop tolerance ranges + previous crop (rotation) — from `seed-data.json` and history.

**3. Processing needed.** Score each candidate crop on five axes using piecewise
soil-chemistry × climate curves (pH-availability, N logarithmic response, moisture bell curve,
heat-stress penalty above ~32 °C, soil-impact sign). Apply Liebig's law of the minimum — final
score = the worst factor, not the average — and surface the binding constraint. Penalise the
same crop as last season (rotation); boost soil-positive crops (regenerative). Hand the pick +
constraint to Gemini for the plain-language reason.

**4. Exact models / services and where.**
- Primary: a deterministic piecewise scoring function (interpretable, fast, auditable — the
  right choice for a demo and easy to defend to judges). Tune curves with local ICAR/field-trial
  data.
- Scale path: Vertex AI AutoML Tabular (or custom training) for a learned yield/risk model when
  real trial data is available. https://cloud.google.com/vertex-ai/docs/tabular-data/overview
- Gemini `gemini-2.5-flash` for narration. https://ai.google.dev/gemini-api/docs/models

**5. Output — format & relevance.** `{ ranked:[{crop, yield, income, water, risk, soil}], pick,
seedVarietyId, rotationTip, bindingConstraint, reasonHi, reasonEn }`. Relevance: this is the
"regenerative" pillar the challenge names explicitly, and it feeds M4 (seed) and M8 (what-if).

---

# M4 — Seed & genetic-resource intelligence

**1. User journey.** Alongside the crop pick, the farmer sees a named, locally-adapted or
indigenous variety suited to their zone and soil, with the reason and its source/breeder.

**2. Input sources & formats (with links).**
- Crop pick + field zone (from M3) and soil constraints (from M0).
- Variety database — seeded from real varieties (e.g. HHB-67 pearl millet, HD-2967 wheat) in
  `seed-data.json`; sources include ICAR / state agricultural universities. https://icar.org.in/
- Cross-border variety pool → other nodes via BigQuery (federated pattern, M7).

**3. Processing needed.** Query varieties where `crop = pick AND zone matches`; rank by trait
fit (drought tolerance if rain is low, disease resistance if M2 flagged a pathogen,
nitrogen-fixing if soil N is low); filter by availability; attribute the source (farmers'
rights). Gemini writes the one-line reason. If the local pool is thin, pull candidates from
other BRICS nodes.

**4. Exact models / services and where.**
- Firestore (variety DB) + BigQuery (cross-border pool). https://cloud.google.com/bigquery
- Gemini `gemini-2.5-flash` (trait-match narration). https://ai.google.dev/gemini-api/docs/models
- No custom ML — a ranked query plus LLM narration.

**5. Output — format & relevance.** `{ seedVariety:{name, crop, trait, zone, source, available},
reason, attribution }`. Relevance: this is AgriN's literal namesake (agro-inputs, seeds,
genetic resources) and gives the federated layer something concrete to exchange.

---

# M5 — Agricultural nervous system

**1. User journey.** A district planner opens a live risk map each morning: red disease
clusters, orange drought bands, blue waterlogging — visible before any official report.

**2. Input sources & formats (with links).**
- NDVI stress per field (aggregated from M0) — Earth Engine.
- Disease scans (consented, geo-tagged) from M2 — Firestore.
- Rainfall/forecast tiles → CHIRPS + NASA POWER. https://developers.google.com/earth-engine/datasets/catalog/UCSB-CHG_CHIRPS_DAILY · https://power.larc.nasa.gov/api/
- Seeded district baseline (`riskTiles` in `seed-data.json`).

**3. Processing needed.** Threshold + cluster logic: NDVI below a floor across a cluster →
crop-stress (YELLOW); rain < 40% of seasonal normal for 14 days → drought (ORANGE); soil
saturation + forecast → waterlogging (BLUE); ≥N matching disease scans in a district within
7 days → disease cluster (RED). Aggregate in BigQuery; write tiles; render on the dashboard
choropleth via Maps Platform. Trigger an in-app alert on a new RED cluster.

**4. Exact models / services and where.**
- Earth Engine (NDVI aggregation) + BigQuery (scan/weather aggregation) + Maps Platform
  (choropleth). https://cloud.google.com/bigquery · https://developers.google.com/maps
- Rule-based thresholds for the demo; Vertex AI forecasting as a scale path.

**5. Output — format & relevance.** `{ tiles:[{regionId, level: R|O|Y|G|B, driver}] }` + alert
triggers. Relevance: the early-warning layer — turns millions of individual scans into
regional foresight, and is the moment a live farmer scan visibly flips a district red.

---

# M6 — Economic intelligence engine

**1. User journey.** A planner asks "will we face a wheat shortfall?" and gets a projected gap
plus grow / import / substitute / reallocate options, each with cost, CO₂, and food-security
consequences.

**2. Input sources & formats (with links).**
- Production estimate (from M5 risk + historical yield).
- Demand (population × per-capita consumption).
- Trade / production reference → FAOSTAT. https://www.fao.org/faostat/en/#data
- Domestic prices → Agmarknet via data.gov.in. https://www.data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi
- Seeded scenario numbers (`scenarios` in `seed-data.json`) for the demo.

**3. Processing needed.** Compute the gap (demand − projected production). For each option
compute cost/tonne, CO₂ footprint, food-security score, and strategic-dependency index; rank
by a composite score. Populate with seeded data for the demo; run in BigQuery + Vertex AI at
scale.

**4. Exact models / services and where.**
- BigQuery (cross-border production/trade) + Vertex AI (scenario/forecast model). https://cloud.google.com/bigquery · https://cloud.google.com/vertex-ai
- Gemini for the briefing narrative (optional).

**5. Output — format & relevance.** `{ gapPct, options:[{type, cost, co2, foodSecurityScore,
note}] }`. Relevance: elevates the platform from farmer advisory to national food-system
planning — the "strengthen cooperation on sustainable food production" part of the brief.

---

# M7 — Federated Agri-DPI

**1. User journey.** A network view shows BRICS nodes (India, Brazil, China, South Africa). A
disease model contributed by Brazil is imported into India's node and measurably lifts local
accuracy — with no raw farm data crossing borders. The digital public good, made visible.

**2. Input sources & formats (with links).**
- Model artifacts (e.g. Brazil's wheat-rust classifier) + metadata `{ownerNode, crop,
  accuracyBefore}`.
- Node + model registry data (`nodes`, `modelRegistry` in `seed-data.json`).
- Cross-border reference data → Copernicus Data Space (global satellite), FAOSTAT. https://dataspace.copernicus.eu/ · https://www.fao.org/faostat/en/#data

**3. Processing needed.** Register models in the Vertex AI model registry with metadata; the
target node pulls a model via an open API and evaluates it on a local test set → records the
accuracy lift. No raw records move — only model weights + metadata. Translation API switches
the UI language when the demo switches nodes. Publish an open API spec so external national
systems can interoperate. For the demo: mock nodes + one genuinely shared model artifact.

**4. Exact models / services and where.**
- Vertex AI model registry. https://cloud.google.com/vertex-ai/docs/model-registry/introduction
- Cloud Run (open API endpoint) + Cloud Translation (per-node language). https://cloud.google.com/run · https://cloud.google.com/translate

**5. Output — format & relevance.** `{ node, model:{accuracyBefore, accuracyAfter} }` + a
node/model network view + an open API spec. Relevance: this is the "scalable digital public
good" and "share agricultural data models" core of the challenge — and 20% of the score
(cross-border).

---

# M8 — Farm digital twin

**1. User journey.** The farmer toggles "what if rainfall is 20% lower?" and the recommendation
and expected yield update live.

**2. Input sources & formats (with links).**
- Current field profile (M0) + current recommendation (M3).
- User deltas: `{ rainfallPct, fertilizerPct, cropOverride }`.
- No new external source — it re-runs M3's logic with altered inputs.

**3. Processing needed.** Re-run the M3 scoring function with adjusted inputs (lower rainfall →
moisture score drops → water-hungry crops penalised harder; less fertiliser → N score drops →
recommendation may shift to an N-fixing crop). Compute `expectedYieldDeltaPct` vs. baseline.
Gemini explains the delta in one sentence.

**4. Exact models / services and where.**
- Reuses the M3 scoring function (do NOT build a second model — same code, new inputs).
- Vertex AI as the scale path if M3 becomes a learned model. Gemini for the delta sentence.

**5. Output — format & relevance.** `{ pick, expectedYieldDeltaPct, explanation }`. Relevance:
makes the intelligence feel alive and interactive in the demo, and shares 100% of its logic
with M3 — nearly free to build.

---

# Cross-cutting: model & data source summary

**Models by role**

| Role | Model / service | ID / where |
|---|---|---|
| Advisory, reasoning, narration | Gemini | `gemini-2.5-flash` (→ `gemini-3.1-flash-lite` after Oct 2026) |
| Multimodal disease explanation | Gemini | `gemini-2.5-flash` (multimodal) |
| Disease classification | Vertex AI Vision (AutoML) | trained on CGIAR + Wheat Leaf + IARI datasets; TFLite Edge export |
| Voice in / out | Cloud Speech-to-Text · Text-to-Speech | `hi-IN`, `en-IN`, `pt-BR` |
| Language | Cloud Translation v3 | BRICS languages |
| Yield / risk / scenario | Piecewise scoring fn (demo) → Vertex AI AutoML Tabular (scale) | — |
| Geospatial | Earth Engine + Maps Platform | `COPERNICUS/S2_SR_HARMONIZED`, `UCSB-CHG/CHIRPS/DAILY` |
| Federated sharing | Vertex AI model registry | — |

**Data sources**

| Signal | Source | Link |
|---|---|---|
| Satellite / NDVI | Sentinel-2 SR (EE) | https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED |
| Rainfall | CHIRPS daily (EE) | https://developers.google.com/earth-engine/datasets/catalog/UCSB-CHG_CHIRPS_DAILY |
| Soil | ISRIC SoilGrids | https://rest.isric.org/soilgrids/v2.0/docs |
| Agro-climate | NASA POWER | https://power.larc.nasa.gov/api/ |
| Forecast | Open-Meteo · IMD | https://open-meteo.com/en/docs · https://mausam.imd.gov.in/ |
| Prices | Agmarknet (data.gov.in) | https://www.data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi |
| Production / trade | FAOSTAT | https://www.fao.org/faostat/en/#data |
| Global satellite (cross-border) | Copernicus Data Space | https://dataspace.copernicus.eu/ |
| Wheat disease images | CGIAR · Wheat Leaf · IARI | https://www.kaggle.com/datasets/shadabhussain/cgiar-computer-vision-for-crop-disease · https://www.kaggle.com/datasets/olyadgetch/wheat-leaf-dataset · https://data.mendeley.com/datasets/th422bg4yd/1 |
| Maize fallback images | PlantVillage | https://www.kaggle.com/datasets/abdallahalidev/plantvillage-dataset |

---

# How the build earns points (scoring mechanism)

Six weighted criteria. Below: what the judge asks, how each module earns it, what to show,
and the risk that loses it.

## AI / technical execution — 25% (the biggest single lever)
*"Is Google AI doing meaningful work? Does the prototype function end-to-end?"*
- Earned by: every module powered by a named Google model (see the model table) doing real
  work — Gemini advisory, Vertex AI Vision disease, Cloud voice, Earth Engine NDVI — and the
  8-step happy path running start-to-finish.
- Show: a live Gemini advisory, a live camera scan → Vertex Vision diagnosis, voice in/out,
  and real satellite NDVI on a real field.
- Loses points if: features are faked or the disease model is a generic on-device classifier
  with no Google AI visibly involved. Route disease through Vertex AI Vision + Gemini, not a
  bare TFLite model.

## Problem–solution fit — 20%
*"Does it directly and specifically address the stated challenge?"*
- Earned by: the 1:1 mapping — advisory (M1) + disease diagnosis (M2) + regenerative
  recommendation (M3) + seeds (M4) + DPG (M7) cover every clause of the brief.
- Show: the challenge-mapping table; say which module answers which requirement out loud.
- Loses points if: the pitch drifts into the economic/industrial engine and the farmer-facing
  core looks secondary. Keep the smallholder the hero.

## Cross-border applicability — 20% (the cheapest points on the board)
*"Can this realistically work across multiple BRICS nations, not just one?"*
- Earned by: a nation-agnostic architecture (Earth Engine is global; Translation covers BRICS
  languages; each nation plugs its own open-data portal; models cross via the registry) plus a
  demo across ≥2 nations.
- Show: switch the app to Portuguese and a Brazil node; import Brazil's model into India and
  show the accuracy lift — no raw data crossing borders.
- Loses points if: everything is visibly India-only. You do not need live multi-country data —
  you need a credible design and one real second language + shared model.

## Deployability & scalability — 20%
*"Could this be piloted within a ministry or across a member nation in weeks?"*
- Earned by: running entirely on managed Google Cloud (Firebase, Cloud Run, BigQuery, Vertex —
  no infrastructure to procure); onboarding a nation = point at its open-data portal + met
  service, switch language, seed a district; data stays sovereign per ministry.
- Show: state the weeks-not-months pilot path and that it is standard managed services.
- Loses points if: the architecture implies bespoke infrastructure or central data pooling.

## Impact potential — 10%
*"Scale of benefit — how many people, across how many countries, how meaningfully?"*
- Earned by: smallholder-first design; each new BRICS node multiplies reach; regenerative +
  MRV opens sustainability/carbon payments normally closed to smallholders.
- Show: the reach math (farmers per district → nation → network) and the regenerative angle.
- Loses points if: benefit is stated for one district only with no path to scale.

## Presentation & clarity — 5%
*"Can an international delegate understand the value in 5 minutes?"*
- Earned by: the tight 5-minute happy path climbing field → nation → network, plus the
  one-line positioning.
- Show: rehearse the run; lead with the one-liner; keep the arc single-threaded.
- Loses points if: the demo wanders across eight modules with no narrative spine.

**Where to spend hours:** technical execution + cross-border + deployability = 65% of the
score. That is: real Google AI, working end-to-end, across more than one nation, pilotable in
weeks. Everything else supports that.
