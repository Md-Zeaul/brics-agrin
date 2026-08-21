"""The advisory copy, written by hand in every language M1 speaks.

This is the asset the Build Brief calls "advisory copy templates in Hindi +
English", widened to Portuguese because S10 flips the whole app to it.

**The model never writes prose.** It picks a template id and fills its slots.
Everything a farmer reads was written by a person, which is the only way the
Hindi and Portuguese carry the right agricultural register — a machine
translation of "top dressing" or "tillering" is confidently wrong in both. It
also makes the rendered text deterministic, so the demo's audio can be
pre-cached, and it makes the choice testable: a test asserts which template was
chosen, not how a sentence happened to come out.

Each entry declares the signals it needs. A template whose signals are missing
or unavailable is not eligible, whatever the model would prefer — that is the
mechanism that stops the advisory asserting something no source supports.

Three fields per language, matching the S2 wireframe:
  situation — what is true right now
  action    — the one thing to do about it
  reason    — why, in a sentence, including what we are unsure of
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Urgency, in the order the card ranks them.
ROUTINE = "routine"
ADVISORY = "advisory"
URGENT = "urgent"

_URGENCY_RANK = {URGENT: 3, ADVISORY: 2, ROUTINE: 1}

LANGUAGES = ("en", "hi", "pt")


@dataclass(frozen=True)
class Template:
    id: str
    topic: str
    urgency: str
    requires: tuple[str, ...]
    slots: tuple[str, ...]
    text: dict[str, dict[str, str]]
    stages: tuple[str, ...] = ()   # empty means any stage, including unknown

    @property
    def rank(self) -> int:
        return _URGENCY_RANK[self.urgency]

    def render(self, language: str, slots: dict) -> dict[str, str]:
        """Fill this template in one language, falling back to English.

        A language with no entry degrades to English rather than to a blank
        card — the same rule the Flutter string table follows.
        """
        copy = self.text.get(language) or self.text["en"]
        return {part: text.format(**slots) for part, text in copy.items()}


def _t(id, topic, urgency, requires, slots, text, stages=()):
    return Template(
        id=id, topic=topic, urgency=urgency, requires=tuple(requires),
        slots=tuple(slots), text=text, stages=tuple(stages),
    )


TEMPLATES: tuple[Template, ...] = (
    _t(
        "irrigation.hold", "irrigation", ADVISORY,
        requires=["waterBalance7dMm", "rainForecast7dMm"],
        slots=["rainMm"],
        text={
            "en": {
                "situation": "{rainMm} mm of rain is expected over the next 7 days.",
                "action": "Hold irrigation this week.",
                "reason": "That is more than your crop will use, so watering now "
                          "would waste it and risk waterlogging.",
            },
            "hi": {
                "situation": "अगले 7 दिनों में {rainMm} मिमी बारिश का अनुमान है।",
                "action": "इस हफ़्ते सिंचाई रोक दें।",
                "reason": "यह आपकी फसल की ज़रूरत से ज़्यादा है — अभी पानी देना "
                          "बर्बादी होगी और जलभराव का ख़तरा रहेगा।",
            },
            "pt": {
                "situation": "São esperados {rainMm} mm de chuva nos próximos 7 dias.",
                "action": "Suspenda a irrigação esta semana.",
                "reason": "É mais do que a lavoura vai consumir; irrigar agora "
                          "desperdiça água e arrisca encharcamento.",
            },
        },
    ),
    _t(
        "irrigation.apply", "irrigation", URGENT,
        requires=["waterBalance7dMm", "topsoilWater"],
        slots=["deficitMm", "topsoilPct"],
        text={
            "en": {
                "situation": "Your crop will need about {deficitMm} mm more water "
                             "than rain will bring this week.",
                "action": "Irrigate within the next two days.",
                "reason": "The top of the soil is already dry, at {topsoilPct}% moisture.",
            },
            "hi": {
                "situation": "इस हफ़्ते बारिश से आपकी फसल को लगभग {deficitMm} मिमी "
                             "कम पानी मिलेगा।",
                "action": "अगले दो दिनों में सिंचाई कर लें।",
                "reason": "ऊपरी मिट्टी पहले से सूखी है — नमी सिर्फ़ {topsoilPct}% है।",
            },
            "pt": {
                "situation": "A lavoura vai precisar de cerca de {deficitMm} mm a mais "
                             "do que a chuva trará esta semana.",
                "action": "Irrigue nos próximos dois dias.",
                "reason": "A camada superficial já está seca, com {topsoilPct}% de umidade.",
            },
        },
    ),
    _t(
        "irrigation.watch", "irrigation", ROUTINE,
        requires=["waterBalance7dMm", "rootzoneWater"],
        slots=["deficitMm"],
        text={
            "en": {
                "situation": "Rain this week falls about {deficitMm} mm short of "
                             "what your crop will use.",
                "action": "Check the soil by hand before you irrigate.",
                "reason": "The shortfall is small and there is still water deeper "
                          "in the root zone.",
            },
            "hi": {
                "situation": "इस हफ़्ते बारिश ज़रूरत से लगभग {deficitMm} मिमी कम रहेगी।",
                "action": "सिंचाई से पहले मिट्टी हाथ से जाँच लें।",
                "reason": "कमी ज़्यादा नहीं है और जड़ों के नीचे अभी नमी बची है।",
            },
            "pt": {
                "situation": "A chuva desta semana fica cerca de {deficitMm} mm "
                             "abaixo do que a lavoura vai consumir.",
                "action": "Confira o solo com a mão antes de irrigar.",
                "reason": "O déficit é pequeno e ainda há água mais fundo na zona "
                          "das raízes.",
            },
        },
    ),
    _t(
        "fertiliser.hold_rain", "fertiliser", URGENT,
        requires=["rainForecastMm"],
        slots=["rainTomorrowMm"],
        text={
            "en": {
                "situation": "{rainTomorrowMm} mm of rain is expected tomorrow.",
                "action": "Do not apply nitrogen today.",
                "reason": "Urea spread before heavy rain washes away before the "
                          "crop can take it up.",
            },
            "hi": {
                "situation": "कल {rainTomorrowMm} मिमी बारिश का अनुमान है।",
                "action": "आज यूरिया न डालें।",
                "reason": "तेज़ बारिश से पहले डाली गई यूरिया फसल के काम आने से पहले "
                          "ही बह जाती है।",
            },
            "pt": {
                "situation": "São esperados {rainTomorrowMm} mm de chuva amanhã.",
                "action": "Não aplique nitrogênio hoje.",
                "reason": "Ureia aplicada antes de chuva forte é lixiviada antes de "
                          "a lavoura conseguir absorvê-la.",
            },
        },
    ),
    _t(
        "fertiliser.nitrogen_low", "fertiliser", ADVISORY,
        requires=["soilNitrogen", "ndviPercentile"],
        slots=["behindPct"],
        text={
            "en": {
                "situation": "Your canopy is behind {behindPct}% of nearby fields "
                             "and soil nitrogen reads low.",
                "action": "Plan a nitrogen top-dressing.",
                "reason": "That nitrogen figure is a district estimate, not a soil "
                          "test — check your Soil Health Card before buying.",
            },
            "hi": {
                "situation": "आपकी फसल की हरियाली आस-पास के {behindPct}% खेतों से "
                             "पीछे है और मिट्टी में नाइट्रोजन कम दिख रही है।",
                "action": "नाइट्रोजन की टॉप-ड्रेसिंग की योजना बनाएँ।",
                "reason": "यह नाइट्रोजन का आँकड़ा इलाक़े का अनुमान है, मिट्टी की जाँच "
                          "नहीं — ख़रीदने से पहले मृदा स्वास्थ्य कार्ड देख लें।",
            },
            "pt": {
                "situation": "Seu dossel está atrás de {behindPct}% das lavouras "
                             "vizinhas e o nitrogênio do solo aparece baixo.",
                "action": "Programe uma adubação nitrogenada de cobertura.",
                "reason": "Esse valor de nitrogênio é uma estimativa regional, não "
                          "uma análise de solo — confirme antes de comprar.",
            },
        },
    ),
    _t(
        "fertiliser.topdress_window", "fertiliser", ADVISORY,
        requires=["soilNitrogen"],
        slots=["days"],
        stages=["vegetative"],
        text={
            "en": {
                "situation": "Your crop is {days} days from sowing, in its main "
                             "growth phase.",
                "action": "This is the window for a nitrogen top-dressing.",
                "reason": "Nitrogen given during vegetative growth builds the "
                          "tillers that carry yield later.",
            },
            "hi": {
                "situation": "बुवाई को {days} दिन हो चुके हैं — फसल अपनी मुख्य "
                             "बढ़वार में है।",
                "action": "नाइट्रोजन टॉप-ड्रेसिंग का यही सही समय है।",
                "reason": "बढ़वार के समय दी गई नाइट्रोजन उन कल्लों को बनाती है जिन "
                          "पर आगे चलकर पैदावार टिकती है।",
            },
            "pt": {
                "situation": "A lavoura está com {days} dias após a semeadura, na "
                             "fase de crescimento.",
                "action": "Esta é a janela para a adubação nitrogenada de cobertura.",
                "reason": "Nitrogênio aplicado no crescimento vegetativo forma os "
                          "perfilhos que sustentam a produtividade.",
            },
        },
    ),
    _t(
        "protection.heat_stress", "protection", ADVISORY,
        requires=["airTempMaxC", "vpdKpa"],
        slots=["tmaxC"],
        text={
            "en": {
                "situation": "Tomorrow reaches {tmaxC} °C with very dry air.",
                "action": "Irrigate in the evening, not the middle of the day.",
                "reason": "Evaporative demand is high, so midday water is lost "
                          "before it reaches the roots.",
            },
            "hi": {
                "situation": "कल तापमान {tmaxC} °C तक जाएगा और हवा बहुत सूखी रहेगी।",
                "action": "सिंचाई शाम को करें, दोपहर में नहीं।",
                "reason": "वाष्पीकरण तेज़ है — दोपहर का पानी जड़ों तक पहुँचने से "
                          "पहले ही उड़ जाता है।",
            },
            "pt": {
                "situation": "Amanhã chega a {tmaxC} °C com ar muito seco.",
                "action": "Irrigue à noite, não no meio do dia.",
                "reason": "A demanda evaporativa está alta; a água do meio-dia se "
                          "perde antes de chegar às raízes.",
            },
        },
    ),
    _t(
        "protection.disease_watch", "protection", ADVISORY,
        requires=["surfaceWetness", "airTempMaxC"],
        slots=[],
        text={
            "en": {
                "situation": "Warm days with a wet canopy — the conditions fungal "
                             "disease likes.",
                "action": "Scan a few leaves for spots or rust this week.",
                "reason": "Caught early, treatment can stay with a bio option "
                          "instead of a chemical one.",
            },
            "hi": {
                "situation": "दिन गर्म हैं और पत्तियाँ गीली रह रही हैं — फफूँद रोग "
                             "के लिए अनुकूल स्थिति।",
                "action": "इस हफ़्ते कुछ पत्तियों को धब्बों या रतुआ के लिए स्कैन करें।",
                "reason": "जल्दी पकड़ में आ जाए तो जैविक उपचार से काम चल जाता है, "
                          "रासायनिक की ज़रूरत नहीं पड़ती।",
            },
            "pt": {
                "situation": "Dias quentes com dossel úmido — as condições que a "
                             "doença fúngica prefere.",
                "action": "Escaneie algumas folhas em busca de manchas ou ferrugem.",
                "reason": "Detectada cedo, dá para tratar com uma opção biológica "
                          "em vez de química.",
            },
        },
    ),
    _t(
        "canopy.behind_neighbours", "canopy", URGENT,
        requires=["ndviPercentile"],
        slots=["behindPct"],
        text={
            "en": {
                "situation": "Your canopy is weaker than {behindPct}% of the farms "
                             "around you.",
                "action": "Walk the field and look for patchy growth, pests or "
                          "standing water.",
                "reason": "The satellite can see the difference but not the cause.",
            },
            "hi": {
                "situation": "आपके खेत की हरियाली आस-पास के {behindPct}% खेतों से "
                             "कमज़ोर है।",
                "action": "खेत में घूमकर देखें — कहीं बढ़वार पतली, कीट या पानी "
                          "भरा तो नहीं।",
                "reason": "सैटेलाइट फ़र्क़ देख सकता है, वजह नहीं।",
            },
            "pt": {
                "situation": "Seu dossel está mais fraco que o de {behindPct}% das "
                             "lavouras ao redor.",
                "action": "Percorra o talhão procurando falhas, pragas ou água parada.",
                "reason": "O satélite enxerga a diferença, mas não a causa.",
            },
        },
    ),
    _t(
        "canopy.no_active_crop", "canopy", ROUTINE,
        requires=["neighbourhoodMedianNdvi"],
        slots=[],
        text={
            "en": {
                "situation": "The fields around you are bare — the area is between "
                             "crops.",
                "action": "Use the planner to choose what to sow next.",
                "reason": "There is no canopy to assess yet, so field readings will "
                          "not mean much until sowing.",
            },
            "hi": {
                "situation": "आस-पास के खेत ख़ाली हैं — इलाक़ा दो फसलों के बीच में है।",
                "action": "अगली फसल चुनने के लिए योजना खोलें।",
                "reason": "अभी कोई फसल खड़ी नहीं है, इसलिए बुवाई तक खेत की रीडिंग "
                          "का ख़ास मतलब नहीं।",
            },
            "pt": {
                "situation": "As lavouras ao redor estão em pousio — a região está "
                             "entre safras.",
                "action": "Use o planejador para escolher a próxima cultura.",
                "reason": "Ainda não há dossel para avaliar, então as leituras do "
                          "talhão dizem pouco até a semeadura.",
            },
        },
    ),
    _t(
        "soil.alkaline", "soil", ROUTINE,
        requires=["soilPh"],
        slots=["ph"],
        text={
            "en": {
                "situation": "Your soil pH is {ph}, on the alkaline side.",
                "action": "Work nitrogen into the soil rather than spreading it "
                          "on the surface.",
                "reason": "Above pH 8, surface-spread urea is lost to the air as "
                          "ammonia before the crop reaches it.",
            },
            "hi": {
                "situation": "आपकी मिट्टी का pH {ph} है — क्षारीय तरफ़।",
                "action": "यूरिया ऊपर से बिखेरने के बजाय मिट्टी में मिलाएँ।",
                "reason": "pH 8 से ऊपर ऊपर-ऊपर डाली गई यूरिया अमोनिया बनकर हवा में "
                          "उड़ जाती है, फसल तक पहुँचती ही नहीं।",
            },
            "pt": {
                "situation": "O pH do seu solo é {ph}, do lado alcalino.",
                "action": "Incorpore o nitrogênio ao solo em vez de aplicá-lo "
                          "na superfície.",
                "reason": "Acima de pH 8, a ureia na superfície se perde como "
                          "amônia antes de a lavoura aproveitá-la.",
            },
        },
    ),
    _t(
        "canopy.healthy", "canopy", ROUTINE,
        requires=["ndviPercentile"],
        slots=["aheadPct"],
        text={
            "en": {
                "situation": "Your canopy is ahead of {aheadPct}% of nearby farms.",
                "action": "Keep to your current schedule.",
                "reason": "Nothing in this week's readings calls for a change.",
            },
            "hi": {
                "situation": "आपके खेत की हरियाली आस-पास के {aheadPct}% खेतों से "
                             "आगे है।",
                "action": "जो चल रहा है, वही जारी रखें।",
                "reason": "इस हफ़्ते की रीडिंग में बदलाव की कोई वजह नहीं दिखती।",
            },
            "pt": {
                "situation": "Seu dossel está à frente de {aheadPct}% das lavouras "
                             "vizinhas.",
                "action": "Mantenha o manejo atual.",
                "reason": "Nada nas leituras desta semana pede mudança.",
            },
        },
    ),
)

# Not in TEMPLATES, and never eligible: the floor for a field where nothing at
# all could be established. Saying so is the honest output — a cheerful default
# advisory over no signals is the one failure mode this whole design exists to
# avoid.
INSUFFICIENT_DATA = _t(
    "advisory.insufficient_data", "none", ROUTINE,
    requires=[], slots=[],
    text={
        "en": {
            "situation": "Not enough of today's readings came through for this field.",
            "action": "Refresh, or check back once the satellite passes again.",
            "reason": "Advice without readings behind it would be a guess, so "
                      "there is none to give.",
        },
        "hi": {
            "situation": "इस खेत के लिए आज की पर्याप्त रीडिंग नहीं मिल पाई।",
            "action": "रिफ़्रेश करें, या सैटेलाइट के अगले चक्कर के बाद देखें।",
            "reason": "बिना रीडिंग की सलाह सिर्फ़ अंदाज़ा होगी, इसलिए अभी कोई "
                      "सलाह नहीं दी जा रही।",
        },
        "pt": {
            "situation": "Não chegaram leituras suficientes para este talhão hoje.",
            "action": "Atualize, ou volte após a próxima passagem do satélite.",
            "reason": "Recomendação sem leitura por trás seria um palpite, então "
                      "não há nenhuma a dar.",
        },
    },
)

BY_ID: dict[str, Template] = {t.id: t for t in TEMPLATES}
BY_ID[INSUFFICIENT_DATA.id] = INSUFFICIENT_DATA


def get(template_id: str) -> Template | None:
    return BY_ID.get(template_id)
