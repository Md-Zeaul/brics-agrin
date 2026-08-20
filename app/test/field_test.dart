// Client-side M0 tests: geometry parity with the backend, and contract parsing.

import 'dart:convert';

import 'package:agrisetu/features/field/domain/field_profile.dart';
import 'package:agrisetu/features/field/domain/geometry.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('self-intersection', () {
    // Must agree vertex-for-vertex with is_simple in backend/m0_field/geometry.py.
    const square = [
      [29.610, 76.110],
      [29.610, 76.114],
      [29.607, 76.114],
      [29.607, 76.110],
    ];
    const bowtie = [
      [29.610, 76.110],
      [29.610, 76.114],
      [29.607, 76.110],
      [29.607, 76.114],
    ];

    test('a square is simple', () => expect(isSimple(square), isTrue));

    test('a closed ring is simple',
        () => expect(isSimple([...square, square.first]), isTrue));

    test('a triangle cannot cross itself',
        () => expect(isSimple(square.take(3).toList()), isTrue));

    test('a concave field stays valid', () {
      // Concave is legitimate — many real fields are. Only crossing is not.
      expect(
        isSimple(const [
          [0.0, 0.0],
          [0.0, 3.0],
          [2.0, 3.0],
          [2.0, 2.0],
          [1.0, 2.0],
          [1.0, 0.0],
        ]),
        isTrue,
      );
    });

    test('a bow-tie is rejected', () => expect(isSimple(bowtie), isFalse));

    test('which matters because its area shoelaces to zero',
        () => expect(areaHaOf(bowtie), 0.0));
  });

  group('geometry', () {
    test('square polygon has the requested area', () {
      final polygon = squarePolygonAround(29.61, 76.11, areaHa: 1.5);
      expect(areaHaOf(polygon), closeTo(1.5, 0.02));
    });

    test('polygon is a closed ring', () {
      final polygon = squarePolygonAround(29.61, 76.11);
      expect(polygon.first, equals(polygon.last));
    });

    test('centroid returns to the pin', () {
      final centroid = centroidOf(squarePolygonAround(29.61, 76.11));
      expect(centroid.lat, closeTo(29.61, 0.0001));
      expect(centroid.lng, closeTo(76.11, 0.0001));
    });

    test('area scales with the request', () {
      final small = areaHaOf(squarePolygonAround(29.61, 76.11, areaHa: 1.0));
      final large = areaHaOf(squarePolygonAround(29.61, 76.11, areaHa: 4.0));
      expect(large / small, closeTo(4.0, 0.05));
    });

    test('agrees with the backend polygon for the demo field', () {
      // Emitted by `python3 backend/run_local.py` for 29.61, 76.11 at 1.5 ha.
      final backend = [
        [29.609446, 76.109367],
        [29.609446, 76.110633],
        [29.610554, 76.110633],
        [29.610554, 76.109367],
        [29.609446, 76.109367],
      ];
      final client = squarePolygonAround(29.61, 76.11, areaHa: 1.5);
      for (var i = 0; i < backend.length; i++) {
        expect(client[i][0], closeTo(backend[i][0], 1e-6));
        expect(client[i][1], closeTo(backend[i][1], 1e-6));
      }
    });
  });

  group('FieldProfile parsing', () {
    // A trimmed real response from the M0 endpoint.
    const raw = '''
    {
      "fieldId": "field-demo-narwana",
      "polygon": [[29.609446,76.109367],[29.610554,76.110633]],
      "centroid": {"lat": 29.61, "lng": 76.11},
      "areaHa": 1.5011,
      "ndvi": null,
      "soil": {"ph": 7.9, "n": 1.33, "p": null, "k": null,
               "cec": 12.8, "moisture": 0.48, "soc": 9.2, "clay": 20.2},
      "rainForecastMm": 0.9,
      "rainForecast7dMm": 35.6,
      "tempForecast": [{"date":"2026-08-19","maxC":33.5,"minC":27.0},
                       {"date":"2026-08-21","maxC":32.4,"minC":25.5}],
      "radiationScore": 0.391,
      "healthChip": "YELLOW",
      "sources": {
        "soil": {"source":"ISRIC SoilGrids v2.0","status":"live"},
        "ndvi": {"source":"Sentinel-2","status":"unavailable","note":"no credentials"}
      },
      "generatedAt": "2026-08-19T14:21:20+00:00"
    }''';

    late FieldProfile profile;

    setUp(() {
      profile = FieldProfile.fromJson(
        jsonDecode(raw) as Map<String, dynamic>,
      );
    });

    test('reads the core signals', () {
      expect(profile.fieldId, 'field-demo-narwana');
      expect(profile.areaHa, closeTo(1.5011, 0.0001));
      expect(profile.soil.ph, 7.9);
      expect(profile.rainForecastMm, 0.9);
      expect(profile.healthChip, HealthChip.yellow);
    });

    test('tolerates a null NDVI rather than throwing', () {
      expect(profile.ndvi, isNull);
    });

    test('keeps phosphorus and potassium null', () {
      expect(profile.soil.p, isNull);
      expect(profile.soil.k, isNull);
    });

    test('bands soil chemistry for the advisory', () {
      expect(profile.soil.phBand, 'alkaline');
      expect(profile.soil.nitrogenBand, 'medium');
    });

    test('finds the peak temperature M3 penalises on', () {
      expect(profile.peakTempC, 33.5);
    });

    test('parses per-signal provenance', () {
      expect(profile.sources['soil']!.status, SignalStatus.live);
      expect(profile.sources['ndvi']!.status, SignalStatus.unavailable);
      expect(profile.sources['ndvi']!.note, 'no credentials');
    });

    test('is not fully live while NDVI is missing', () {
      expect(profile.isFullyLive, isFalse);
    });

    test('round-trips through JSON', () {
      final again = FieldProfile.fromJson(
        jsonDecode(jsonEncode(profile.toJson())) as Map<String, dynamic>,
      );
      expect(again.soil.ph, profile.soil.ph);
      expect(again.healthChip, profile.healthChip);
      expect(again.sources.length, profile.sources.length);
    });

    test('survives a sparse payload', () {
      final sparse = FieldProfile.fromJson(
        jsonDecode('{"fieldId":"f"}') as Map<String, dynamic>,
      );
      expect(sparse.polygon, isEmpty);
      expect(sparse.healthChip, HealthChip.yellow);
      expect(sparse.soil.ph, isNull);
    });
  });
}
