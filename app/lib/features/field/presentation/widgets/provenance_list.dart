/// Per-signal provenance — the answer to "is that number live?".
///
/// Worth showing on stage: the Build Brief tiers modules by data fidelity, and
/// a judge asking which parts are real should be able to see it, not be told.
library;

import 'package:flutter/material.dart';

import '../../domain/field_profile.dart';

class ProvenanceList extends StatelessWidget {
  const ProvenanceList({super.key, required this.sources});

  final Map<String, Provenance> sources;

  @override
  Widget build(BuildContext context) {
    if (sources.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: sources.entries.map((entry) {
        final colour = _statusColour(entry.value.status);
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                margin: const EdgeInsets.only(top: 5),
                width: 8,
                height: 8,
                decoration:
                    BoxDecoration(color: colour, shape: BoxShape.circle),
              ),
              const SizedBox(width: 10),
              SizedBox(
                width: 92,
                child: Text(
                  entry.key,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              ),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${entry.value.status.label} · ${entry.value.source}',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    if (entry.value.note != null)
                      Text(
                        entry.value.note!,
                        style:
                            Theme.of(context).textTheme.bodySmall?.copyWith(
                                  color: Theme.of(context)
                                      .colorScheme
                                      .onSurfaceVariant,
                                  fontStyle: FontStyle.italic,
                                ),
                      ),
                  ],
                ),
              ),
            ],
          ),
        );
      }).toList(),
    );
  }

  Color _statusColour(SignalStatus status) => switch (status) {
        SignalStatus.live => const Color(0xFF2E7D32),
        // A farmer's own soil card outranks any modelled or averaged value.
        SignalStatus.reported => const Color(0xFF00796B),
        SignalStatus.cached => const Color(0xFF1565C0),
        SignalStatus.seeded => const Color(0xFFF9A825),
        SignalStatus.unavailable => const Color(0xFF9E9E9E),
      };
}
