/// S3 — Crop scan. M2, owned by @herambskanda.
library;

import 'package:flutter/material.dart';

import '../../../core/module_stub.dart';
import '../../../core/routes.dart';

class ScanScreen extends StatelessWidget {
  const ScanScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const ModuleStub(
      screenId: 'S3',
      titleKey: 'scan.title',
      module: 'M2 Disease Diagnostic',
      owner: 'herambskanda',
      purpose: 'Photograph a leaf and get a diagnosis that still works with no '
          'network, because demo-day wifi cannot be trusted.',
      elements: [
        'Live camera viewfinder with a shutter control',
        'Gallery pick as well as capture, so the demo can use a known image',
        'Capture runs the on-device TFLite model, then opens S4',
      ],
      actions: [(label: 'Diagnosis →', route: Routes.diagnosis)],
    );
  }
}
