/// The language toggle, for the corner of any screen that wants one.
///
/// Renders nothing outside a [LanguageScope] — widget tests pump single screens
/// without the app wrapper, and a control that cannot do anything is worse than
/// an absent one.
library;

import 'package:flutter/material.dart';

import 'app_language.dart';
import 'language_scope.dart';

class LanguageButton extends StatelessWidget {
  const LanguageButton({super.key});

  @override
  Widget build(BuildContext context) {
    final controller = LanguageScope.maybeOf(context);
    if (controller == null) return const SizedBox.shrink();

    final t = controller.strings;
    return PopupMenuButton<AppLanguage>(
      tooltip: t('nav.language'),
      initialValue: controller.language,
      onSelected: controller.switchTo,
      itemBuilder: (context) => [
        for (final language in AppLanguage.values)
          PopupMenuItem(
            value: language,
            child: Text(language.label),
          ),
      ],
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Text(
          controller.language.code.toUpperCase(),
          style: Theme.of(context).textTheme.labelLarge,
        ),
      ),
    );
  }
}
