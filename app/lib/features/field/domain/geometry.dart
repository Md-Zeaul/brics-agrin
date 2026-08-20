/// Client-side mirror of `backend/m0_field/geometry.py`.
///
/// The Build Brief wants the boundary outlined in under 30 seconds, so the app
/// draws the polygon the instant the pin moves rather than waiting on a round
/// trip. The backend still recomputes it authoritatively; this only has to
/// agree well enough to be the same square.
library;

import 'dart:math' as math;

const double defaultPlotHa = 1.5;
const double _metresPerDegreeLat = 110574.0;

double _metresPerDegreeLng(double latitude) =>
    111320.0 * math.cos(latitude * math.pi / 180.0);

/// A closed square polygon of [areaHa] centred on the pin, as [lat, lng] pairs.
List<List<double>> squarePolygonAround(
  double lat,
  double lng, {
  double areaHa = defaultPlotHa,
}) {
  final sideM = math.sqrt(areaHa * 10000.0);
  final halfLat = (sideM / 2.0) / _metresPerDegreeLat;
  final halfLng = (sideM / 2.0) / _metresPerDegreeLng(lat);

  double r(double v) => double.parse(v.toStringAsFixed(6));

  return [
    [r(lat - halfLat), r(lng - halfLng)],
    [r(lat - halfLat), r(lng + halfLng)],
    [r(lat + halfLat), r(lng + halfLng)],
    [r(lat + halfLat), r(lng - halfLng)],
    [r(lat - halfLat), r(lng - halfLng)],
  ];
}

/// Arithmetic centroid of the polygon's distinct vertices.
({double lat, double lng}) centroidOf(List<List<double>> polygon) {
  final points = openRing(polygon);
  if (points.isEmpty) return (lat: 0, lng: 0);
  final lat = points.map((p) => p[0]).reduce((a, b) => a + b) / points.length;
  final lng = points.map((p) => p[1]).reduce((a, b) => a + b) / points.length;
  return (lat: lat, lng: lng);
}

/// Shoelace area in hectares, projecting degrees to metres about the centroid.
double areaHaOf(List<List<double>> polygon) {
  final points = openRing(polygon);
  if (points.length < 3) return 0;

  final originLat =
      points.map((p) => p[0]).reduce((a, b) => a + b) / points.length;
  final lngScale = _metresPerDegreeLng(originLat);

  final xy = points
      .map((p) => (
            x: (p[1] - points[0][1]) * lngScale,
            y: (p[0] - points[0][0]) * _metresPerDegreeLat,
          ))
      .toList();

  var total = 0.0;
  for (var i = 0; i < xy.length; i++) {
    final a = xy[i];
    final b = xy[(i + 1) % xy.length];
    total += a.x * b.y - b.x * a.y;
  }

  return (total.abs() / 2.0) / 10000.0;
}

/// Drop the duplicated closing vertex if present.
List<List<double>> openRing(List<List<double>> polygon) =>
    polygon.length > 1 &&
            polygon.first[0] == polygon.last[0] &&
            polygon.first[1] == polygon.last[1]
        ? polygon.sublist(0, polygon.length - 1)
        : polygon;

/// True when no two edges of the boundary cross.
///
/// Mirrors `is_simple` in backend/m0_field/geometry.py. A farmer dragging
/// across their own line makes a bow-tie, and the shoelace formula sums the two
/// lobes with opposite winding: a crossed square reports 0.0 ha, not a wrong
/// one. Catching it here saves the round-trip and explains the problem while
/// the boundary is still on screen.
bool isSimple(List<List<double>> polygon) {
  final ring = openRing(polygon);
  final count = ring.length;
  if (count < 4) return true; // a triangle cannot cross itself

  for (var i = 0; i < count; i++) {
    final a1 = ring[i];
    final a2 = ring[(i + 1) % count];
    // Start at i+2: neighbouring edges legitimately share a vertex.
    for (var j = i + 2; j < count; j++) {
      // The last edge wraps to vertex 0, so it neighbours edge 0.
      if (i == 0 && j == count - 1) continue;
      if (_segmentsCross(a1, a2, ring[j], ring[(j + 1) % count])) return false;
    }
  }
  return true;
}

bool _segmentsCross(
  List<double> p1,
  List<double> p2,
  List<double> q1,
  List<double> q2,
) {
  final d1 = _orientation(q1, q2, p1);
  final d2 = _orientation(q1, q2, p2);
  final d3 = _orientation(p1, p2, q1);
  final d4 = _orientation(p1, p2, q2);

  if ((d1 > 0) != (d2 > 0) && (d3 > 0) != (d4 > 0)) return true;

  return (d1 == 0 && _onSegment(q1, q2, p1)) ||
      (d2 == 0 && _onSegment(q1, q2, p2)) ||
      (d3 == 0 && _onSegment(p1, p2, q1)) ||
      (d4 == 0 && _onSegment(p1, p2, q2));
}

/// Cross product sign: >0 left turn, <0 right turn, 0 collinear.
double _orientation(List<double> a, List<double> b, List<double> c) {
  final value = (b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1]);
  return value.abs() < 1e-12 ? 0.0 : value;
}

bool _onSegment(List<double> a, List<double> b, List<double> point) =>
    point[0] >= (a[0] < b[0] ? a[0] : b[0]) &&
    point[0] <= (a[0] > b[0] ? a[0] : b[0]) &&
    point[1] >= (a[1] < b[1] ? a[1] : b[1]) &&
    point[1] <= (a[1] > b[1] ? a[1] : b[1]);
