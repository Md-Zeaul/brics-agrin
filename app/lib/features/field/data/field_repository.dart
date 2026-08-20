/// Coordinates the M0 endpoint and the offline cache.
///
/// Degradation is the point: a failed network call must surface the last good
/// profile rather than an error screen, because the farmer flow has to work
/// with no signal and the demo has to survive venue wifi.
library;

import '../domain/field_profile.dart';
import 'field_cache.dart';
import 'm0_client.dart';

/// A profile plus how it was obtained, so the UI can be honest about it.
class FieldProfileResult {
  const FieldProfileResult({
    required this.profile,
    required this.fromCache,
    this.warning,
  });

  final FieldProfile profile;

  /// True when the network call failed and this is the last good profile.
  final bool fromCache;

  /// Why the live call failed, when it did.
  final String? warning;
}

class FieldRepository {
  FieldRepository({M0Client? client, FieldCache? cache})
      : _client = client ?? M0Client(),
        _cache = cache ?? FieldCache();

  final M0Client _client;
  final FieldCache _cache;

  /// Build the profile for a pin, falling back to cache when M0 is unreachable.
  Future<FieldProfileResult> profileForPin({
    required double lat,
    required double lng,
    String fieldId = 'field-demo-narwana',
    double? fallbackNdvi,
    Map<String, dynamic>? seededSoil,
    Map<String, dynamic>? crop,
  }) =>
      _build(
        fieldId: fieldId,
        fallbackNdvi: fallbackNdvi,
        seededSoil: seededSoil,
        crop: crop,
        pin: (lat: lat, lng: lng),
      );

  /// Build the profile from a boundary the farmer drew themselves.
  Future<FieldProfileResult> profileForPolygon({
    required List<List<double>> polygon,
    String fieldId = 'field-demo-narwana',
    double? fallbackNdvi,
    Map<String, dynamic>? seededSoil,
    Map<String, dynamic>? crop,
  }) =>
      _build(
        fieldId: fieldId,
        fallbackNdvi: fallbackNdvi,
        seededSoil: seededSoil,
        crop: crop,
        polygon: polygon,
      );

  Future<FieldProfileResult> _build({
    required String fieldId,
    double? fallbackNdvi,
    Map<String, dynamic>? seededSoil,
    Map<String, dynamic>? crop,
    ({double lat, double lng})? pin,
    List<List<double>>? polygon,
  }) async {
    try {
      final profile = await _client.buildProfile(
        pin: pin,
        polygon: polygon,
        fieldId: fieldId,
        fallbackNdvi: fallbackNdvi,
        seededSoil: seededSoil,
        crop: crop,
      );
      await _cache.save(profile);
      return FieldProfileResult(profile: profile, fromCache: false);
    } on M0Exception catch (error) {
      final cached = await _cache.load();
      if (cached == null) rethrow;
      return FieldProfileResult(
        profile: cached,
        fromCache: true,
        warning: error.message,
      );
    }
  }

  /// The cached profile, for an instant first paint before any network call.
  Future<FieldProfile?> cachedProfile() => _cache.load();

  Future<void> clearCache() => _cache.clear();

  void dispose() => _client.dispose();
}
