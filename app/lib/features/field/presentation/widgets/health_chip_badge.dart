/// The field-health chip from S2 — GREEN / YELLOW / RED at a glance.
library;

import 'package:flutter/material.dart';

import '../../domain/field_profile.dart';

class HealthChipBadge extends StatelessWidget {
  const HealthChipBadge({super.key, required this.chip, this.driver});

  final HealthChip chip;

  /// The binding signal, e.g. `canopy_stress` — shown so the colour is never
  /// unexplained.
  final String? driver;

  @override
  Widget build(BuildContext context) {
    final (colour, label) = switch (chip) {
      HealthChip.green => (const Color(0xFF2E7D32), 'Healthy'),
      HealthChip.yellow => (const Color(0xFFF9A825), 'Watch'),
      HealthChip.red => (const Color(0xFFC62828), 'Stressed'),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: colour.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: colour.withValues(alpha: 0.5)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 10,
            height: 10,
            decoration: BoxDecoration(color: colour, shape: BoxShape.circle),
          ),
          const SizedBox(width: 8),
          Text(
            label,
            style: TextStyle(color: colour, fontWeight: FontWeight.w600),
          ),
          if (driver != null) ...[
            const SizedBox(width: 6),
            Text(
              '· ${driver!.replaceAll('_', ' ')}',
              style: TextStyle(
                color: colour.withValues(alpha: 0.8),
                fontSize: 12,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
