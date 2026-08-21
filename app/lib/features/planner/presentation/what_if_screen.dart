/// S6 — What-if sliders. M8.
library;

import 'package:flutter/material.dart';

import '../../../core/module_stub.dart';

class WhatIfScreen extends StatelessWidget {
  const WhatIfScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const ModuleStub(
      screenId: 'S6',
      titleKey: 'whatIf.title',
      module: 'M8 Farm Digital Twin',
      issue: 9,
      purpose: 'Stress-test the recommendation live, so the advice survives a '
          'question rather than a demo script.',
      elements: [
        'Rainfall and fertiliser sliders',
        'Moving a slider re-runs M3 scoring on the perturbed inputs',
        'The pick and its yield update in place — no reload, no spinner',
      ],
    );
  }
}
