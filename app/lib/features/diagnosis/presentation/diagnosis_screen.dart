/// S4 — Diagnosis result. M2, owned by @herambskanda.
library;

import 'package:flutter/material.dart';

import '../../../core/module_stub.dart';

class DiagnosisScreen extends StatelessWidget {
  const DiagnosisScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const ModuleStub(
      screenId: 'S4',
      titleKey: 'diagnosis.title',
      module: 'M2 Disease Diagnostic',
      owner: 'herambskanda',
      purpose: 'Name the disease, own the uncertainty, and prescribe bio '
          'treatment before chemical.',
      elements: [
        'Label and confidence — e.g. leaf rust, 87%',
        'Differential list: what else it could be, and was ruled out',
        'Treatment block, bio option first, chemical as the alternative',
        'Save writes a DiseaseScan, which is the live signal M5 aggregates',
        'Ask opens M1 with the diagnosis as context',
      ],
    );
  }
}
