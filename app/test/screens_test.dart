// Widget tests for S1 and S2 — they must render with no network and no keys.

import 'dart:convert';
import 'dart:io';

import 'package:agrisetu/features/field/data/field_repository.dart';
import 'package:agrisetu/features/field/domain/crop.dart';
import 'package:agrisetu/features/field/domain/field_profile.dart';
import 'package:agrisetu/features/field/presentation/home_screen.dart';
import 'package:agrisetu/features/field/presentation/onboarding_screen.dart';
import 'package:agrisetu/features/field/presentation/widgets/crop_picker.dart';
import 'package:agrisetu/features/field/presentation/widgets/field_map_view.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

FieldProfile _profile({
  double? ndvi,
  HealthChip chip = HealthChip.yellow,
  String driver = 'ndvi_unavailable',
  double? percentile,
  String boundaryMode = 'pin',
  Map<String, dynamic>? crop,
}) {
  return FieldProfile(
    fieldId: 'field-demo-narwana',
    polygon: const [
      [29.609446, 76.109367],
      [29.609446, 76.110633],
      [29.610554, 76.110633],
      [29.610554, 76.109367],
      [29.609446, 76.109367],
    ],
    centroid: (lat: 29.61, lng: 76.11),
    areaHa: 1.5011,
    boundaryMode: boundaryMode,
    crop: crop,
    ndviPercentile: percentile,
    soil: const Soil(ph: 7.9, n: 1.33, cec: 12.8, moisture: 0.48),
    healthChip: chip,
    ndvi: ndvi,
    rainForecastMm: 0.9,
    rainForecast7dMm: 35.6,
    tempForecast: const [DailyTemp(date: '2026-08-19', maxC: 33.5, minC: 27.0)],
    radiationScore: 0.391,
    sources: {
      'soil': const Provenance(
        source: 'ISRIC SoilGrids v2.0',
        status: SignalStatus.live,
      ),
      'ndvi': const Provenance(
        source: 'Sentinel-2 via Earth Engine',
        status: SignalStatus.unavailable,
        note: 'no Earth Engine credentials',
      ),
      'healthChip': Provenance(
        source: 'M0 rule set',
        status: SignalStatus.live,
        note: 'driver: $driver',
      ),
    },
  );
}

