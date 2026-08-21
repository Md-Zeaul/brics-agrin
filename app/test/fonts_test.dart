// The Hindi demo has to survive with no network.
//
// Roboto has no Devanagari. On the web Flutter hides that by fetching a Noto
// fallback from Google's CDN on first use, so Hindi looks fine in every
// rehearsal with wifi and renders as empty boxes the moment there isn't any —
// which is precisely the condition the offline story invites a judge to test.
// These tests pin the three things that keep the glyphs in the bundle.
import 'dart:io';

import 'package:agrisetu/core/l10n/app_language.dart';
import 'package:agrisetu/core/l10n/strings.dart';
import 'package:agrisetu/core/theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('the Devanagari font is bundled', () {
    test('pubspec declares the family the theme falls back to', () {
      final pubspec = File('pubspec.yaml').readAsStringSync();
      expect(
        pubspec,
        contains('family: ${AppTheme.devanagari}'),
        reason: 'the theme names a family pubspec never declares, so Flutter '
            'would silently ignore the fallback',
      );
    });

    test('every declared font file exists and is really a font', () {
      final pubspec = File('pubspec.yaml').readAsStringSync();
      final assets = RegExp(r'asset:\s*(assets/fonts/\S+)')
          .allMatches(pubspec)
          .map((m) => m.group(1)!)
          .toList();

      expect(assets, isNotEmpty, reason: 'no font assets declared at all');

      for (final path in assets) {
        final file = File(path);
        expect(file.existsSync(), isTrue, reason: '$path is declared but absent');

        // TrueType outlines start 0x00010000; a stray HTML error page or an
        // LFS pointer committed by mistake would not.
        final header = file.readAsBytesSync().take(4).toList();
        expect(header, [0x00, 0x01, 0x00, 0x00], reason: '$path is not a TTF');

        expect(file.lengthSync(), greaterThan(100 * 1024),
            reason: '$path is too small to hold the Devanagari block');
      }
    });

    test('the licence travels with the font, as OFL-1.1 requires', () {
      final licence = File('assets/fonts/OFL.txt');
      expect(licence.existsSync(), isTrue);
      expect(licence.readAsStringSync(), contains('SIL Open Font License'));
    });
  });

  group('the theme reaches for it', () {
    test('the fallback is declared', () {
      expect(AppTheme.light().textTheme.bodyMedium?.fontFamilyFallback,
          contains(AppTheme.devanagari));
    });

    testWidgets('Hindi text resolves to a style that can render it',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light(),
          home: const Scaffold(body: Text('नमस्ते, रेखा')),
        ),
      );

      final style = tester.widget<RichText>(find.byType(RichText)).text.style;
      expect(style?.fontFamilyFallback, contains(AppTheme.devanagari));
    });
  });

  test('every Hindi string is Devanagari, not a forgotten English copy', () {
    // A section left untranslated is invisible in English-language testing:
    // the fallback quietly serves the English text and nothing looks wrong.
    const hindi = AppStrings(AppLanguage.hindi);
    const keys = [
      'app.title',
      'nav.farmer',
      'nav.commandCenter',
      'home.greeting',
      'scan.title',
      'planner.title',
      'command.title',
      'network.title',
    ];

    for (final key in keys) {
      expect(hindi.isTranslated(key), isTrue, reason: '$key has no Hindi entry');
      expect(
        hindi(key).runes.any((r) => r >= 0x0900 && r <= 0x097F),
        isTrue,
        reason: '$key is present but holds no Devanagari — likely copied from '
            'the English map',
      );
    }
  });
}
