# Working on AgriSetu

One developer, six days, one demo. This file exists so a fresh terminal — or a
fresh morning — does not spend an hour rediscovering what was already worked
out.

## Setup, start to finish

**1. Tools.** Flutter (stable) and Python 3.9+. On this machine Flutter lives
outside `PATH`, so every command below assumes:

    export PATH="$HOME/development/flutter/bin:$PATH"

**2. Clone and install.**

    git clone https://github.com/Md-Zeaul/brics-agrin.git
    cd brics-agrin
    python3 -m venv .venv
    .venv/bin/pip install -r backend/requirements.txt
    cd app && flutter pub get && cd ..

**3. Environment.**

    cp .env.example .env
    # set GCP_PROJECT; leave GCP_SA_JSON unset

**4. Google credentials — no key file changes hands.**

    gcloud auth application-default login
    gcloud auth application-default set-quota-project "$GCP_PROJECT"

Your Google account already holds a role on the project, which is
authorisation. This command is authentication — the separate question of
proving who you are. Being granted a role does not log you in.

The same login serves Earth Engine (M0's NDVI) and Vertex AI (M1's chooser).
They need two *different* things switched on, and both are easy to miss:

- the API enabled on the project — `aiplatform.googleapis.com` for Vertex
- an IAM role on your account — `roles/aiplatform.user`

Enabling the API without the role fails as `403 aiplatform.endpoints.predict
denied`, which reads like a billing problem and is not one.

**5. Check it before trusting it.**

    source .env && .venv/bin/python backend/check_ee.py

This runs the same call path M0 uses and names the first thing that is wrong.
Do this before writing any code, because a missing credential does not raise —
NDVI degrades to `unavailable`, the health chip still renders off the other
signals, and nothing tells you the satellite was never asked.

## Running it

Two terminals.

    # 1 — the backend: /m0 and /m1. Use the venv python; the system one has
    #     no earthengine-api and NDVI silently falls back.
    source .env && .venv/bin/python backend/dev_server.py    # :8787

    # 2 — the app
    export PATH="$HOME/development/flutter/bin:$PATH"
    cd app && flutter run -d chrome

A profile takes roughly 20 seconds to build the first time — six sources, one
of them Earth Engine. That is not a hang. The advisory that follows takes 1–2
seconds.

To see one advisory decided step by step, with no app and no browser:

    .venv/bin/python backend/trace_advisory.py --sown 2026-06-20 --language hi

To force the rules path and check the fallback still reads well:

    M1_DISABLE_GEMINI=1 .venv/bin/python backend/trace_advisory.py --sown 2026-06-20

To stop them:

    lsof -ti tcp:8787 | xargs kill -9      # the backend
    lsof -ti tcp:8080 | xargs kill -9      # the static web server, if running

## Tests

Both suites must be green before you push.

    .venv/bin/python -m unittest discover -s backend/tests -t backend/tests
    cd app && flutter analyze && flutter test

There is no pytest in this project. `python3 -m unittest` is the runner.

**If an edit seems not to take effect**, clear the bytecode cache. This venv is
built on macOS's system Python, which sets `sys.pycache_prefix` — so `.pyc`
files live outside the repo and deleting `__pycache__` here does nothing:

    rm -rf ~/Library/Caches/com.apple.python$PWD

Python invalidates that cache on the source file's size and mtime, and mtime
has one-second resolution. A scripted edit that changes neither — `bag_kg=45`
to `bag_kg=50`, say — is invisible to it, and the old code keeps running while
the file on disk reads correctly.

## Module order, and what each one owes the demo

Nine modules land on ten screens. They are listed in build order, not module
order: the ordering is by what the five-minute demo cannot proceed without.

| Module | Screens | State | Fidelity for the demo |
|---|---|---|---|
| M0 Field Intelligence | S1, S2 | **built** | Live — Earth Engine, six sources |
| M1 AI Farmer Copilot | S2 | **built** | Live — Vertex Gemini, rules fallback |
| M2 Disease Diagnostic | S3, S4 | to build | Live — Vertex Vision, TFLite offline |
| M3 Regenerative Advisor | S5 | to build | Live rules over real field data |
| M4 Seed Intelligence | S5 | to build | Seeded DB of real varieties |
| M8 Farm Digital Twin | S6 | to build | Live-ish simulator over M3 |
| M5 Nervous System | S7, S8 | to build | Seeded tiles + one live signal |
| M6 Economic Engine | S9 | to build | Seeded scenario |
| M7 Federated Agri-DPI | S10 | to build | Mock — 20% of the score |

Directory layout follows the module split, so the folder you are in tells you
which module you are inside:

    app/lib/features/field/            M0, M1 — S1, S2
    app/lib/features/diagnosis/        M2 — S3, S4
    app/lib/features/planner/          M3, M4, M8 — S5, S6
    app/lib/features/command_center/   M5, M6, M7 — S7 to S10
    app/lib/core/                      shell: routes, language, config
    backend/m0_field/                  M0
    backend/m1_advisory/               M1

### The two seams worth designing before writing

These were coordination problems when two people were building. With one, they
are still design problems — the cost just moved from a merge conflict to a
rewrite.

**S5 carries three modules.** M3's ranked table, M4's seed variety and M1's
one-line reason all land on one screen. Keep M4 a pure lookup —
`recommend_seed(crop, zone, traits) -> variety` plus its data rows — so the
screen has one owner and the data has none.

**`data/seed-data.json` gates four modules.** M4, M5, M6 and M7 all read it and
none of them can be started without it. It is issue #1 for that reason: one
data session unlocks a third of what is left.

**Language is one mechanism.** `app/lib/core/l10n/` serves M1's advisory and
M7's Portuguese flip alike. Add strings to `strings.dart`; English is required,
the other two degrade to English when missing. Do not build a second one.

## Branches

`main` must stay demoable at all times. That is the only rule with teeth: if a
half-finished module lands on `main` the night before submission, there is
nothing to show.

    git pull
    git checkout -b m2-disease
    # ... work, commit as you go ...
    git push -u origin m2-disease

Then open a pull request on GitHub and merge it. No review requirement, no CI
gate — with two people over six days the branch is there to protect the demo,
not to enforce process.

Push small and often. A branch that lives three days is a merge conflict
waiting to happen.

## House style

- **Say what is unknown.** Every signal in M0 carries its own provenance and
  can degrade on its own — `live`, `cached`, `reported`, `seeded`,
  `unavailable`. A number with no source behind it is a claim, not a finding.
  Whatever you build, keep that property.
- **Fail loudly in development, degrade gracefully in the demo.** A missing
  credential should be obvious to us and invisible to a judge.
- **Never commit a key.** `.env` and `*.json` key files are gitignored. If you
  add a new secret, add its name to `.env.example` and its *value* nowhere.
- Comments explain why, not what.
