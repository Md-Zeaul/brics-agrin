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

# Singular and plural forms of a day count, per language. Hindi does not
# inflect दिन here, so both forms are the same and the entry exists to keep the
# lookup total rather than to say something.
_DAY_FORMS = {
    "en": ("1 day", "{n} days"),
    "hi": ("1 दिन", "{n} दिन"),
    "pt": ("1 dia", "{n} dias"),
}


def days_phrase(count: int, language: str = "en") -> str:
    """A day count as words, so a template never renders "1 days"."""
    singular, plural = _DAY_FORMS.get(language) or _DAY_FORMS["en"]
    return singular if count == 1 else plural.format(n=count)


@dataclass(frozen=True)
class Template:
    id: str
    topic: str
    urgency: str
    requires: tuple[str, ...]
    slots: tuple[str, ...]
    text: dict[str, dict[str, str]]
    stages: tuple[str, ...] = ()   # empty means any stage, including unknown

    # Templates that must never appear on the same card as this one. Entries
    # match another template's id or its topic.
    #
    # A different topic is not enough to make two actions compatible: "stop
    # irrigating now" and "irrigate 25 mm" are harvest advice and irrigation
    # advice, and a card carrying both is worse than a card carrying neither.
    # Contradiction is what a farmer remembers about an app.
    conflicts: tuple[str, ...] = ()

    # True for the "nothing needs doing" card. It is a complete advisory on its
    # own and never a second line beside a real instruction — "stop irrigating
    # now" followed by "no change this week" reads as an app arguing with
    # itself.
    primary_only: bool = False

    def conflicts_with(self, other: "Template") -> bool:
        return (
            other.id in self.conflicts
            or other.topic in self.conflicts
            or self.id in other.conflicts
            or self.topic in other.conflicts
        )

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


def _t(id, topic, urgency, requires, slots, text, stages=(), conflicts=(),
       primary_only=False):
    return Template(
        id=id, topic=topic, urgency=urgency, requires=tuple(requires),
        slots=tuple(slots), text=text, stages=tuple(stages),
        conflicts=tuple(conflicts), primary_only=primary_only,
    )


