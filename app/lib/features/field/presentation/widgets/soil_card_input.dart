/// Optional phosphorus and potassium input.
///
/// Neither is modelled by SoilGrids and neither can be sensed from orbit, so
/// without this the only source is a district average. Every Indian farmer has
/// a Soil Health Card carrying exactly these two numbers, and a reading from
/// their own field beats any regional mean — so it is offered, collapsed by
/// default to protect the "almost no typing" path.
library;

import 'package:flutter/material.dart';

class SoilCardInput extends StatelessWidget {
  const SoilCardInput({
    super.key,
    required this.phosphorus,
    required this.potassium,
    required this.onChanged,
  });

  final double? phosphorus;
  final double? potassium;
  final void Function(double? p, double? k) onChanged;

  @override
  Widget build(BuildContext context) {
    return ExpansionTile(
      tilePadding: EdgeInsets.zero,
      childrenPadding: const EdgeInsets.only(bottom: 8),
      title: const Text('Soil test values (optional)'),
      subtitle: Text(
        phosphorus == null && potassium == null
            ? 'Otherwise we use your district average'
            : 'Using your own soil card',
        style: Theme.of(context).textTheme.bodySmall,
      ),
      children: [
        Row(
          children: [
            Expanded(
              child: _NumberField(
                label: 'Phosphorus',
                suffix: 'kg/ha',
                value: phosphorus,
                onChanged: (p) => onChanged(p, potassium),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _NumberField(
                label: 'Potassium',
                suffix: 'kg/ha',
                value: potassium,
                onChanged: (k) => onChanged(phosphorus, k),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _NumberField extends StatelessWidget {
  const _NumberField({
    required this.label,
    required this.suffix,
    required this.value,
    required this.onChanged,
  });

  final String label;
  final String suffix;
  final double? value;
  final ValueChanged<double?> onChanged;

  @override
  Widget build(BuildContext context) {
    return TextFormField(
      initialValue: value?.toString(),
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
      decoration: InputDecoration(
        labelText: label,
        suffixText: suffix,
        border: const OutlineInputBorder(),
      ),
      onChanged: (text) => onChanged(double.tryParse(text.trim())),
    );
  }
}
