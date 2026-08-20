/// Parsing typed or pasted coordinates.
///
/// A farmer who knows where their field is should not have to find it on a map.
/// Coordinates reach them in several shapes — a decimal pair copied out of a
/// phone, a hemisphere-suffixed pair from a survey sheet, degrees-minutes-
/// seconds off an older land record — so all three parse here rather than each
/// caller re-deriving the rules.
library;

/// The outcome of a parse: either a coordinate, or the reason there isn't one.
class ParsedCoordinates {
  const ParsedCoordinates.success(this.value) : error = null;
  const ParsedCoordinates.failure(this.error) : value = null;

  final ({double lat, double lng})? value;

  /// Written for the farmer, not the log — says what to do, not what broke.
  final String? error;

  bool get isValid => value != null;
}

/// One coordinate component. Minutes and seconds must carry their symbol,
/// otherwise "29.61 76.11" would read as one value with 76.11 minutes.
final _component = RegExp(
  r"(-?\d+(?:\.\d+)?)\s*[°d]?\s*"
  r"(?:(\d+(?:\.\d+)?)\s*['′m]\s*)?"
  r'(?:(\d+(?:\.\d+)?)\s*["″s]\s*)?'
  r'([NSEWnsew])?',
);

const _latRange = 90.0;
const _lngRange = 180.0;

/// Parse a latitude/longitude pair from free text.
///
/// Accepts `29.61, 76.11`, `29.61 76.11`, `29.61N 76.11E`, `12.55S, 55.72W`
/// and `29°36'36"N 76°06'36"E`. Hemisphere letters, when present, decide which
/// number is which — so a pasted `76.11E, 29.61N` still lands correctly.
ParsedCoordinates parseLatLng(String input) {
  final text = input.trim();
  if (text.isEmpty) {
    return const ParsedCoordinates.failure(
      'Enter a latitude and longitude, e.g. 29.61, 76.11',
    );
  }

  final found = <({double value, String? hemisphere})>[];
  for (final match in _component.allMatches(text)) {
    if (match.group(0)!.trim().isEmpty) continue;
    final parsed = _componentValue(match);
    if (parsed != null) found.add(parsed);
    if (found.length == 2) break;
  }

  if (found.length < 2) {
    return const ParsedCoordinates.failure(
      'Enter both a latitude and a longitude, e.g. 29.61, 76.11',
    );
  }

  var (first, second) = (found[0], found[1]);

  // A hemisphere letter is authoritative about which number it is; without one
  // we fall back to the near-universal latitude-first convention.
  final firstIsLng = _isLongitude(first.hemisphere);
  final secondIsLat = _isLatitude(second.hemisphere);
  if (firstIsLng || secondIsLat) {
    if (firstIsLng && !_isLongitude(second.hemisphere)) {
      (first, second) = (second, first);
    }
  }

  final lat = first.value;
  final lng = second.value;

  if (lat.abs() > _latRange) {
    return const ParsedCoordinates.failure(
      'Latitude must be between -90 and 90',
    );
  }
  if (lng.abs() > _lngRange) {
    return const ParsedCoordinates.failure(
      'Longitude must be between -180 and 180',
    );
  }

  return ParsedCoordinates.success((lat: lat, lng: lng));
}

/// Validate a single already-separated field, for the two-box form.
ParsedCoordinates parseLatLngPair(String latText, String lngText) {
  final lat = _single(latText);
  final lng = _single(lngText);

  if (lat == null) {
    return const ParsedCoordinates.failure('Latitude is not a number');
  }
  if (lng == null) {
    return const ParsedCoordinates.failure('Longitude is not a number');
  }
  if (lat.abs() > _latRange) {
    return const ParsedCoordinates.failure(
      'Latitude must be between -90 and 90',
    );
  }
  if (lng.abs() > _lngRange) {
    return const ParsedCoordinates.failure(
      'Longitude must be between -180 and 180',
    );
  }
  return ParsedCoordinates.success((lat: lat, lng: lng));
}

double? _single(String text) {
  final trimmed = text.trim();
  if (trimmed.isEmpty) return null;
  final match = _component.firstMatch(trimmed);
  if (match == null) return null;
  return _componentValue(match)?.value;
}

({double value, String? hemisphere})? _componentValue(RegExpMatch match) {
  final degrees = double.tryParse(match.group(1) ?? '');
  if (degrees == null) return null;

  final minutes = double.tryParse(match.group(2) ?? '') ?? 0;
  final seconds = double.tryParse(match.group(3) ?? '') ?? 0;
  final hemisphere = match.group(4)?.toUpperCase();

  // Sign lives on the degrees, so minutes and seconds always add magnitude.
  var value = degrees.abs() + minutes / 60.0 + seconds / 3600.0;
  if (degrees.isNegative) value = -value;
  if (hemisphere == 'S' || hemisphere == 'W') value = -value.abs();

  return (value: value, hemisphere: hemisphere);
}

bool _isLatitude(String? hemisphere) => hemisphere == 'N' || hemisphere == 'S';
bool _isLongitude(String? hemisphere) => hemisphere == 'E' || hemisphere == 'W';

/// Round-trip display, matching the precision the capture screen shows.
String formatLatLng(double lat, double lng) =>
    '${lat.toStringAsFixed(5)}, ${lng.toStringAsFixed(5)}';