void main() {
  group('S1 onboarding', () {
    testWidgets('renders the map, crop default and confirm action',
        (tester) async {
      await tester.pumpOnboarding();
      // The crop registry loads from an asset; let it arrive.
      await tester.pumpAndSettle();

      expect(find.text('Your field'), findsOneWidget);
      expect(find.text('Confirm field'), findsOneWidget);
      // Build Brief default crop, shown in the default language (Hindi).
      expect(find.text('गेहूँ'), findsOneWidget);
      // Pre-dropped on the demo field, so no typing is needed.
      expect(find.textContaining('29.61000, 76.11000'), findsOneWidget);
      expect(find.textContaining('1.50 ha'), findsWidgets);
    });

    testWidgets('the crop label follows the language toggle', (tester) async {
      await tester.pumpOnboarding();
      await tester.pumpAndSettle();
      expect(find.text('गेहूँ'), findsOneWidget);

      await tester.tap(find.text('EN'));
      await tester.pumpAndSettle();
      expect(find.text('Wheat'), findsOneWidget);
    });

    testWidgets('tapping the map moves the pin and redraws the boundary',
        (tester) async {
      await tester.pumpOnboarding();

      final before = tester.widget<Text>(
        find.textContaining('29.61000').first,
      );

      await tester.tapAt(const Offset(80, 120));
      await tester.pumpAndSettle();

      final after = tester.widget<Text>(
        find.textContaining(',').first,
      );
      expect(after.data, isNot(equals(before.data)));
    });
  });

  cropTests();
  drawingTests();

  group('S1 coordinate entry', () {
    testWidgets('typing a coordinate moves the pin', (tester) async {
      await tester.pumpOnboarding();

      expect(find.textContaining('29.61000, 76.11000'), findsOneWidget);

      await tester.tap(find.text('Enter coordinates'));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.widgetWithText(TextField, 'Latitude').first,
        '-12.55',
      );
      await tester.enterText(
        find.widgetWithText(TextField, 'Longitude').first,
        '-55.72',
      );
      await tester.tap(find.text('Go to this field'));
      await tester.pumpAndSettle();

      expect(find.textContaining('-12.55000, -55.72000'), findsOneWidget);
    });

    testWidgets('an out-of-range latitude is refused with a reason',
        (tester) async {
      await tester.pumpOnboarding();
      await tester.tap(find.text('Enter coordinates'));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.widgetWithText(TextField, 'Latitude').first,
        '129',
      );
      await tester.tap(find.text('Go to this field'));
      await tester.pumpAndSettle();

      expect(find.text('Latitude must be between -90 and 90'), findsOneWidget);
      // The sheet stays open so the farmer can correct it.
      expect(find.text('Go to this field'), findsOneWidget);
    });

    testWidgets('cancelling leaves the pin where it was', (tester) async {
      await tester.pumpOnboarding();
      await tester.tap(find.text('Enter coordinates'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(find.textContaining('29.61000, 76.11000'), findsOneWidget);
    });

    testWidgets('coordinate entry is offered for pins, not drawn boundaries',
        (tester) async {
      await tester.pumpOnboarding();
      expect(find.text('Enter coordinates'), findsOneWidget);

      await tester.tap(find.text('Draw boundary'));
      await tester.pumpAndSettle();
      expect(find.text('Enter coordinates'), findsNothing);
    });
  });

  group('S1 crop picker', () {
    // The field is pre-filled with the current crop. Filtering by that text
    // would offer exactly one option — the crop already chosen — which is the
    // bug this group exists to prevent.
    final registry = CropRegistry(const [
      Crop(id: 'wheat', en: 'Wheat', hi: 'गेहूँ', category: 'cereal'),
      Crop(id: 'rice', en: 'Rice', hi: 'चावल', category: 'cereal'),
      Crop(id: 'sugarcane', en: 'Sugarcane', hi: 'गन्ना', category: 'cash'),
    ]);

    Future<void> pumpPicker(WidgetTester tester, {Crop? selected}) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: CropPicker(
              registry: registry,
              selected: selected ?? registry.crops.first,
              language: 'en',
              onChanged: (_) {},
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
    }

    testWidgets('tapping the field offers every crop, not just the current one',
        (tester) async {
      await pumpPicker(tester);

      await tester.tap(find.byType(TextFormField));
      await tester.pumpAndSettle();

      expect(find.text('Rice'), findsOneWidget);
      expect(find.text('Sugarcane'), findsOneWidget);
    });

    testWidgets('the dropdown arrow opens the list', (tester) async {
      await pumpPicker(tester);

      await tester.tap(find.byTooltip('Show all crops'));
      await tester.pumpAndSettle();

      expect(find.text('Sugarcane'), findsOneWidget);
    });

    testWidgets('typing filters the list', (tester) async {
      await pumpPicker(tester);

      await tester.enterText(find.byType(TextFormField), 'sug');
      await tester.pumpAndSettle();

      expect(find.text('Sugarcane'), findsOneWidget);
      expect(find.text('Rice'), findsNothing);
    });

    testWidgets('an unlisted crop is still accepted', (tester) async {
      await pumpPicker(tester);

      await tester.enterText(find.byType(TextFormField), 'dragon fruit');
      await tester.pumpAndSettle();

      expect(find.text('Use what you typed'), findsOneWidget);
    });

    testWidgets('searching in Hindi finds the crop', (tester) async {
      await pumpPicker(tester);

      await tester.enterText(find.byType(TextFormField), 'गन्ना');
      await tester.pumpAndSettle();

      expect(find.text('Sugarcane'), findsOneWidget);
    });
  });

  group('S2 home', () {
    testWidgets('shows the M0 signals and their provenance', (tester) async {
      tester.useTallSurface();
      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            result: FieldProfileResult(profile: _profile(), origin: ProfileOrigin.live),
            repository: FieldRepository(),
          ),
        ),
      );

      expect(find.text('Namaste, Rekha'), findsOneWidget);
      expect(find.text('Watch'), findsOneWidget); // YELLOW chip
      expect(find.textContaining('0.9 mm of rain'), findsOneWidget);
      expect(find.textContaining('7.9 · alkaline'), findsOneWidget);
      expect(find.textContaining('1.33 g/kg · medium'), findsOneWidget);
      // The gap is stated, not hidden.
      expect(find.text('no remote source'), findsNWidgets(2));
      expect(find.text('awaiting Earth Engine'), findsOneWidget);

      // Provenance sits below the fold; scroll until it is reachable rather
      // than guessing a distance that breaks whenever the page grows.
      await tester.scrollUntilVisible(
        find.textContaining('Unavailable'),
        300,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.textContaining('Unavailable'), findsOneWidget);
      expect(
        find.textContaining('no Earth Engine credentials'),
        findsOneWidget,
      );
    });

    testWidgets('soil values show their confidence interval when known',
        (tester) async {
      final profile = FieldProfile(
        fieldId: 'f',
        polygon: const [],
        centroid: (lat: 29.61, lng: 76.11),
        areaHa: 1.5,
        soil: const Soil(ph: 7.9),
        healthChip: HealthChip.green,
        // SoilGrids' real interval for the demo field: wide enough that a bare
        // "7.9" would overstate what the model actually knows.
        soilRange: const {'ph': (low: 6.2, high: 10.3)},
      );

      tester.useTallSurface();
      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            result: FieldProfileResult(profile: profile, origin: ProfileOrigin.live),
            repository: FieldRepository(),
          ),
        ),
      );

      expect(find.textContaining('likely 6.2-10.3'), findsOneWidget);
    });

    testWidgets('water balance turns rain and demand into one number',
        (tester) async {
      final profile = FieldProfile(
        fieldId: 'f',
        polygon: const [],
        centroid: (lat: 29.61, lng: 76.11),
        areaHa: 1.5,
        soil: const Soil(),
        healthChip: HealthChip.green,
        climate: const {
          'observedRain7dMm': 3.7,
          'et0MmPerDay': 5.39,
          'vpdKpa': 0.92,
          'soilWater': {'0_7cm': 0.342, '7_28cm': 0.281},
        },
        terrain: const {'elevationM': 227.9, 'slopeDeg': 1.98},
      );

      expect(profile.weeklyWaterBalanceMm, closeTo(3.7 - 5.39 * 7, 0.01));

      tester.useTallSurface();
      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            result: FieldProfileResult(profile: profile, origin: ProfileOrigin.live),
            repository: FieldRepository(),
          ),
        ),
      );
      // 3.7 mm of rain against 37.7 mm of demand is a deficit, however wet the
      // month looked.
      await tester.scrollUntilVisible(
        find.textContaining('deficit'),
        300,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.textContaining('deficit'), findsOneWidget);
      expect(find.textContaining('0.342 m³/m³'), findsOneWidget);

      await tester.scrollUntilVisible(
        find.textContaining('1.98°'),
        300,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.textContaining('1.98°'), findsOneWidget);
    });

    testWidgets('a live NDVI replaces the pending label', (tester) async {
      tester.useTallSurface();
      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            result: FieldProfileResult(
              profile: _profile(ndvi: 0.62, chip: HealthChip.green),
              origin: ProfileOrigin.live,
            ),
            repository: FieldRepository(),
          ),
        ),
      );

      expect(find.text('0.620'), findsOneWidget);
      expect(find.text('Healthy'), findsOneWidget);
      expect(find.text('awaiting Earth Engine'), findsNothing);
    });

    testWidgets('GREEN explains itself instead of repeating the word',
        (tester) async {
      tester.useTallSurface();
      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            result: FieldProfileResult(
              profile: _profile(
                chip: HealthChip.green,
                driver: 'healthy',
                percentile: 0.598,
                ndvi: 0.579,
              ),
              origin: ProfileOrigin.live,
            ),
            repository: FieldRepository(),
          ),
        ),
      );

      expect(find.text('Healthy'), findsOneWidget);
      // Not "Healthy · healthy" — the standing itself is the explanation.
      expect(
        find.textContaining('ahead of 60% of nearby farms'),
        findsOneWidget,
      );
    });

    testWidgets('a pinned area is labelled a default, not a measurement',
        (tester) async {
      tester.useTallSurface();
      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            result: FieldProfileResult(profile: _profile(), origin: ProfileOrigin.live),
            repository: FieldRepository(),
          ),
        ),
      );

      expect(find.textContaining('1.50 ha'), findsOneWidget);
      expect(find.text('default size · draw to measure'), findsOneWidget);
    });

    testWidgets('a drawn area says it was measured', (tester) async {
      tester.useTallSurface();
      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            result: FieldProfileResult(
              profile: _profile(boundaryMode: 'drawn'),
              origin: ProfileOrigin.live,
            ),
            repository: FieldRepository(),
          ),
        ),
      );

      expect(find.text('measured from your boundary'), findsOneWidget);
    });

    testWidgets('the crop the farmer chose is the one shown', (tester) async {
      tester.useTallSurface();
      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            result: FieldProfileResult(
              profile: _profile(crop: const {'id': 'sugarcane', 'label': 'Sugarcane'}),
              origin: ProfileOrigin.live,
            ),
            repository: FieldRepository(),
          ),
        ),
      );

      expect(find.textContaining('Sugarcane'), findsOneWidget);
    });

    testWidgets('a restored profile is not called offline', (tester) async {
      // Booting from cache attempts no network call, so claiming the farmer is
      // offline would be a guess presented as a fact.
      tester.useTallSurface();
      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            result: FieldProfileResult(
              profile: _profile(),
              origin: ProfileOrigin.restored,
            ),
            repository: FieldRepository(),
          ),
        ),
      );

      expect(find.textContaining('Saved profile from your last visit'),
          findsOneWidget);
      expect(find.textContaining('Offline'), findsNothing);
    });

    testWidgets('a second field can be captured from the profile',
        (tester) async {
      tester.useTallSurface();
      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            result: FieldProfileResult(
              profile: _profile(),
              origin: ProfileOrigin.restored,
            ),
            repository: FieldRepository(),
          ),
        ),
      );

      await tester.tap(find.byTooltip('Capture a different field'));
      await tester.pumpAndSettle();

      expect(find.byType(OnboardingScreen), findsOneWidget);
    });

    testWidgets('offline cache shows the banner', (tester) async {
      tester.useTallSurface();
      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            result: FieldProfileResult(
              profile: _profile(),
              origin: ProfileOrigin.stale,
              warning: 'could not reach M0',
            ),
            repository: FieldRepository(),
          ),
        ),
      );

      expect(find.textContaining('Offline'), findsOneWidget);
      expect(find.textContaining('could not reach M0'), findsOneWidget);
    });
  });
}

