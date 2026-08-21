/// S10 — BRICS network. M7, owned by @herambskanda.
///
/// Cross-border is 20% of the score and this screen carries almost all of it.
library;

import 'package:flutter/material.dart';

import '../../../core/module_stub.dart';

class NetworkScreen extends StatelessWidget {
  const NetworkScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const ModuleStub(
      screenId: 'S10',
      titleKey: 'network.title',
      module: 'M7 Federated Agri-DPI',
      owner: 'herambskanda',
      purpose: 'Prove the network is real: another nation\'s model makes this '
          'nation\'s predictions better, and no farm record crosses the border.',
      elements: [
        'Four node cards — India, Brazil, China, South Africa',
        'Import model animates an accuracy lift, e.g. 81% to 88%',
        'Switching to the Brazil node flips the whole UI to Portuguese',
        'State plainly that only models and metadata cross, never raw records',
      ],
    );
  }
}
