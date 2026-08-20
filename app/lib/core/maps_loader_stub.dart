/// Non-web implementation of the Maps loader.
library;

import 'package:flutter/foundation.dart';

/// Whether a Google map can be shown on this platform.
///
/// `google_maps_flutter` ships Android, iOS and web implementations only —
/// notably not macOS, which is a target for this prototype, so a key alone is
/// not enough to justify showing the map.
Future<bool> ensureMapsLoaded(String apiKey) async {
  if (apiKey.isEmpty) return false;
  return defaultTargetPlatform == TargetPlatform.android ||
      defaultTargetPlatform == TargetPlatform.iOS;
}
