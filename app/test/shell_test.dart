// The app shell: language switching and the S1–S10 spine.
//
// These are the parts two people build against simultaneously, so they are the
// parts worth pinning down before either of them starts.
import 'package:agrisetu/core/l10n/app_language.dart';
import 'package:agrisetu/core/l10n/language_button.dart';
import 'package:agrisetu/core/l10n/language_scope.dart';
import 'package:agrisetu/core/l10n/strings.dart';
import 'package:agrisetu/core/routes.dart';
import 'package:agrisetu/features/field/data/field_repository.dart';
import 'package:agrisetu/features/field/domain/field_profile.dart';
import 'package:agrisetu/features/field/presentation/home_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

FieldProfile _profile() => FieldProfile(
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
      soil: const Soil(ph: 7.9, n: 1.33, cec: 12.8, moisture: 0.48),
      healthChip: HealthChip.green,
      sources: const {},
    );

Widget _app({LanguageController? controller}) {
  final home = HomeScreen(
    result: FieldProfileResult(profile: _profile(), origin: ProfileOrigin.live),
    repository: FieldRepository(),
  );
  final app = MaterialApp(routes: Routes.table, home: home);
  if (controller == null) return app;
  return LanguageScope(controller: controller, child: app);
}

void main() {
  group('languages', () {
    test('an unknown code falls back to English rather than throwing', () {
      expect(AppLanguage.fromCode('zz'), AppLanguage.english);
      expect(AppLanguage.fromCode(null), AppLanguage.english);
      expect(AppLanguage.fromCode('pt'), AppLanguage.portuguese);
    });

    test('every language carries a region for the TTS voice', () {
      // A pt-PT voice reading a Brazilian advisory is the wrong accent for the
      // audience S10 exists to convince.
      expect(AppLanguage.portuguese.voiceLocale, 'pt-BR');
      expect(AppLanguage.hindi.voiceLocale, 'hi-IN');
    });

    test('a missing translation degrades to English, not to blank', () {
      const hindi = AppStrings(AppLanguage.hindi);
      expect(hindi('nav.farmer'), isNot('nav.farmer'));
      // 'app.title' exists everywhere; an unknown key is the interesting case.
      expect(hindi('planner.notAKey'), 'planner.notAKey');
    });

    test('switching notifies once, and only on a real change', () {
      final controller = LanguageController(AppLanguage.hindi);
      var notifications = 0;
      controller.addListener(() => notifications++);

      controller.switchTo(AppLanguage.hindi);
      expect(notifications, 0, reason: 'no change, no repaint');

      controller.switchTo(AppLanguage.portuguese);
      expect(notifications, 1);
      expect(controller.strings('nav.commandCenter'), 'Centro de Comando');
    });
  });

  group('language toggle', () {
    testWidgets('is absent outside a scope rather than broken inside one',
        (tester) async {
      await tester.pumpWidget(
        const MaterialApp(home: Scaffold(body: LanguageButton())),
      );
      expect(find.byType(PopupMenuButton<AppLanguage>), findsNothing);
    });

    testWidgets('flips the whole tree, which is S10\'s demo beat',
        (tester) async {
      final controller = LanguageController(AppLanguage.english);
      await tester.pumpWidget(_app(controller: controller));

      expect(find.text('Namaste, Rekha'), findsOneWidget);
      expect(find.text('Command Center'), findsOneWidget);

      controller.switchTo(AppLanguage.portuguese);
      await tester.pumpAndSettle();

      expect(find.text('Olá, Rekha'), findsOneWidget);
      expect(find.text('Centro de Comando'), findsOneWidget);
    });
  });

  group('the S1–S10 spine', () {
    testWidgets('every named route resolves to a screen', (tester) async {
      // Registration is the failure mode: a screen can exist, compile, and
      // still be unreachable because nobody added it to the table.
      const expected = [
        Routes.scan,
        Routes.diagnosis,
        Routes.planner,
        Routes.whatIf,
        Routes.commandCenter,
        Routes.regionDetail,
        Routes.scenario,
        Routes.network,
      ];
      expect(Routes.table.keys, containsAll(expected));
      expect(Routes.table.length, expected.length);
    });

    testWidgets('S2 reaches the scan screen', (tester) async {
      await tester.pumpWidget(_app());
      await tester.tap(find.text('Scan crop'));
      await tester.pumpAndSettle();
      expect(find.text('S3'), findsOneWidget);
    });

    testWidgets('S2 reaches the planner', (tester) async {
      await tester.pumpWidget(_app());
      await tester.tap(find.text('Plan season'));
      await tester.pumpAndSettle();
      expect(find.text('S5'), findsOneWidget);
    });

    testWidgets('the side switch reaches the Command Center', (tester) async {
      await tester.pumpWidget(_app());
      await tester.tap(find.widgetWithText(TextButton, 'Command Center'));
      await tester.pumpAndSettle();
      expect(find.text('S7'), findsOneWidget);
    });

    testWidgets('the Command Center reaches all three of its children',
        (tester) async {
      await tester.pumpWidget(_app());
      await tester.tap(find.widgetWithText(TextButton, 'Command Center'));
      await tester.pumpAndSettle();

      // Pop back to S7 between hops rather than re-pumping: pumpWidget reuses
      // the element tree, so a second pump would leave the navigator wherever
      // the previous hop left it.
      for (final (label, screen) in [
        ('Region →', 'S8'),
        ('Food security →', 'S9'),
        ('Network →', 'S10'),
      ]) {
        await tester.tap(find.text(label));
        await tester.pumpAndSettle();
        expect(find.text(screen), findsOneWidget, reason: 'via $label');

        await tester.pageBack();
        await tester.pumpAndSettle();
        expect(find.text('S7'), findsOneWidget);
      }
    });

    testWidgets('a stub names the module and where its scope is written',
        (tester) async {
      // The point of the stub is that opening it tells you what is missing and
      // where the spec for it lives, rather than only that something is.
      await tester.pumpWidget(_app());
      await tester.tap(find.text('Scan crop'));
      await tester.pumpAndSettle();
      expect(find.text('M2 Disease Diagnostic'), findsOneWidget);
      expect(find.textContaining('issue #3'), findsOneWidget);
    });
  });
}
