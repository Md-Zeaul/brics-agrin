/// Coordinates the M1 endpoint and the offline cache.
///
/// Same shape as [FieldRepository], deliberately: a failed call surfaces the
/// last good advisory rather than an error, and the three ways it can reach the
/// screen stay distinguishable instead of collapsing into one "offline" flag.
library;

import '../../field/domain/field_profile.dart';
import '../domain/advisory.dart';
import 'advisory_cache.dart';
import 'm1_client.dart';

enum AdvisoryOrigin {
  /// Built by M1 during this run.
  live,

  /// Restored from cache without attempting a call.
  restored,

  /// A live call was attempted, failed, and this is the last good advice.
  stale,
}

class AdvisoryResult {
  const AdvisoryResult({
    required this.advisory,
    required this.origin,
    this.warning,
  });

  final Advisory advisory;
  final AdvisoryOrigin origin;

  /// Why the live call failed, when it did.
  final String? warning;

  bool get fromCache => origin != AdvisoryOrigin.live;
}

class AdvisoryRepository {
  AdvisoryRepository({M1Client? client, AdvisoryCache? cache})
      : _client = client ?? M1Client(),
        _cache = cache ?? AdvisoryCache();

  final M1Client _client;
  final AdvisoryCache _cache;

  /// Today's advice for this profile, falling back to cache when M1 is
  /// unreachable. Returns null only when there is neither.
  Future<AdvisoryResult?> adviseFor(
    FieldProfile profile, {
    String language = 'en',
  }) async {
    try {
      final advisory =
          await _client.advise(profile: profile, language: language);
      await _cache.save(profile.fieldId, advisory);
      return AdvisoryResult(advisory: advisory, origin: AdvisoryOrigin.live);
    } catch (error) {
      final cached = await _cache.load(profile.fieldId, language);
      if (cached == null) return null;
      return AdvisoryResult(
        advisory: cached,
        origin: AdvisoryOrigin.stale,
        warning: error is M1Exception ? error.message : error.toString(),
      );
    }
  }

  /// The stored advisory, with no network call attempted.
  Future<AdvisoryResult?> restored(String fieldId, String language) async {
    final cached = await _cache.load(fieldId, language);
    if (cached == null) return null;
    return AdvisoryResult(advisory: cached, origin: AdvisoryOrigin.restored);
  }

  Future<void> clear() => _cache.clear();

  void dispose() => _client.dispose();
}
