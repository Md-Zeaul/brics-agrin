/// Coordinates the M0 endpoint and the offline cache.
///
/// Degradation is the point: a failed network call must surface the last good
/// profile rather than an error screen, because the farmer flow has to work
/// with no signal and the demo has to survive venue wifi.
library;

import '../domain/field_profile.dart';
import 'field_cache.dart';
import 'm0_client.dart';

/// How a profile reached the screen. The three cases read alike to the code
/// and completely differently to the farmer, so they must not share a flag.
enum ProfileOrigin {
  /// Fetched from M0 during this run.
  live,

  /// Restored from cache on launch. No network call was attempted, so calling
  /// this "offline" would be a guess dressed as a fact.
  restored,

  /// A live call was attempted, failed, and this is the last good profile.
  stale,
}

/// A profile plus how it was obtained, so the UI can be honest about it.
class FieldProfileResult {
  const FieldProfileResult({
    required this.profile,
    required this.origin,
    this.warning,
  });

  final FieldProfile profile;

  final ProfileOrigin origin;

  /// Why the live call failed, when it did.
  final String? warning;

  /// True whenever the numbers on screen were not fetched this run.
  bool get fromCache => origin != ProfileOrigin.live;
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
    String? sowingDate,
    List<Map<String, dynamic>>? fertiliserLog,
    String? lastIrrigation,
  }) =>
      _build(
        fieldId: fieldId,
        fallbackNdvi: fallbackNdvi,
        seededSoil: seededSoil,
        crop: crop,
        sowingDate: sowingDate,
        fertiliserLog: fertiliserLog,
        lastIrrigation: lastIrrigation,
        pin: (lat: lat, lng: lng),
      );

  /// Build the profile from a boundary the farmer drew themselves.
  Future<FieldProfileResult> profileForPolygon({
    required List<List<double>> polygon,
    String fieldId = 'field-demo-narwana',
    double? fallbackNdvi,
    Map<String, dynamic>? seededSoil,
    Map<String, dynamic>? crop,
    String? sowingDate,
    List<Map<String, dynamic>>? fertiliserLog,
    String? lastIrrigation,
  }) =>
      _build(
        fieldId: fieldId,
        fallbackNdvi: fallbackNdvi,
        seededSoil: seededSoil,
        crop: crop,
        sowingDate: sowingDate,
        fertiliserLog: fertiliserLog,
        lastIrrigation: lastIrrigation,
        polygon: polygon,
      );

  Future<FieldProfileResult> _build({
    required String fieldId,
    double? fallbackNdvi,
    Map<String, dynamic>? seededSoil,
    Map<String, dynamic>? crop,
    String? sowingDate,
    List<Map<String, dynamic>>? fertiliserLog,
    String? lastIrrigation,
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
        sowingDate: sowingDate,
        fertiliserLog: fertiliserLog,
        lastIrrigation: lastIrrigation,
      );
      await _cache.save(profile);
      return FieldProfileResult(profile: profile, origin: ProfileOrigin.live);
    } on M0Exception catch (error) {
      final cached = await _cache.load();
      if (cached == null) rethrow;
      return FieldProfileResult(
        profile: cached,
        origin: ProfileOrigin.stale,
        warning: error.message,
      );
    }
  }

  /// The cached profile, for an instant first paint before any network call.
  Future<FieldProfile?> cachedProfile() => _cache.load();

  Future<void> clearCache() => _cache.clear();

  void dispose() => _client.dispose();
}
