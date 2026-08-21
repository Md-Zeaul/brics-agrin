/// S9 — National scenario. M6, owned by @herambskanda.
library;

import 'package:flutter/material.dart';

import '../../../core/module_stub.dart';

class ScenarioScreen extends StatelessWidget {
  const ScenarioScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const ModuleStub(
      screenId: 'S9',
      titleKey: 'scenario.title',
      module: 'M6 Economic Engine',
      owner: 'herambskanda',
      purpose: 'Turn a shortfall into a decision with a price on it.',
      elements: [
        'The gap, as a percentage — the brief\'s example is 8% wheat',
        'Option cards: grow more, import, substitute',
        'Each option priced in cost, food security and CO2',
        'Selecting an option highlights its consequences',
      ],
    );
  }
}