// --- Boundary drawing (M0's "drops a pin (or draws a boundary)") ---

extension on WidgetTester {
  /// A lazy ListView only builds what fits the viewport, so on the default
  /// 600px test surface a section that exists further down simply is not there
  /// to find. S2 is a long scroll and gains a card with every module; asserting
  /// against a tall surface keeps those tests about content, not about how far
  /// the page happens to have grown this week. The width stays phone-sized so
  /// overflow still fails loudly.
  void useTallSurface() {
    view.physicalSize = const Size(1170, 3600);
    view.devicePixelRatio = 3.0;
    addTearDown(view.resetPhysicalSize);
    addTearDown(view.resetDevicePixelRatio);
  }

  Future<void> pumpOnboarding() async {
    await pumpWidget(
      MaterialApp(home: OnboardingScreen(repository: FieldRepository())),
    );
  }

  /// Tap at a fractional position inside the map, so the test does not break
  /// when the controls below it change height.
  Future<void> tapMap(double fx, double fy) async {
    final rect = getRect(find.byType(FieldMapView));
    await tapAt(Offset(
      rect.left + rect.width * fx,
      rect.top + rect.height * fy,
    ));
    await pumpAndSettle();
  }
}

void cropTests() {
  group('crop registry', () {
    // rootBundle hangs inside flutter_test's fake-async zone, so the asset is
    // validated from disk instead: same file, same guarantee, no bundle.
    test('the shipped asset parses and carries the expected crops', () {
      final file = File('assets/crops.json');
      expect(file.existsSync(), isTrue);

      final decoded = jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
      final crops = (decoded['crops'] as List)
          .map((c) => Crop.fromJson(c as Map<String, dynamic>))
          .toList();
      final registry = CropRegistry(crops);

      expect(crops.length, greaterThan(20));
      expect(registry.byId('wheat')?.en, 'Wheat');
      expect(registry.byId('soybean')?.en, 'Soybean');
      expect(registry.byId('rice')?.hi, 'चावल');
      // Ids are what downstream modules key on; duplicates would be silent bugs.
      expect(crops.map((c) => c.id).toSet().length, crops.length);
    });

    test('the asset is registered in pubspec, or it will not ship', () {
      expect(
        File('pubspec.yaml').readAsStringSync(),
        contains('assets/crops.json'),
      );
    });

    test('searches across every language', () {
      const registry = CropRegistry([
        Crop(id: 'wheat', en: 'Wheat', hi: 'गेहूँ', pt: 'Trigo'),
        Crop(id: 'rice', en: 'Rice', hi: 'चावल', pt: 'Arroz'),
      ]);
      expect(registry.search('whe').single.id, 'wheat');
      expect(registry.search('गेहूँ').single.id, 'wheat');
      expect(registry.search('Arroz').single.id, 'rice');
      expect(registry.search('zzz'), isEmpty);
    });

    test('an unlisted crop becomes a free-text entry, never a failure', () {
      final crop = Crop.other('Ragi from my village');
      expect(crop.id, 'other');
      expect(crop.isOther, isTrue);
      expect(crop.label('hi'), 'Ragi from my village');
    });

    test('labels fall back to English when a translation is missing', () {
      const crop = Crop(id: 'x', en: 'Quinoa');
      expect(crop.label('hi'), 'Quinoa');
    });
  });
}

