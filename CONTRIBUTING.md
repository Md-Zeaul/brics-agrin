# Working on AgriSetu

Two people, six days, one demo. This file exists so the second person does not
spend a morning rediscovering what the first one already worked out.

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

**4. Earth Engine credentials — no key file changes hands.**

    gcloud auth application-default login
    gcloud auth application-default set-quota-project "$GCP_PROJECT"

Your Google account already holds a role on the project, which is
authorisation. This command is authentication — the separate question of
proving who you are. Being granted a role does not log you in.

**5. Check it before trusting it.**

    source .env && .venv/bin/python backend/check_ee.py

This runs the same call path M0 uses and names the first thing that is wrong.
Do this before writing any code, because a missing credential does not raise —
NDVI degrades to `unavailable`, the health chip still renders off the other
signals, and nothing tells you the satellite was never asked.

## Running it

Two terminals.

    # 1 — the M0 endpoint. Use the venv python; the system one has no
    #     earthengine-api and NDVI silently falls back.
    source .env && .venv/bin/python backend/dev_server.py    # :8787

    # 2 — the app
    export PATH="$HOME/development/flutter/bin:$PATH"
    cd app && flutter run -d chrome

A profile takes roughly 20 seconds to build the first time — six sources, one
of them Earth Engine. That is not a hang.

To stop them:

    lsof -ti tcp:8787 | xargs kill -9      # the backend
    lsof -ti tcp:8080 | xargs kill -9      # the static web server, if running

## Tests

Both suites must be green before you push.

    .venv/bin/python -m unittest discover -s backend/tests -t backend/tests
    cd app && flutter analyze && flutter test

There is no pytest in this project. `python3 -m unittest` is the runner.

## Who owns what

Modules are owned whole, not file by file. Work inside your own and the two of
us almost never touch the same file.

| Module | Screens | Owner | Fidelity for the demo |
|---|---|---|---|
| M0 Field Intelligence | S1, S2 | @Md-Zeaul | Live — Earth Engine |
| M1 AI Farmer Copilot | S2 | @Md-Zeaul | Live — Gemini, STT/TTS/Translate |
| M2 Disease Diagnostic | S3, S4 | @herambskanda | Live — Vertex Vision, TFLite offline |
| M3 Regenerative Advisor | S5 | @Md-Zeaul | Live rules over real field data |
| M4 Seed Intelligence | S5 | @herambskanda | Seeded DB of real varieties |
| M5 Nervous System | S7, S8 | @herambskanda | Seeded tiles + one live signal |
| M6 Economic Engine | S9 | @herambskanda | Seeded scenario |
| M7 Federated Agri-DPI | S10 | @herambskanda | Mock — 20% of the score |
| M8 Farm Digital Twin | S6 | @Md-Zeaul | Live-ish simulator |

Directory layout follows that table, so the folder you are in tells you whose
code it is:

    app/lib/features/field/            M0 — S1, S2
    app/lib/features/diagnosis/        M2 — S3, S4
    app/lib/features/planner/          M3, M4, M8 — S5, S6
    app/lib/features/command_center/   M5, M6, M7 — S7 to S10
    app/lib/core/                      shell: routes, language, config
    backend/m0_field/                  M0

### The two seams that need agreeing, not assuming

**S5 has three owners.** M3's ranked table, M4's seed variety and M1's one-line
reason all land on one screen. M4 ships as a pure lookup —
`recommend_seed(crop, zone, traits) -> variety` plus its data rows — and
@Md-Zeaul renders the screen. M4's owner does not open `planner_screen.dart`.

**Language is shared.** `app/lib/core/l10n/` is the one mechanism, used by M1
for the spoken advisory and by M7 for the Portuguese flip. Add your strings in
your own section of `strings.dart`; English is required, the other two degrade
to English when missing. Do not build a second language mechanism.

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
