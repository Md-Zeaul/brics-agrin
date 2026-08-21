/// S8 — Region risk detail. M5, owned by @herambskanda.
library;

import 'package:flutter/material.dart';

import '../../../core/module_stub.dart';

class RegionDetailScreen extends StatelessWidget {
  const RegionDetailScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const ModuleStub(
      screenId: 'S8',
      titleKey: 'region.title',
      module: 'M5 Nervous System',
      owner: 'herambskanda',
      purpose: 'Why this tile is red, and how many farms it covers.',
      elements: [
        'The region\'s risk drivers, ranked',
        'Count of affected farms',
      ],
    );
  }
}