void drawingTests() {
  group('S1 boundary drawing', () {
    testWidgets('offers both capture modes', (tester) async {
      await tester.pumpOnboarding();
      expect(find.text('Drop a pin'), findsOneWidget);
      expect(find.text('Draw boundary'), findsOneWidget);
      expect(find.text('Tap the map to move your field'), findsOneWidget);
    });

    testWidgets('switching to draw mode changes the instruction and disables '
        'confirm until enough corners exist', (tester) async {
      await tester.pumpOnboarding();
      await tester.tap(find.text('Draw boundary'));
      await tester.pumpAndSettle();

      expect(find.text('Tap each corner of your field'), findsOneWidget);
      expect(find.text('Tap at least 3 corners'), findsOneWidget);

      final button = tester.widget<FilledButton>(find.byType(FilledButton));
      expect(button.onPressed, isNull, reason: 'no corners placed yet');
    });

    testWidgets('three taps make a usable boundary with a real area',
        (tester) async {
      await tester.pumpOnboarding();
      await tester.tap(find.text('Draw boundary'));
      await tester.pumpAndSettle();

      await tester.tapMap(0.25, 0.25);
      expect(find.text('1 corner'), findsOneWidget);

      await tester.tapMap(0.75, 0.25);
      expect(find.text('2 corners'), findsOneWidget);

      await tester.tapMap(0.75, 0.75);
      expect(find.textContaining('3 corners'), findsOneWidget);
      // Area only appears once the ring closes.
      expect(find.textContaining('ha'), findsWidgets);

      expect(find.text('Confirm field'), findsOneWidget);
      final button = tester.widget<FilledButton>(find.byType(FilledButton));
      expect(button.onPressed, isNotNull);
    });

    testWidgets('a crossed boundary blocks confirm and says why',
        (tester) async {
      await tester.pumpOnboarding();
      await tester.tap(find.text('Draw boundary'));
      await tester.pumpAndSettle();

      // Tap the corners in bow-tie order, so edge 2 crosses edge 0.
      await tester.tapMap(0.25, 0.25);
      await tester.tapMap(0.75, 0.25);
      await tester.tapMap(0.25, 0.75);
      await tester.tapMap(0.75, 0.75);

      expect(find.text('Lines cross — undo and redraw'), findsOneWidget);
      final crossed = tester.widget<FilledButton>(find.byType(FilledButton));
      expect(crossed.onPressed, isNull);

      // Undoing the offending corner makes it usable again.
      await tester.tap(find.text('Undo'));
      await tester.pumpAndSettle();

      expect(find.text('Confirm field'), findsOneWidget);
      final fixed = tester.widget<FilledButton>(find.byType(FilledButton));
      expect(fixed.onPressed, isNotNull);
    });

    testWidgets('undo removes the last corner', (tester) async {
      await tester.pumpOnboarding();
      await tester.tap(find.text('Draw boundary'));
      await tester.pumpAndSettle();

      await tester.tapMap(0.25, 0.25);
      await tester.tapMap(0.75, 0.25);
      expect(find.text('2 corners'), findsOneWidget);

      await tester.tap(find.text('Undo'));
      await tester.pumpAndSettle();
      expect(find.text('1 corner'), findsOneWidget);
    });

    testWidgets('clear empties the draft', (tester) async {
      await tester.pumpOnboarding();
      await tester.tap(find.text('Draw boundary'));
      await tester.pumpAndSettle();

      await tester.tapMap(0.25, 0.25);
      await tester.tapMap(0.75, 0.25);
      await tester.tap(find.text('Clear'));
      await tester.pumpAndSettle();

      expect(find.text('0 corners'), findsOneWidget);
      expect(find.text('Tap at least 3 corners'), findsOneWidget);
    });

    testWidgets('going back to pin mode discards the draft', (tester) async {
      await tester.pumpOnboarding();
      await tester.tap(find.text('Draw boundary'));
      await tester.pumpAndSettle();
      await tester.tapMap(0.25, 0.25);

      await tester.tap(find.text('Drop a pin'));
      await tester.pumpAndSettle();

      expect(find.text('Tap the map to move your field'), findsOneWidget);
      expect(find.textContaining('1.50 ha'), findsWidgets);
    });
  });
}
