/// S5 — Season planner. M3 + M4.
library;

import 'package:flutter/material.dart';

import '../../../core/module_stub.dart';
import '../../../core/routes.dart';

class PlannerScreen extends StatelessWidget {
  const PlannerScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const ModuleStub(
      screenId: 'S5',
      titleKey: 'planner.title',
      module: 'M3 Regenerative Advisor + M4 Seed Intelligence',
      issue: 4,
      purpose: 'Rank next season\'s crops on risk-adjusted return and soil, '
          'then name the seed variety to actually buy.',
      elements: [
        'Ranked crop table: yield, income, water, risk, soil (M3)',
        'The highlighted pick, with why it beat the runner-up',
        'Recommended seed variety from M4, called as a pure lookup',
        'One-line reason in the farmer\'s language (M1)',
      ],
      actions: [(label: 'Simulate →', route: Routes.whatIf)],
    );
  }
}
