/// UI strings, keyed by language.
///
/// Deliberately a plain map rather than generated `.arb` localisations: the
/// demo needs to flip language at runtime on S10 with no rebuild, and a
/// six-day build cannot afford a codegen step in the loop.
///
/// **Adding strings:** put them in your module's section below, keyed
/// `screen.thing`. English is required — it is the fallback, so a missing
/// Hindi or Portuguese entry degrades to readable rather than blank. The
/// sections are separated so two people adding strings the same afternoon
/// touch different regions of the file.
library;

import 'app_language.dart';

/// Lookup for one language, falling back to English, then to the key itself.
///
/// Returning the key rather than an empty string is deliberate: an untranslated
/// label shows up as `planner.title` on screen during development, which is
/// impossible to miss, instead of a blank space nobody notices until demo day.
class AppStrings {
  const AppStrings(this.language);

  final AppLanguage language;

  String call(String key) {
    return _strings[language.code]?[key] ?? _strings['en']?[key] ?? key;
  }

  /// True when this key has no entry in the active language. Useful for
  /// spotting gaps in a translation pack without reading the whole map.
  bool isTranslated(String key) => _strings[language.code]?.containsKey(key) ?? false;
}

// ---------------------------------------------------------------------------
// Shared chrome — owned by whoever touches the shell. Keep this section small.
// ---------------------------------------------------------------------------
const Map<String, String> _sharedEn = {
  'app.title': 'AgriSetu',
  'nav.farmer': 'Farmer',
  'nav.commandCenter': 'Command Center',
  'nav.language': 'Language',
  'common.back': 'Back',
  'common.notBuiltYet': 'Not built yet',
};

const Map<String, String> _sharedHi = {
  'app.title': 'एग्रीसेतु',
  'nav.farmer': 'किसान',
  'nav.commandCenter': 'कमांड सेंटर',
  'nav.language': 'भाषा',
  'common.back': 'वापस',
  'common.notBuiltYet': 'अभी नहीं बना',
};

const Map<String, String> _sharedPt = {
  'app.title': 'AgriSetu',
  'nav.farmer': 'Agricultor',
  'nav.commandCenter': 'Centro de Comando',
  'nav.language': 'Idioma',
  'common.back': 'Voltar',
  'common.notBuiltYet': 'Ainda não construído',
};

// ---------------------------------------------------------------------------
// M0 field intelligence + M1 copilot — S1, S2.
// ---------------------------------------------------------------------------
const Map<String, String> _farmerEn = {
  'home.greeting': 'Namaste, Rekha',
  'home.today': 'TODAY',
  'home.scanCrop': 'Scan crop',
  'home.planSeason': 'Plan season',
  'home.speak': 'Read aloud',
  'advisory.loading': 'Reading your field…',
  'advisory.none': 'No advice yet — refresh once your field profile is built.',
  'advisory.saved': 'Saved advice, not refreshed today.',
  'advisory.fromDefaults': 'Based on district averages, not measurements of '
      'your field.',
  'advisory.stage': 'Growth stage',
};

const Map<String, String> _farmerHi = {
  'home.greeting': 'नमस्ते, रेखा',
  'home.today': 'आज',
  'home.scanCrop': 'फसल स्कैन करें',
  'home.planSeason': 'अगली फसल चुनें',
  'home.speak': 'सुनें',
  'advisory.loading': 'आपका खेत पढ़ा जा रहा है…',
  'advisory.none': 'अभी कोई सलाह नहीं — खेत की जानकारी बनने के बाद रिफ़्रेश करें।',
  'advisory.saved': 'सहेजी हुई सलाह, आज ताज़ा नहीं की गई।',
  'advisory.fromDefaults': 'यह इलाक़े के औसत पर आधारित है, आपके खेत की माप पर नहीं।',
  'advisory.stage': 'फसल की अवस्था',
};

const Map<String, String> _farmerPt = {
  'home.greeting': 'Olá, Rekha',
  'home.today': 'HOJE',
  'home.scanCrop': 'Escanear cultura',
  'home.planSeason': 'Planejar safra',
  'home.speak': 'Ouvir',
  'advisory.loading': 'Lendo seu talhão…',
  'advisory.none': 'Ainda sem recomendação — atualize depois que o perfil do '
      'talhão for montado.',
  'advisory.saved': 'Recomendação salva, não atualizada hoje.',
  'advisory.fromDefaults': 'Baseado em médias regionais, não em medições do '
      'seu talhão.',
  'advisory.stage': 'Estádio da cultura',
};

// ---------------------------------------------------------------------------
// M2 disease diagnostic — S3, S4.
// ---------------------------------------------------------------------------
const Map<String, String> _diagnosisEn = {
  'scan.title': 'Scan crop',
  'diagnosis.title': 'Diagnosis',
};

const Map<String, String> _diagnosisHi = {
  'scan.title': 'फसल स्कैन',
  'diagnosis.title': 'निदान',
};

const Map<String, String> _diagnosisPt = {
  'scan.title': 'Escanear cultura',
  'diagnosis.title': 'Diagnóstico',
};

// ---------------------------------------------------------------------------
// M3 regenerative advisor, M4 seed, M8 twin — S5, S6.
// ---------------------------------------------------------------------------
const Map<String, String> _plannerEn = {
  'planner.title': 'Next-season planner',
  'whatIf.title': 'What-if simulator',
};

const Map<String, String> _plannerHi = {
  'planner.title': 'अगले मौसम की योजना',
  'whatIf.title': 'क्या-अगर सिमुलेटर',
};

const Map<String, String> _plannerPt = {
  'planner.title': 'Planejador da próxima safra',
  'whatIf.title': 'Simulador de cenários',
};

// ---------------------------------------------------------------------------
// M5 nervous system, M6 economic engine, M7 federated DPI — S7–S10.
// ---------------------------------------------------------------------------
const Map<String, String> _commandEn = {
  'command.title': 'District risk',
  'region.title': 'Region detail',
  'scenario.title': 'Food security',
  'network.title': 'BRICS network',
};

const Map<String, String> _commandHi = {
  'command.title': 'जिला जोखिम',
  'region.title': 'क्षेत्र विवरण',
  'scenario.title': 'खाद्य सुरक्षा',
  'network.title': 'ब्रिक्स नेटवर्क',
};

const Map<String, String> _commandPt = {
  'command.title': 'Risco distrital',
  'region.title': 'Detalhe da região',
  'scenario.title': 'Segurança alimentar',
  'network.title': 'Rede BRICS',
};

const Map<String, Map<String, String>> _strings = {
  'en': {..._sharedEn, ..._farmerEn, ..._diagnosisEn, ..._plannerEn, ..._commandEn},
  'hi': {..._sharedHi, ..._farmerHi, ..._diagnosisHi, ..._plannerHi, ..._commandHi},
  'pt': {..._sharedPt, ..._farmerPt, ..._diagnosisPt, ..._plannerPt, ..._commandPt},
};
