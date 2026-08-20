// Coordinate parsing: the shapes a real land record or phone actually produces.
import 'package:agrisetu/features/field/domain/coordinates.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('decimal pairs', () {
    test('comma separated', () {
      final r = parseLatLng('29.61, 76.11');
      expect(r.isValid, isTrue);
      expect(r.value!.lat, closeTo(29.61, 1e-9));
      expect(r.value!.lng, closeTo(76.11, 1e-9));
    });

    test('space separated', () {
      final r = parseLatLng('29.61 76.11');
      expect(r.value!.lat, closeTo(29.61, 1e-9));
      expect(r.value!.lng, closeTo(76.11, 1e-9));
    });

    test('negative values survive', () {
      final r = parseLatLng('-12.55, -55.72');
      expect(r.value!.lat, closeTo(-12.55, 1e-9));
      expect(r.value!.lng, closeTo(-55.72, 1e-9));
    });

    test('surrounding text is tolerated', () {
      final r = parseLatLng('lat 29.61 lng 76.11');
      expect(r.value!.lat, closeTo(29.61, 1e-9));
      expect(r.value!.lng, closeTo(76.11, 1e-9));
    });
  });

  group('hemisphere letters', () {
    test('N and E stay positive', () {
      final r = parseLatLng('29.61N, 76.11E');
      expect(r.value!.lat, closeTo(29.61, 1e-9));
      expect(r.value!.lng, closeTo(76.11, 1e-9));
    });

    test('S and W go negative', () {
      final r = parseLatLng('12.55 S, 55.72 W');
      expect(r.value!.lat, closeTo(-12.55, 1e-9));
      expect(r.value!.lng, closeTo(-55.72, 1e-9));
    });

    test('longitude given first is put back in order', () {
      // A pasted "76.11E, 29.61N" must not become lat 76.11.
      final r = parseLatLng('76.11E, 29.61N');
      expect(r.value!.lat, closeTo(29.61, 1e-9));
      expect(r.value!.lng, closeTo(76.11, 1e-9));
    });
  });

  group('degrees minutes seconds', () {
    test('full DMS with symbols', () {
      final r = parseLatLng('29°36\'36"N 76°06\'36"E');
      expect(r.value!.lat, closeTo(29.61, 1e-4));
      expect(r.value!.lng, closeTo(76.11, 1e-4));
    });

    test('southern DMS is negative', () {
      final r = parseLatLng('12°33\'00"S 55°43\'12"W');
      expect(r.value!.lat, closeTo(-12.55, 1e-4));
      expect(r.value!.lng, closeTo(-55.72, 1e-4));
    });

    test('degrees and minutes only', () {
      final r = parseLatLng("29°36'N 76°06'E");
      expect(r.value!.lat, closeTo(29.6, 1e-4));
    });
  });

  group('rejections explain themselves', () {
    test('empty', () {
      expect(parseLatLng('').error, contains('Enter a latitude'));
    });

    test('only one number', () {
      expect(parseLatLng('29.61').error, contains('both'));
    });

    test('latitude out of range', () {
      expect(parseLatLng('129.61, 76.11').error, contains('between -90 and 90'));
    });

    test('longitude out of range', () {
      expect(
        parseLatLng('29.61, 276.11').error,
        contains('between -180 and 180'),
      );
    });

    test('words only', () {
      expect(parseLatLng('my field').isValid, isFalse);
    });
  });

  group('two-box form', () {
    test('valid pair', () {
      final r = parseLatLngPair('29.61', '76.11');
      expect(r.value!.lat, closeTo(29.61, 1e-9));
    });

    test('blank latitude is named', () {
      expect(parseLatLngPair('', '76.11').error, contains('Latitude'));
    });

    test('blank longitude is named', () {
      expect(parseLatLngPair('29.61', '').error, contains('Longitude'));
    });

    test('out of range latitude', () {
      expect(parseLatLngPair('91', '76.11').isValid, isFalse);
    });
  });

  test('formats at capture precision', () {
    expect(formatLatLng(29.61, 76.11), '29.61000, 76.11000');
  });
}
