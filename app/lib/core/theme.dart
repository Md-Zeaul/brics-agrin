/// The app's one theme.
///
/// Lives here rather than inline in `main.dart` so a widget test can pump a
/// screen under the same theme the app ships. That matters for exactly one
/// reason today, and it is not decoration: the Devanagari font fallback is
/// declared here, so a test asserting Hindi will render is testing the real
/// configuration rather than a copy of it.
library;

import 'package:flutter/material.dart';

class AppTheme {
  const AppTheme._();

  static const Color seed = Color(0xFF2E7D32);

  /// The bundled Devanagari face, named exactly as `pubspec.yaml` declares it.
  ///
  /// Roboto covers no Devanagari at all. On the web Flutter papers over that by
  /// fetching a Noto fallback from Google's CDN the first time it meets one —
  /// which works right up until the demo runs offline, and then every Hindi
  /// string on screen becomes an empty box. Naming the bundled family as an
  /// explicit fallback means the glyphs are already in the bundle and no
  /// network request is ever made for them.
  static const String devanagari = 'Noto Sans Devanagari';

  static ThemeData light() {
    return ThemeData(
      colorScheme: ColorScheme.fromSeed(seedColor: seed),
      useMaterial3: true,
      fontFamilyFallback: const [devanagari],
    );
  }
}