TEMPLATES: tuple[Template, ...] = (
    _t(
        "irrigation.hold", "irrigation", ADVISORY,
        requires=["waterBalance7dMm", "rainForecast7dMm"],
        slots=["rainMm"],
        # "Do not irrigate for 7 days" cannot share a card with advice about
        # what time of day to irrigate.
        conflicts=["protection.heat_stress"],
        text={
            "en": {
                "situation": "{rainMm} mm of rain is expected over the next 7 days.",
                "action": "Do not irrigate for the next 7 days.",
                "reason": "That is more than your crop will use, so watering now "
                          "would waste it and risk waterlogging.",
            },
            "hi": {
                "situation": "अगले 7 दिनों में {rainMm} मिमी बारिश का अनुमान है।",
                "action": "अगले 7 दिन सिंचाई बिलकुल न करें।",
                "reason": "यह आपकी फसल की ज़रूरत से ज़्यादा है — अभी पानी देना "
                          "बर्बादी होगी और जलभराव का ख़तरा रहेगा।",
            },
            "pt": {
                "situation": "São esperados {rainMm} mm de chuva nos próximos 7 dias.",
                "action": "Não irrigue nos próximos 7 dias.",
                "reason": "É mais do que a lavoura vai consumir; irrigar agora "
                          "desperdiça água e arrisca encharcamento.",
            },
        },
    ),
    _t(
        "irrigation.apply", "irrigation", URGENT,
        requires=["waterBalance7dMm", "topsoilWater"],
        # Not at maturity: the crop is meant to be drying down, and water then
        # adds no yield while risking lodging and spoilage in storage.
        stages=["establishment", "vegetative", "reproductive", "filling"],
        slots=["depthMm", "volumePerHaM3", "topsoilPct"],
        text={
            "en": {
                "situation": "The top of your soil is dry, at {topsoilPct}% moisture, "
                             "and rain will not cover this week's demand.",
                "action": "Irrigate {depthMm} mm within two days — about "
                          "{volumePerHaM3} m³ per hectare.",
                "reason": "Less than this will not reach the root zone; much more "
                          "drains past it and carries nitrogen away with it.",
            },
            "hi": {
                "situation": "ऊपरी मिट्टी सूखी है — नमी सिर्फ़ {topsoilPct}% — और "
                             "इस हफ़्ते बारिश ज़रूरत पूरी नहीं करेगी।",
                "action": "दो दिन के भीतर {depthMm} मिमी सिंचाई करें — लगभग "
                          "{volumePerHaM3} घन मीटर प्रति हेक्टेयर।",
                "reason": "इससे कम पानी जड़ों तक नहीं पहुँचेगा; बहुत ज़्यादा नीचे "
                          "चला जाता है और साथ में नाइट्रोजन भी बहा ले जाता है।",
            },
            "pt": {
                "situation": "A camada superficial está seca, com {topsoilPct}% de "
                             "umidade, e a chuva não cobre a demanda desta semana.",
                "action": "Irrigue {depthMm} mm em até dois dias — cerca de "
                          "{volumePerHaM3} m³ por hectare.",
                "reason": "Menos que isso não alcança a zona das raízes; muito mais "
                          "drena além dela e leva o nitrogênio junto.",
            },
        },
    ),
    _t(
        "irrigation.recent", "irrigation", URGENT,
        requires=["daysSinceIrrigation"],
        slots=["sinceDays"],
        text={
            "en": {
                "situation": "You irrigated {sinceDays} ago.",
                "action": "Do not irrigate again yet. Dig to spade depth first and "
                          "water only if the soil is dry to the touch down there.",
                "reason": "The satellite's soil-water reading lags a fresh irrigation "
                          "by several days, so it still shows this field as dry. Your "
                          "own record is the better guide today.",
            },
            "hi": {
                "situation": "आपने {sinceDays} पहले सिंचाई की थी।",
                "action": "अभी दोबारा सिंचाई न करें। पहले कुदाल जितनी गहराई पर मिट्टी "
                          "देखें — वहाँ सूखी लगे तभी पानी दें।",
                "reason": "उपग्रह की मिट्टी-नमी की रीडिंग ताज़ा सिंचाई को कुछ दिन बाद "
                          "पकड़ती है, इसलिए वह अब भी खेत को सूखा दिखा रही है। आज आपका "
                          "अपना रिकॉर्ड ज़्यादा भरोसेमंद है।",
            },
            "pt": {
                "situation": "Você irrigou há {sinceDays}.",
                "action": "Não irrigue de novo ainda. Cave até a profundidade de uma "
                          "pá e só regue se estiver seco ali embaixo.",
                "reason": "A leitura de umidade do solo por satélite demora alguns "
                          "dias para registrar uma irrigação recente, então ainda "
                          "mostra a lavoura seca. Hoje o seu próprio registro vale mais.",
            },
        },
    ),
    _t(
        "irrigation.watch", "irrigation", ROUTINE,
        requires=["waterBalance7dMm", "rootzoneWater"],
        slots=["deficitMm", "depthMm"],
        text={
            "en": {
                "situation": "Rain this week falls about {deficitMm} mm short of "
                             "what your crop will use.",
                "action": "Dig 15 cm down in two places. If the soil crumbles dry, "
                          "irrigate {depthMm} mm.",
                "reason": "The shortfall is small and there is still water deeper in "
                          "the root zone, so the soil decides this one, not the sky.",
            },
            "hi": {
                "situation": "इस हफ़्ते बारिश ज़रूरत से लगभग {deficitMm} मिमी कम रहेगी।",
                "action": "दो जगह 15 सेंटीमीटर गहरा खोदकर देखें। मिट्टी सूखी भुरभुरी "
                          "लगे तो {depthMm} मिमी सिंचाई करें।",
                "reason": "कमी ज़्यादा नहीं है और जड़ों के नीचे नमी बची है — इसलिए "
                          "फ़ैसला आसमान नहीं, मिट्टी करेगी।",
            },
            "pt": {
                "situation": "A chuva desta semana fica cerca de {deficitMm} mm abaixo "
                             "do que a lavoura vai consumir.",
                "action": "Cave 15 cm em dois pontos. Se o solo esfarelar seco, "
                          "irrigue {depthMm} mm.",
                "reason": "O déficit é pequeno e ainda há água mais fundo, então quem "
                          "decide é o solo, não o céu.",
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
                "action": "Do not spread urea today or tomorrow. Wait until the rain "
                          "has passed, then apply.",
                "reason": "Urea spread before heavy rain washes away before the crop "
                          "can take it up — the money goes into the drain.",
            },
            "hi": {
                "situation": "कल {rainTomorrowMm} मिमी बारिश का अनुमान है।",
                "action": "आज और कल यूरिया न डालें। बारिश निकल जाने के बाद डालें।",
                "reason": "तेज़ बारिश से पहले डाली गई यूरिया फसल के काम आने से पहले "
                          "बह जाती है — पैसा नाली में चला जाता है।",
            },
            "pt": {
                "situation": "São esperados {rainTomorrowMm} mm de chuva amanhã.",
                "action": "Não aplique ureia hoje nem amanhã. Espere a chuva passar "
                          "e aplique depois.",
                "reason": "Ureia aplicada antes de chuva forte é lixiviada antes de a "
                          "lavoura absorvê-la — o dinheiro vai embora na água.",
            },
        },
    ),
    _t(
        "fertiliser.nitrogen_low", "fertiliser", ADVISORY,
        requires=["soilNitrogen", "ndviPercentile", "ureaTopdressKgPerHa"],
        slots=["behindPct", "ureaKgPerHa"],
        # Nitrogen has a window, and it closes. Applied at grain fill the crop
        # can no longer take much of it up, it delays maturity and costs grain
        # quality — and the thin canopy that triggered this rule is, at that
        # stage, ordinary senescence rather than hunger. Unknown stage is
        # excluded too: without knowing where the crop is, withholding a dose
        # is the cheaper mistake.
        stages=["establishment", "vegetative"],
        text={
            "en": {
                "situation": "Your canopy is behind {behindPct}% of nearby fields and "
                             "soil nitrogen reads low.",
                "action": "Spread {ureaKgPerHa} kg of urea per hectare this week, then "
                          "irrigate lightly to wash it in.",
                "reason": "That nitrogen reading is a district estimate, not a soil "
                          "test — check your Soil Health Card before you buy.",
            },
            "hi": {
                "situation": "आपकी फसल की हरियाली आस-पास के {behindPct}% खेतों से पीछे "
                             "है और मिट्टी में नाइट्रोजन कम दिख रही है।",
                "action": "इस हफ़्ते {ureaKgPerHa} किलो यूरिया प्रति हेक्टेयर डालें, "
                          "फिर हल्की सिंचाई करके उसे मिट्टी में बैठा दें।",
                "reason": "यह नाइट्रोजन का आँकड़ा इलाक़े का अनुमान है, मिट्टी की जाँच "
                          "नहीं — ख़रीदने से पहले मृदा स्वास्थ्य कार्ड देख लें।",
            },
            "pt": {
                "situation": "Seu dossel está atrás de {behindPct}% das lavouras "
                             "vizinhas e o nitrogênio do solo aparece baixo.",
                "action": "Aplique {ureaKgPerHa} kg de ureia por hectare esta semana e "
                          "faça uma irrigação leve para incorporá-la.",
                "reason": "Essa leitura de nitrogênio é uma estimativa regional, não "
                          "uma análise de solo — confirme antes de comprar.",
            },
        },
    ),
    _t(
        "fertiliser.topdress_window", "fertiliser", ADVISORY,
        requires=["ureaTopdressKgPerHa", "cropLabel", "soilNitrogen"],
        slots=["days", "ureaKgPerHa", "cropLabel"],
        stages=["vegetative"],
        text={
            "en": {
                "situation": "Your crop is {days} from sowing, in its main "
                             "growth phase.",
                "action": "Spread {ureaKgPerHa} kg of urea per hectare, then irrigate "
                          "lightly to wash it in.",
                "reason": "That is about a third of the season's nitrogen for "
                          "{cropLabel}, the usual share at this stage. It is a general "
                          "rate — check your Soil Health Card before you buy.",
            },
            "hi": {
                "situation": "बुवाई को {days} हो चुके हैं — फसल अपनी मुख्य "
                             "बढ़वार में है।",
                "action": "{ureaKgPerHa} किलो यूरिया प्रति हेक्टेयर डालें, फिर हल्की "
                          "सिंचाई करके उसे मिट्टी में बैठा दें।",
                "reason": "यह {cropLabel} की पूरे मौसम की नाइट्रोजन का लगभग एक तिहाई "
                          "है, जो इस अवस्था में दिया जाता है। यह आम दर है — ख़रीदने "
                          "से पहले मृदा स्वास्थ्य कार्ड देख लें।",
            },
            "pt": {
                "situation": "A lavoura está com {days} após a semeadura, na fase "
                             "de crescimento.",
                "action": "Aplique {ureaKgPerHa} kg de ureia por hectare e faça uma "
                          "irrigação leve para incorporá-la.",
                "reason": "É cerca de um terço do nitrogênio da safra de {cropLabel}, a "
                          "parcela usual neste estádio. É uma dose geral — confirme com "
                          "sua análise de solo antes de comprar.",
            },
        },
    ),
    _t(
        "fertiliser.next_split_due", "fertiliser", ADVISORY,
        # Only the date is required. A farmer who did not say what they spread
        # still gets the timing, and the sentence calls it "fertiliser".
        requires=["daysSinceNitrogen"],
        slots=["sinceDays", "dueInDays", "product"],
        # Same stages as the dose templates it stands in for: this is the card
        # a farmer sees *instead of* a top-dressing instruction, so it belongs
        # wherever that instruction would have belonged.
        stages=["establishment", "vegetative"],
        text={
            "en": {
                "situation": "You applied {product} {sinceDays} ago.",
                "action": "Do not spread more nitrogen yet. The next split is due in "
                          "about {dueInDays}.",
                "reason": "Nitrogen applied too close together is lost to the air and "
                          "past the roots before the crop can use it — the second bag "
                          "does the work of half a bag.",
            },
            "hi": {
                "situation": "आपने {sinceDays} पहले {product} डाली थी।",
                "action": "अभी और नाइट्रोजन न डालें। अगली मात्रा लगभग {dueInDays} "
                          "बाद देनी है।",
                "reason": "बहुत कम अंतर पर डाली गई नाइट्रोजन फसल के काम आने से पहले "
                          "हवा में उड़ जाती है या जड़ों से नीचे चली जाती है — दूसरी "
                          "बोरी आधी बोरी जितना ही काम करती है।",
            },
            "pt": {
                "situation": "Você aplicou {product} há {sinceDays}.",
                "action": "Não aplique mais nitrogênio ainda. A próxima parcela é "
                          "daqui a cerca de {dueInDays}.",
                "reason": "Nitrogênio aplicado com pouco intervalo se perde para o ar "
                          "e abaixo das raízes antes de a lavoura aproveitá-lo — o "
                          "segundo saco rende metade.",
            },
        },
    ),
    _t(
        "fertiliser.topdress_adjusted", "fertiliser", ADVISORY,
        requires=["ureaRemainingKgPerHa", "nitrogenAppliedKgPerHa",
                  "seasonNitrogenKgPerHa", "cropLabel"],
        slots=["ureaKgPerHa", "appliedN", "seasonN", "cropLabel"],
        stages=["establishment", "vegetative"],
        text={
            "en": {
                "situation": "You have put on about {appliedN} kg of nitrogen per "
                             "hectare so far, of roughly {seasonN} kg for the season.",
                "action": "Spread {ureaKgPerHa} kg of urea per hectare, then irrigate "
                          "lightly to wash it in.",
                "reason": "That is the balance of {cropLabel}'s season nitrogen worked "
                          "out from what you told us you already applied, rather than "
                          "a standard rate — so it is only as right as that answer.",
            },
            "hi": {
                "situation": "अब तक आपने लगभग {appliedN} किलो नाइट्रोजन प्रति हेक्टेयर "
                             "डाली है, पूरे मौसम के करीब {seasonN} किलो में से।",
                "action": "{ureaKgPerHa} किलो यूरिया प्रति हेक्टेयर डालें, फिर हल्की "
                          "सिंचाई करके उसे मिट्टी में बैठा दें।",
                "reason": "यह {cropLabel} की मौसम भर की नाइट्रोजन का बचा हुआ हिस्सा "
                          "है, जो आपके बताए अनुसार निकाला गया है, कोई आम दर नहीं — "
                          "यानी यह उतना ही सही है जितना आपका जवाब।",
            },
            "pt": {
                "situation": "Você já aplicou cerca de {appliedN} kg de nitrogênio por "
                             "hectare, de aproximadamente {seasonN} kg da safra.",
                "action": "Aplique {ureaKgPerHa} kg de ureia por hectare e faça uma "
                          "irrigação leve para incorporá-la.",
                "reason": "É o saldo do nitrogênio de {cropLabel} nesta safra, "
                          "calculado a partir do que você informou, e não uma dose "
                          "padrão — vale o quanto valer essa resposta.",
            },
        },
    ),
    _t(
        "fertiliser.season_n_complete", "fertiliser", ADVISORY,
        requires=["nitrogenAppliedKgPerHa", "seasonNitrogenKgPerHa", "cropLabel"],
        slots=["appliedN", "seasonN", "cropLabel"],
        text={
            "en": {
                "situation": "You have applied about {appliedN} kg of nitrogen per "
                             "hectare. {cropLabel} needs roughly {seasonN} kg for the "
                             "whole season.",
                "action": "Do not buy more urea for this crop. Put that money into "
                          "next season's seed instead.",
                "reason": "Past the season's requirement, extra nitrogen softens the "
                          "stem and the crop goes down in the first strong wind. It "
                          "takes yield away rather than adding it.",
            },
            "hi": {
                "situation": "आपने लगभग {appliedN} किलो नाइट्रोजन प्रति हेक्टेयर डाल "
                             "दी है। {cropLabel} को पूरे मौसम में करीब {seasonN} किलो "
                             "चाहिए।",
                "action": "इस फसल के लिए और यूरिया न ख़रीदें। वह पैसा अगले मौसम के बीज "
                          "में लगाएँ।",
                "reason": "ज़रूरत से ज़्यादा नाइट्रोजन से तना कमज़ोर पड़ जाता है और "
                          "पहली तेज़ हवा में फसल गिर जाती है — पैदावार बढ़ने की जगह "
                          "घट जाती है।",
            },
            "pt": {
                "situation": "Você já aplicou cerca de {appliedN} kg de nitrogênio por "
                             "hectare. {cropLabel} pede cerca de {seasonN} kg na safra "
                             "inteira.",
                "action": "Não compre mais ureia para esta lavoura. Guarde o dinheiro "
                          "para a semente da próxima safra.",
                "reason": "Acima da exigência da safra, o nitrogênio extra amolece o "
                          "colmo e a lavoura acama no primeiro vento forte. Tira "
                          "produtividade em vez de somar.",
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
                "action": "Irrigate after 5 pm or before 8 am. Do not irrigate between "
                          "11 am and 4 pm.",
                "reason": "In the middle of the day most of the water evaporates before "
                          "it reaches the roots.",
            },
            "hi": {
                "situation": "कल तापमान {tmaxC} °C तक जाएगा और हवा बहुत सूखी रहेगी।",
                "action": "शाम 5 बजे के बाद या सुबह 8 बजे से पहले सिंचाई करें। "
                          "दोपहर 11 से 4 के बीच बिलकुल न करें।",
                "reason": "दोपहर में ज़्यादातर पानी जड़ों तक पहुँचने से पहले ही "
                          "भाप बनकर उड़ जाता है।",
            },
            "pt": {
                "situation": "Amanhã chega a {tmaxC} °C com ar muito seco.",
                "action": "Irrigue depois das 17h ou antes das 8h. Não irrigue entre "
                          "11h e 16h.",
                "reason": "No meio do dia a maior parte da água evapora antes de "
                          "chegar às raízes.",
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
                "action": "Check 10 plants in each of 5 spots this week. Turn the "
                          "leaves over and look for spots or rust.",
                "reason": "Caught in the first few plants, treatment can stay with a "
                          "bio option instead of a chemical spray.",
            },
            "hi": {
                "situation": "दिन गर्म हैं और पत्तियाँ गीली रह रही हैं — फफूँद रोग "
                             "के लिए अनुकूल स्थिति।",
                "action": "इस हफ़्ते खेत में 5 जगह चुनकर हर जगह 10 पौधे देखें। "
                          "पत्तियाँ पलटकर धब्बे या रतुआ ढूँढ़ें।",
                "reason": "शुरुआती कुछ पौधों में ही पकड़ लिया जाए तो जैविक उपचार से "
                          "काम चल जाता है, रासायनिक छिड़काव की ज़रूरत नहीं पड़ती।",
            },
            "pt": {
                "situation": "Dias quentes com dossel úmido — as condições que a doença "
                             "fúngica prefere.",
                "action": "Verifique 10 plantas em cada um de 5 pontos esta semana. Vire "
                          "as folhas e procure manchas ou ferrugem.",
                "reason": "Detectada nas primeiras plantas, dá para tratar com uma opção "
                          "biológica em vez de pulverização química.",
            },
        },
    ),
    _t(
        "canopy.behind_neighbours", "canopy", URGENT,
        requires=["ndviPercentile"],
        slots=["behindPct"],
        # Not at maturity: a canopy falling behind the neighbours then usually
        # means this field is ripening first, which is not a problem to go
        # looking for. Sending a farmer to walk a ripening field for pests is
        # how an advisory loses their trust.
        stages=["establishment", "vegetative", "reproductive", "filling"],
        text={
            "en": {
                "situation": "Your canopy is weaker than {behindPct}% of the farms "
                             "around you.",
                "action": "Walk the field today. Check 5 spots for thin patches, insects "
                          "under the leaves, and standing water.",
                "reason": "The satellite can see the difference but not the cause — only "
                          "standing in the field will tell you which of the three it is.",
            },
            "hi": {
                "situation": "आपके खेत की हरियाली आस-पास के {behindPct}% खेतों से "
                             "कमज़ोर है।",
                "action": "आज खेत में घूमें। 5 जगह देखें — बढ़वार पतली तो नहीं, "
                          "पत्तियों के नीचे कीड़े तो नहीं, पानी तो नहीं भरा।",
                "reason": "सैटेलाइट फ़र्क़ देख सकता है, वजह नहीं — तीनों में से कौन "
                          "सी है, यह खेत में खड़े होकर ही पता चलेगा।",
            },
            "pt": {
                "situation": "Seu dossel está mais fraco que o de {behindPct}% das "
                             "lavouras ao redor.",
                "action": "Percorra o talhão hoje. Verifique 5 pontos: falhas, insetos "
                          "sob as folhas e água parada.",
                "reason": "O satélite enxerga a diferença, mas não a causa — só andando "
                          "no talhão dá para saber qual das três é.",
            },
        },
    ),
    _t(
        "canopy.no_active_crop", "canopy", ROUTINE,
        requires=["neighbourhoodMedianNdvi"],
        slots=[],
        text={
            "en": {
                "situation": "The fields around you are bare — the area is between crops.",
                "action": "Open the planner and choose your next crop.",
                "reason": "There is no canopy to assess yet, so field readings will not "
                          "mean much until sowing.",
            },
            "hi": {
                "situation": "आस-पास के खेत ख़ाली हैं — इलाक़ा दो फसलों के बीच में है।",
                "action": "योजना खोलें और अगली फसल चुनें।",
                "reason": "अभी कोई फसल खड़ी नहीं है, इसलिए बुवाई तक खेत की रीडिंग का "
                          "ख़ास मतलब नहीं।",
            },
            "pt": {
                "situation": "As lavouras ao redor estão em pousio — a região está "
                             "entre safras.",
                "action": "Abra o planejador e escolha a próxima cultura.",
                "reason": "Ainda não há dossel para avaliar, então as leituras do talhão "
                          "dizem pouco até a semeadura.",
            },
        },
    ),
    _t(
        "soil.alkaline", "soil", ROUTINE,
        # Gated on the dose signal as well as the pH: this is advice about how
        # to place urea, and a legume that should never receive urea has no
        # use for it. Gated on stage for the same reason — it appears only in
        # the window where applying urea is itself advisable.
        requires=["soilPh", "ureaTopdressKgPerHa"],
        stages=["establishment", "vegetative"],
        slots=["ph"],
        text={
            "en": {
                "situation": "Your soil pH is {ph}, on the alkaline side.",
                "action": "Mix urea into the soil about 5 cm deep. Do not spread it on "
                          "the surface and leave it there.",
                "reason": "Above pH 8, surface urea turns to ammonia gas and blows away "
                          "within a day or two — a third of the bag can be lost.",
            },
            "hi": {
                "situation": "आपकी मिट्टी का pH {ph} है — क्षारीय तरफ़।",
                "action": "यूरिया को मिट्टी में लगभग 5 सेंटीमीटर गहरा मिलाएँ। ऊपर से "
                          "बिखेरकर ऐसे ही न छोड़ें।",
                "reason": "pH 8 से ऊपर ऊपर पड़ी यूरिया एक-दो दिन में अमोनिया गैस बनकर "
                          "उड़ जाती है — बोरी का एक तिहाई तक बरबाद हो सकता है।",
            },
            "pt": {
                "situation": "O pH do seu solo é {ph}, do lado alcalino.",
                "action": "Incorpore a ureia a cerca de 5 cm de profundidade. Não deixe "
                          "aplicada na superfície.",
                "reason": "Acima de pH 8, a ureia na superfície vira gás amônia em um ou "
                          "dois dias — até um terço da saca pode se perder.",
            },
        },
    ),
    _t(
        "harvest.dry_down", "harvest", ADVISORY,
        requires=[],
        slots=["days"],
        stages=["maturity"],
        # This screen's advice is "stop watering". Nothing about irrigating
        # belongs beside it.
        conflicts=["irrigation", "protection.heat_stress"],
        text={
            "en": {
                "situation": "Your crop is {days} from sowing and close to "
                             "harvest.",
                "action": "Stop irrigating now. Harvest when a grain is hard and "
                          "your thumbnail leaves no mark on it.",
                "reason": "Water this late adds no yield, and a damp crop at harvest "
                          "spoils in storage.",
            },
            "hi": {
                "situation": "बुवाई को {days} हो चुके हैं — कटाई नज़दीक है।",
                "action": "अब सिंचाई बंद कर दें। दाना जाँचें: जब नाखून से दबाने पर "
                          "निशान न पड़े, तब कटाई करें।",
                "reason": "इस समय पानी देने से पैदावार नहीं बढ़ती, और नमी वाली फसल "
                          "भंडारण में ख़राब हो जाती है।",
            },
            "pt": {
                "situation": "A lavoura está com {days} após a semeadura e perto "
                             "da colheita.",
                "action": "Pare de irrigar agora. Colha quando o grão estiver duro e a "
                          "unha não deixar marca.",
                "reason": "Água nesta fase não acrescenta produtividade, e lavoura "
                          "úmida na colheita estraga no armazenamento.",
            },
        },
    ),
    _t(
        "canopy.healthy", "canopy", ROUTINE,
        requires=["ndviPercentile"],
        slots=["aheadPct"],
        primary_only=True,
        text={
            "en": {
                "situation": "Your canopy is ahead of {aheadPct}% of nearby farms.",
                "action": "No change this week. Check the field again in 7 days.",
                "reason": "Nothing in this week's readings calls for a change.",
            },
            "hi": {
                "situation": "आपके खेत की हरियाली आस-पास के {aheadPct}% खेतों से आगे है।",
                "action": "इस हफ़्ते कोई बदलाव नहीं। 7 दिन बाद खेत फिर देखें।",
                "reason": "इस हफ़्ते की रीडिंग में बदलाव की कोई वजह नहीं दिखती।",
            },
            "pt": {
                "situation": "Seu dossel está à frente de {aheadPct}% das lavouras "
                             "vizinhas.",
                "action": "Sem mudanças esta semana. Confira o talhão de novo em 7 dias.",
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
            "reason": "Advice without readings behind it would be a guess, so there "
                      "is none to give.",
        },
        "hi": {
            "situation": "इस खेत के लिए आज की पर्याप्त रीडिंग नहीं मिल पाई।",
            "action": "रिफ़्रेश करें, या सैटेलाइट के अगले चक्कर के बाद देखें।",
            "reason": "बिना रीडिंग की सलाह सिर्फ़ अंदाज़ा होगी, इसलिए अभी कोई सलाह "
                      "नहीं दी जा रही।",
        },
        "pt": {
            "situation": "Não chegaram leituras suficientes para este talhão hoje.",
            "action": "Atualize, ou volte após a próxima passagem do satélite.",
            "reason": "Recomendação sem leitura por trás seria um palpite, então não "
                      "há nenhuma a dar.",
        },
    },
)

BY_ID: dict[str, Template] = {t.id: t for t in TEMPLATES}
BY_ID[INSUFFICIENT_DATA.id] = INSUFFICIENT_DATA


def get(template_id: str) -> Template | None:
    return BY_ID.get(template_id)
