/// Build-time configuration.
///
/// Every externally-tunable value lives here so switching model, endpoint or
/// nation is a one-line change — the Data Model Spec calls for the Gemini model
/// id in particular to be a single config value, since `gemini-2.5-flash` is
/// scheduled to shut down in mid-October 2026.
///
/// Override at build time:
///   flutter run --dart-define=MAPS_KEY=... --dart-define=M0_ENDPOINT=...
class AppConfig {
  const AppConfig._();

  /// M0 field-intelligence endpoint. Defaults to the local dev server
  /// (`python3 backend/dev_server.py`); point at the Cloud Function in prod.
  static const String m0Endpoint = String.fromEnvironment(
    'M0_ENDPOINT',
    defaultValue: 'http://localhost:8787/m0',
  );

  /// Google Maps Platform key. Empty until the key is provisioned, which the
  /// map view detects to fall back to a schematic renderer.
  static const String mapsApiKey = String.fromEnvironment('MAPS_KEY');

  /// Switch to `gemini-3.1-flash-lite` if the demo runs past mid-October 2026.
  static const String geminiModel = String.fromEnvironment(
    'GEMINI_MODEL',
    defaultValue: 'gemini-2.5-flash',
  );

  /// Build Brief product defaults: Haryana wheat belt, near Narwana.
  static const double demoLat = 29.61;
  static const double demoLng = 76.11;
  static const double defaultPlotHa = 1.5;

  static bool get hasMapsKey => mapsApiKey.isNotEmpty;
}
