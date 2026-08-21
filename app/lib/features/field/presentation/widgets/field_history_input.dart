/// S1's "what have you already done to this field" input.
///
/// Collapsed by default, like the soil card: the Build Brief's S1 must stay
/// walkable in seconds, and a farmer who skips this gets exactly the advisory
/// they got before it existed. Opening it is what buys the sharper one.
library;

import 'package:flutter/material.dart';

import '../../domain/field_history.dart';

class FieldHistoryInput extends StatelessWidget {
  const FieldHistoryInput({
    super.key,
    required this.history,
    required this.onChanged,
  });

  final FieldHistory history;
  final ValueChanged<FieldHistory> onChanged;

  String _summary() {
    final parts = <String>[];
    if (history.fertilisedOn != null) {
      final product = kFertiliserProducts
          .where((p) => p.id == history.product)
          .map((p) => p.label);
      parts.add(product.isEmpty ? 'Fertiliser noted' : product.first);
    }
    if (history.irrigatedOn != null) parts.add('Irrigation noted');
    return parts.isEmpty
        ? 'We will assume nothing has been applied yet'
        : parts.join(' · ');
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final quantifiable = history.product != null &&
        !kUnquantifiableProducts.contains(history.product);

    return ExpansionTile(
      tilePadding: EdgeInsets.zero,
      childrenPadding: const EdgeInsets.only(bottom: 8),
      title: const Text('Already fertilised or watered? (optional)'),
      subtitle: Text(_summary(), style: theme.textTheme.bodySmall),
      children: [
        _DateRow(
          label: 'Last fertilised',
          value: history.fertilisedOn,
          emptyText: 'Not yet applied',
          onPicked: (date) => onChanged(history.copyWith(fertilisedOn: date)),
          onCleared: () => onChanged(history.copyWith(clearFertilised: true)),
        ),
        if (history.fertilisedOn != null) ...[
          const SizedBox(height: 12),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                flex: 3,
                child: DropdownButtonFormField<String>(
                  initialValue: history.product,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'What did you put on?',
                    border: OutlineInputBorder(),
                  ),
                  items: [
                    for (final product in kFertiliserProducts)
                      DropdownMenuItem(
                        value: product.id,
                        child: Text(product.label, overflow: TextOverflow.ellipsis),
                      ),
                  ],
                  onChanged: (id) =>
                      onChanged(history.copyWith(product: id, bagsPerAcre: null)),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                flex: 2,
                child: DropdownButtonFormField<double>(
                  // Disabled rather than merely ignored for manure and for a
                  // product nobody remembers: neither has an analysis, so a
                  // quantity against them is a number that can only mislead.
                  initialValue: quantifiable ? history.bagsPerAcre : null,
                  isExpanded: true,
                  decoration: InputDecoration(
                    labelText: 'How much?',
                    border: const OutlineInputBorder(),
                    helperText: quantifiable ? 'bags/acre' : 'not needed',
                  ),
                  items: [
                    for (final bags in kBagOptions)
                      DropdownMenuItem(
                        value: bags,
                        child: Text(bags == bags.roundToDouble()
                            ? '${bags.toInt()}'
                            : '$bags'),
                      ),
                  ],
                  onChanged: quantifiable
                      ? (bags) => onChanged(history.copyWith(bagsPerAcre: bags))
                      : null,
                ),
              ),
            ],
          ),
        ],
        const SizedBox(height: 12),
        _DateRow(
          label: 'Last watered',
          value: history.irrigatedOn,
          emptyText: 'Not yet watered',
          onPicked: (date) => onChanged(history.copyWith(irrigatedOn: date)),
          onCleared: () => onChanged(history.copyWith(clearIrrigated: true)),
        ),
      ],
    );
  }
}

class _DateRow extends StatelessWidget {
  const _DateRow({
    required this.label,
    required this.value,
    required this.emptyText,
    required this.onPicked,
    required this.onCleared,
  });

  final String label;
  final DateTime? value;
  final String emptyText;
  final ValueChanged<DateTime> onPicked;
  final VoidCallback onCleared;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final now = DateTime.now();

    return InkWell(
      onTap: () async {
        final picked = await showDatePicker(
          context: context,
          initialDate: value ?? now,
          firstDate: DateTime(now.year - 1),
          // A future date is not an application that happened, and the backend
          // discards one. Refusing it here means the farmer finds that out
          // while the calendar is still open.
          lastDate: now,
        );
        if (picked != null) onPicked(picked);
      },
      child: InputDecorator(
        decoration: InputDecoration(
          labelText: label,
          border: const OutlineInputBorder(),
          suffixIcon: value == null
              ? null
              : IconButton(
                  icon: const Icon(Icons.clear, size: 18),
                  tooltip: 'Clear',
                  onPressed: onCleared,
                ),
        ),
        child: Text(
          value == null
              ? emptyText
              : '${value!.day}/${value!.month}/${value!.year}',
          style: value == null
              ? TextStyle(color: theme.colorScheme.outline)
              : null,
        ),
      ),
    );
  }
}
