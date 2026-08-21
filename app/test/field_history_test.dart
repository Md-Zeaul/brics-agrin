// What the farmer has already done to the field — S1's optional input, and the
// shape it has to reach M0 in.
//
// The interesting cases are all about *not* over-claiming: a date with no
// product, a product with no quantity, and a product whose quantity would be a
// fiction. Each has to reach the backend as exactly what it is.
import 'package:agrisetu/features/field/domain/field_history.dart';
import 'package:agrisetu/features/field/presentation/widgets/field_history_input.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Widget _host(FieldHistory initial) {
  return MaterialApp(
    home: Scaffold(
      body: StatefulBuilder(
        builder: (context, setState) {
          var history = initial;
          return ListView(
            children: [
              FieldHistoryInput(
                history: history,
                onChanged: (next) => setState(() => history = next),
              ),
            ],
          );
        },
      ),
    ),
  );
}

void main() {
  group('the log M0 receives', () {
    test('is empty when nothing was answered', () {
      expect(const FieldHistory().log, isEmpty);
      expect(const FieldHistory().lastIrrigationIso, isNull);
      expect(const FieldHistory().isEmpty, isTrue);
    });

    test('a date alone is a complete entry', () {
      // The lowest rung of the ladder, and a legitimate place to stop: it is
      // enough to hold the next dose back.
      final history = FieldHistory(fertilisedOn: DateTime(2026, 8, 12));
      expect(history.log, [
        {'date': '2026-08-12'}
      ]);
    });

    test('a product with no quantity carries the product and nothing more', () {
      final history = FieldHistory(
        fertilisedOn: DateTime(2026, 8, 12),
        product: 'dap',
      );
      expect(history.log.single, {'date': '2026-08-12', 'product': 'dap'});
    });

    test('a full answer carries the quantity too', () {
      final history = FieldHistory(
        fertilisedOn: DateTime(2026, 8, 12),
        product: 'urea',
        bagsPerAcre: 1.5,
      );
      expect(history.log.single, {
        'date': '2026-08-12',
        'product': 'urea',
        'bagsPerAcre': 1.5,
      });
    });

    test('manure never carries a quantity, whatever is in state', () {
      // It is spread by the trolley and its analysis depends on what the
      // animals ate. A number here would be a guess the backend would treat as
      // an analysis.
      final history = FieldHistory(
        fertilisedOn: DateTime(2026, 8, 12),
        product: 'fym',
        bagsPerAcre: 2,
      );
      expect(history.log.single.containsKey('bagsPerAcre'), isFalse);
    });

    test('an unremembered product never carries a quantity either', () {
      final history = FieldHistory(
        fertilisedOn: DateTime(2026, 8, 12),
        product: 'unknown',
        bagsPerAcre: 2,
      );
      expect(history.log.single.containsKey('bagsPerAcre'), isFalse);
    });

    test('a quantity with no date is not an entry at all', () {
      // An application with no date is not a weaker record of an application.
      const history = FieldHistory(product: 'urea', bagsPerAcre: 2);
      expect(history.log, isEmpty);
    });

    test('irrigation is carried as a plain ISO date', () {
      final history = FieldHistory(irrigatedOn: DateTime(2026, 8, 20));
      expect(history.lastIrrigationIso, '2026-08-20');
      expect(history.isEmpty, isFalse);
    });

    test('changing the product drops the old quantity', () {
      // Two bags of urea is 102 kg of nitrogen and two bags of DAP is 40. A
      // quantity left behind by a product change is the wrong number, silently.
      final history = FieldHistory(
        fertilisedOn: DateTime(2026, 8, 12),
        product: 'urea',
        bagsPerAcre: 2,
      ).copyWith(product: 'dap', bagsPerAcre: null);
      expect(history.bagsPerAcre, isNull);
    });

    test('clearing the date clears the whole entry', () {
      final history = FieldHistory(
        fertilisedOn: DateTime(2026, 8, 12),
        product: 'urea',
        bagsPerAcre: 2,
      ).copyWith(clearFertilised: true);
      expect(history.log, isEmpty);
      expect(history.product, isNull);
      expect(history.bagsPerAcre, isNull);
    });
  });

  group('the S1 control', () {
    testWidgets('stays collapsed and says what the silence means',
        (tester) async {
      await tester.pumpWidget(_host(const FieldHistory()));
      expect(find.text('We will assume nothing has been applied yet'),
          findsOneWidget);
      // Collapsed: the fields exist only once the farmer opens it.
      expect(find.text('Last fertilised'), findsNothing);
    });

    testWidgets('opens to a date field and no product question yet',
        (tester) async {
      await tester.pumpWidget(_host(const FieldHistory()));
      await tester.tap(find.text('Already fertilised or watered? (optional)'));
      await tester.pumpAndSettle();

      expect(find.text('Not yet applied'), findsOneWidget);
      expect(find.text('Not yet watered'), findsOneWidget);
      // Nothing to name a product for until there is a date.
      expect(find.text('What did you put on?'), findsNothing);
    });

    testWidgets('asks what and how much once a date is set', (tester) async {
      await tester
          .pumpWidget(_host(FieldHistory(fertilisedOn: DateTime(2026, 8, 12))));
      await tester.tap(find.text('Already fertilised or watered? (optional)'));
      await tester.pumpAndSettle();

      expect(find.text('What did you put on?'), findsOneWidget);
      expect(find.text('How much?'), findsOneWidget);
    });

    testWidgets('offers every product the backend knows', (tester) async {
      await tester
          .pumpWidget(_host(FieldHistory(fertilisedOn: DateTime(2026, 8, 12))));
      await tester.tap(find.text('Already fertilised or watered? (optional)'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('What did you put on?'));
      await tester.pumpAndSettle();

      for (final product in kFertiliserProducts) {
        expect(find.text(product.label), findsWidgets,
            reason: '${product.id} is missing from the picker');
      }
    });

    testWidgets('not remembering is offered as an answer, not a dead end',
        (tester) async {
      await tester
          .pumpWidget(_host(FieldHistory(fertilisedOn: DateTime(2026, 8, 12))));
      await tester.tap(find.text('Already fertilised or watered? (optional)'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('What did you put on?'));
      await tester.pumpAndSettle();
      expect(find.text("Don't remember"), findsWidgets);
    });

    testWidgets('the quantity field is disabled for what cannot be weighed',
        (tester) async {
      await tester.pumpWidget(_host(FieldHistory(
        fertilisedOn: DateTime(2026, 8, 12),
        product: 'fym',
      )));
      await tester.tap(find.text('Already fertilised or watered? (optional)'));
      await tester.pumpAndSettle();

      expect(find.text('not needed'), findsOneWidget);
      final field = tester.widget<DropdownButtonFormField<double>>(
        find.byType(DropdownButtonFormField<double>),
      );
      expect(field.onChanged, isNull, reason: 'should not accept a quantity');
    });

    testWidgets('the quantity field is live for a product with an analysis',
        (tester) async {
      await tester.pumpWidget(_host(FieldHistory(
        fertilisedOn: DateTime(2026, 8, 12),
        product: 'urea',
      )));
      await tester.tap(find.text('Already fertilised or watered? (optional)'));
      await tester.pumpAndSettle();

      expect(find.text('bags/acre'), findsOneWidget);
      final field = tester.widget<DropdownButtonFormField<double>>(
        find.byType(DropdownButtonFormField<double>),
      );
      expect(field.onChanged, isNotNull);
    });

    testWidgets('a filled answer is summarised without opening it',
        (tester) async {
      await tester.pumpWidget(_host(FieldHistory(
        fertilisedOn: DateTime(2026, 8, 12),
        product: 'dap',
        irrigatedOn: DateTime(2026, 8, 20),
      )));
      expect(find.text('DAP · Irrigation noted'), findsOneWidget);
    });
  });
}
