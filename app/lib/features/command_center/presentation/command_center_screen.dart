/// S7 — Command Center home. M5.
library;

import 'package:flutter/material.dart';

import '../../../core/module_stub.dart';
import '../../../core/routes.dart';

class CommandCenterScreen extends StatelessWidget {
  const CommandCenterScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const ModuleStub(
      screenId: 'S7',
      titleKey: 'command.title',
      module: 'M5 Nervous System',
      issue: 6,
      purpose: 'The planner\'s morning view: where the district is in trouble, '
          'at a glance.',
      elements: [
        'Choropleth of risk tiles — seeded, plus one genuinely live signal',
        'A red disease cluster and an orange drought band must both be visible',
        'The live signal is the saved DiseaseScan count from M2',
      ],
      actions: [
        (label: 'Region →', route: Routes.regionDetail),
        (label: 'Food security →', route: Routes.scenario),
        (label: 'Network →', route: Routes.network),
      ],
    );
  }
}
