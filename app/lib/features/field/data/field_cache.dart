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
  static const String _key = 'agrisetu.field_profile';

  Future<void> save(FieldProfile profile) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, jsonEncode(profile.toJson()));
  }

  /// The last successfully-built profile, or null on a cold install.
  Future<FieldProfile?> load() async {
    final prefs = await SharedPreferences.getInstance();
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
  }
}
