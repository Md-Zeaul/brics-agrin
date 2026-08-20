/// Offline persistence for the field profile.
///
/// The Tech Spec makes offline-first a non-functional requirement for the whole
/// farmer flow (S1-S6) and the Build Brief warns never to trust venue wifi, so
/// the last good profile is always kept on device.
///
/// Backed by SharedPreferences for the prototype; swap for Firestore's offline
/// persistence or Hive once Firebase is provisioned — the interface holds.
library;

import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../domain/field_profile.dart';

class FieldCache {
  /// Bump when the stored shape changes.
  ///
  /// A profile saved before `boundaryMode` existed parses cleanly and defaults
  /// to `pin`, so a drawn 12 ha field silently comes back as a 1.5 ha square —
  /// wrong in a way no try/catch can see. Versioning the key drops those
  /// entries instead of trusting them.
  static const int _schema = 2;
  static const String _key = 'agrisetu.field_profile.v$_schema';

  /// Keys from earlier schemas, removed on first access.
  static const List<String> _superseded = ['agrisetu.field_profile'];

  Future<void> save(FieldProfile profile) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, jsonEncode(profile.toJson()));
  }

  /// The last successfully-built profile, or null on a cold install.
  Future<FieldProfile?> load() async {
    final prefs = await SharedPreferences.getInstance();
    for (final stale in _superseded) {
      if (prefs.containsKey(stale)) await prefs.remove(stale);
    }
    final raw = prefs.getString(_key);
    if (raw == null) return null;
    try {
      return FieldProfile.fromJson(jsonDecode(raw) as Map<String, dynamic>);
    } catch (_) {
      // A cache we cannot parse is worse than none; drop it and refetch.
      await prefs.remove(_key);
      return null;
    }
  }

  Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_key);
    for (final stale in _superseded) {
      await prefs.remove(stale);
    }
  }
}
