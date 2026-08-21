/// The languages the demo runs in.
///
/// Voice and language are first-class in the Build Brief, not polish: the
/// advisory is spoken in Hindi on S2, and S10's whole point is that the same
/// app flips to Portuguese for the Brazil node. Both need the same fact — which
/// language is active right now — so it lives in one place.
library;

enum AppLanguage {
  /// The fallback. Every string exists in English; the others may be partial.
  english('en', 'English', 'en-IN'),

  /// The demo language for the farmer flow (S1–S6).
  hindi('hi', 'हिन्दी', 'hi-IN'),

  /// The cross-border proof (S10). 20% of the score rides on this switch.
  portuguese('pt', 'Português', 'pt-BR');

  const AppLanguage(this.code, this.label, this.voiceLocale);

  /// ISO 639-1, and the key strings are looked up under.
  final String code;

  /// Written in the language itself — a Hindi speaker should not have to read
  /// the word "Hindi" in English to find it.
  final String label;

  /// BCP-47 for Cloud Text-to-Speech and Speech-to-Text. Region matters: a
  /// `pt-PT` voice reading a Brazilian advisory sounds wrong to the audience
  /// M7 is meant to convince.
  final String voiceLocale;

  static AppLanguage fromCode(String? code) {
    for (final language in values) {
      if (language.code == code) return language;
    }
    return english;
  }
}
