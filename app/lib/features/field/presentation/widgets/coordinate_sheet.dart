/// Typing coordinates instead of hunting for the field on a map.
///
/// Many farmers already know their coordinates — off a survey sheet, a previous
/// scheme registration, or a phone someone handed them. Panning a satellite map
/// to find a plot you can already name is the slower path, so this offers the
/// faster one.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../domain/coordinates.dart';

/// Ask for a latitude/longitude. Returns null if the farmer backs out.
Future<({double lat, double lng})?> showCoordinateSheet(
  BuildContext context, {
  required double initialLat,
  required double initialLng,
}) {
  return showModalBottomSheet<({double lat, double lng})>(
    context: context,
    isScrollControlled: true,
    builder: (context) => Padding(
      padding: EdgeInsets.only(
        bottom: MediaQuery.of(context).viewInsets.bottom,
      ),
      child: _CoordinateSheet(lat: initialLat, lng: initialLng),
    ),
  );
}

class _CoordinateSheet extends StatefulWidget {
  const _CoordinateSheet({required this.lat, required this.lng});

  final double lat;
  final double lng;

  @override
  State<_CoordinateSheet> createState() => _CoordinateSheetState();
}

class _CoordinateSheetState extends State<_CoordinateSheet> {
  late final TextEditingController _lat =
      TextEditingController(text: widget.lat.toStringAsFixed(5));
  late final TextEditingController _lng =
      TextEditingController(text: widget.lng.toStringAsFixed(5));

  String? _error;

  @override
  void dispose() {
    _lat.dispose();
    _lng.dispose();
    super.dispose();
  }

  /// Pasting a whole pair into the latitude box fills both, because that is
  /// what someone holding "29.61, 76.11" on a clipboard will actually do.
  void _onLatChanged(String text) {
    if (!text.contains(RegExp(r'[,\s]'))) return;
    final parsed = parseLatLng(text);
    if (!parsed.isValid) return;
    _lat.text = parsed.value!.lat.toStringAsFixed(5);
    _lng.text = parsed.value!.lng.toStringAsFixed(5);
    setState(() => _error = null);
  }

  void _submit() {
    final parsed = parseLatLngPair(_lat.text, _lng.text);
    if (!parsed.isValid) {
      setState(() => _error = parsed.error);
      return;
    }
    Navigator.of(context).pop(parsed.value);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 28),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Enter coordinates', style: theme.textTheme.titleLarge),
          const SizedBox(height: 4),
          Text(
            'Decimal or degrees — 29.61, 76.11 or 29°36\'36"N 76°06\'36"E.',
            style: theme.textTheme.bodySmall
                ?.copyWith(color: theme.colorScheme.outline),
          ),
          const SizedBox(height: 16),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: TextField(
                  controller: _lat,
                  autofocus: true,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                    signed: true,
                  ),
                  inputFormatters: [
                    FilteringTextInputFormatter.deny(RegExp(r'[^\d\-.,\s°′\x27"NSEWnsew]')),
                  ],
                  decoration: const InputDecoration(
                    labelText: 'Latitude',
                    border: OutlineInputBorder(),
                    hintText: '29.61',
                  ),
                  onChanged: _onLatChanged,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: TextField(
                  controller: _lng,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                    signed: true,
                  ),
                  decoration: const InputDecoration(
                    labelText: 'Longitude',
                    border: OutlineInputBorder(),
                    hintText: '76.11',
                  ),
                  onSubmitted: (_) => _submit(),
                ),
              ),
            ],
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Row(
              children: [
                Icon(Icons.error_outline,
                    size: 18, color: theme.colorScheme.error),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _error!,
                    style: TextStyle(color: theme.colorScheme.error),
                  ),
                ),
              ],
            ),
          ],
          const SizedBox(height: 20),
          Row(
            children: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('Cancel'),
              ),
              const Spacer(),
              FilledButton(
                onPressed: _submit,
                child: const Text('Go to this field'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
