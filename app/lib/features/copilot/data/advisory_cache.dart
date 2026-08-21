/// Offline persistence for the advisory.
///
/// The Build Brief requires steps 1-5 of the demo to run from cache, and the
/// advisory is step 2. Kept per field *and* per language: the same field
/// advised in Hindi and in Portuguese is two different strings, and serving one
/// for the other is the exact failure S10's language flip would expose.
library;

import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../domain/advisory.dart';

class AdvisoryCache {
  static const int _schema = 1;
  static const String _prefix = 'agrisetu.advisory.v$_schema';

  static String _key(String fieldId, String language) =>
      '$_prefix:$fieldId:$language';

  Future<void> save(String fieldId, Advisory advisory) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      _key(fieldId, advisory.language),
      jsonEncode(advisory.toJson()),
    );
  }

  Future<Advisory?> load(String fieldId, String language) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key(fieldId, language));
    if (raw == null) return null;
    try {
      return Advisory.fromJson(jsonDecode(raw) as Map<String, dynamic>);
    } catch (_) {
      // An advisory we cannot parse is worse than none.
      await prefs.remove(_key(fieldId, language));
      return null;
    }
  }

  /// Drop every stored advisory, in every language, for every field.
  Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    for (final key in prefs.getKeys().where((k) => k.startsWith(_prefix))) {
      await prefs.remove(key);
    }
  }
}
