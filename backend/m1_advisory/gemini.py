"""Gemini as a chooser, not an author.

The model is never asked what the farmer should do. It is handed the templates
that are *already* eligible — signals present, stage matching, rule satisfied —
and asked which one fits best. Everything it can say is therefore something a
person already wrote and a rule already permitted, so a hallucinated id is a
no-op rather than a wrong instruction on a farmer's phone.

That inversion is what makes the model safe to use here at all, and it is also
what makes it worth using: choosing between four applicable recommendations is
a judgement call that rules make crudely (urgency, then declaration order) and
a model makes well, because it can weigh how much each one actually matters
today against the specific numbers behind it.

Runs on Vertex AI through the REST API with the credentials M0 already uses —
no new key, no extra dependency beyond google-auth, which earthengine-api
already brings. Every failure path returns None, and None means the rules
decide.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

log = logging.getLogger("m1.gemini")

DEFAULT_REGION = "asia-south1"
DEFAULT_MODEL = "gemini-2.5-flash"

# Short on purpose. The advisory card is the first thing on S2 and a slow model
# call must never be what a farmer waits for; the rules answer is already good.
TIMEOUT_SECONDS = 8.0

_SCHEMA = {
    "type": "object",
    "properties": {
        "primary": {"type": "string"},
        "secondary": {"type": "string"},
        "why": {"type": "string"},
    },
    "required": ["primary"],
}

# Temperature zero because the same field must advise the same way twice: the
# demo's audio is pre-cached against the rendered text, and a card that
# reworded itself between rehearsal and stage would desync it.
GENERATION_CONFIG = {
    "temperature": 0,
    "maxOutputTokens": 2048,
    "responseMimeType": "application/json",
    "responseSchema": _SCHEMA,
}

_INSTRUCTIONS = """\
You are choosing today's advice for one smallholder farm.

You are NOT writing advice. Every recommendation below was written by an
agronomist and has already been checked against this field's actual readings.
Your only job is to pick which one matters most today.

Return JSON: {"primary": "<id>", "secondary": "<id or empty>", "why": "<one short sentence>"}

Rules you must follow:
- Both ids MUST come from the list below, exactly as written. Do not invent one.
- secondary must have a different topic from primary, or be empty.
- Prefer the recommendation that changes what the farmer does in the next few
  days over one that describes a standing condition.
- A reading marked `seeded` is a district default, not a measurement of this
  field. Weigh advice resting on it a little lower than advice resting on
  `live` readings.
"""


def gemini_available() -> bool:
    """True when a chooser could plausibly be built.

    Deliberately cheap — it checks configuration, not reachability. Whether
    Vertex actually answers is discovered by calling it, and answered by
    falling back.
    """
    if os.environ.get("M1_DISABLE_GEMINI"):
        return False
    if not os.environ.get("GCP_PROJECT"):
        return False
    from _credentials import credentials_present

    return credentials_present()


def _token() -> str:
    """A bearer token from whichever credential this machine has.

    Same two paths as Earth Engine: this repo's own GCP_SA_JSON, or the
    Application Default Credentials a collaborator gets from
    `gcloud auth application-default login`.
    """
    from google.auth.transport.requests import Request

    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    key_path = os.environ.get("GCP_SA_JSON")
    if key_path:
        from google.oauth2 import service_account

        creds = service_account.Credentials.from_service_account_file(
            os.path.expanduser(key_path), scopes=scopes
        )
    else:
        import google.auth

        creds, _ = google.auth.default(scopes=scopes)

    creds.refresh(Request())
    return creds.token


def _prompt(candidates, signals, context) -> str:
    lines = [_INSTRUCTIONS, "", "FIELD"]
    lines.append(f"  crop: {context.get('crop') or 'unknown'}")
    lines.append(f"  growth stage: {context.get('stage')}"
                 f" ({context.get('daysAfterSowing')} days after sowing)")
    lines.append("")
    lines.append("READINGS")
    for name in sorted(signals):
        signal = signals[name]
        lines.append(f"  {name} = {signal.value}  [{signal.status}]")
    lines.append("")
    lines.append("APPLICABLE RECOMMENDATIONS")
    for template in candidates:
        english = template.text["en"]
        lines.append(f"  id: {template.id}")
        lines.append(f"     topic: {template.topic}   urgency: {template.urgency}")
        lines.append(f"     says: {english['situation']} {english['action']}")
    return "\n".join(lines)


class GeminiChooser:
    """Implements the `Chooser` protocol in advisory.py."""

    def __init__(self, project=None, region=None, model=None, timeout=None):
        self.project = project or os.environ.get("GCP_PROJECT")
        self.region = region or os.environ.get("VERTEX_REGION", DEFAULT_REGION)
        self.model = model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
        self.timeout = timeout or TIMEOUT_SECONDS

        # What actually happened last call, for the endpoint to report. A
        # silent fallback that nobody can see is how a demo ends up claiming
        # live AI while running on rules.
        self.last_error: str | None = None

    @property
    def source(self) -> str:
        return f"{self.model} via Vertex AI ({self.region})"

    @property
    def endpoint(self) -> str:
        return (
            f"https://{self.region}-aiplatform.googleapis.com/v1/projects/"
            f"{self.project}/locations/{self.region}/publishers/google/models/"
            f"{self.model}:generateContent"
        )

    def __call__(self, candidates, signals, context):
        self.last_error = None
        try:
            return self._choose(candidates, signals, context)
        except Exception as error:
            # Recorded before it propagates. advisory.py catches this and falls
            # back to rules, and without the record the endpoint would report a
            # rules advisory with no hint that a model was even attempted.
            if not self.last_error:
                self.last_error = f"{type(error).__name__}: {error}"
            raise

    def _choose(self, candidates, signals, context):
        body = json.dumps({
            "contents": [{
                "role": "user",
                "parts": [{"text": _prompt(candidates, signals, context)}],
            }],
            "generationConfig": GENERATION_CONFIG,
        }).encode("utf-8")

        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {_token()}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read()[:200].decode("utf-8", "replace")
            self.last_error = f"HTTP {error.code}: {detail}"
            raise

        text = (
            payload["candidates"][0]["content"]["parts"][0]["text"]
        )
        choice = json.loads(text)
        log.info("gemini chose %s / %s — %s", choice.get("primary"),
                 choice.get("secondary"), choice.get("why"))
        return choice.get("primary"), choice.get("secondary") or None
