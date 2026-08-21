/// A screen that exists so the demo path is walkable before its module is.
///
/// The Build Brief's instruction is to build the spine ugly first: all eight
/// steps of the happy path should navigate end-to-end on day one, even where
/// the content behind a step is still a promise. Each stub carries the brief's
/// own spec for that screen, so whoever replaces it does not have to go back to
/// the document to remember what it owes.
library;

import 'package:flutter/material.dart';

import 'l10n/language_scope.dart';

class ModuleStub extends StatelessWidget {
  const ModuleStub({
    super.key,
    required this.screenId,
    required this.titleKey,
    required this.module,
    required this.owner,
    required this.purpose,
    required this.elements,
    this.actions = const [],
  });

  /// S3, S7 — the brief's own numbering.
  final String screenId;

  /// Key into [AppStrings], so the stub flips language like everything else.
  final String titleKey;

  /// 'M2 Disease Diagnostic'.
  final String module;

  /// GitHub handle of whoever owns this module. Named on the screen so a
  /// question about it has an obvious addressee.
  final String owner;

  final String purpose;

  /// What the brief says this screen must show.
  final List<String> elements;

  /// Onward navigation, live even while the screen is a stub — the point of
  /// the spine is that every step of the happy path is reachable today.
  final List<({String label, String route})> actions;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final t = LanguageScope.stringsOf(context);

    return Scaffold(
      appBar: AppBar(title: Text(t(titleKey))),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Row(
            children: [
              Chip(
                label: Text(screenId),
                visualDensity: VisualDensity.compact,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(module, style: theme.textTheme.titleMedium),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            '${t('common.notBuiltYet')} · @$owner',
            style: theme.textTheme.labelMedium
                ?.copyWith(color: theme.colorScheme.outline),
          ),
          const SizedBox(height: 20),
          Text(purpose, style: theme.textTheme.bodyLarge),
          const SizedBox(height: 20),
          Text('This screen owes', style: theme.textTheme.titleSmall),
          const SizedBox(height: 8),
          for (final element in elements)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('· '),
                  Expanded(child: Text(element)),
                ],
              ),
            ),
          if (actions.isNotEmpty) ...[
            const SizedBox(height: 24),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                for (final action in actions)
                  FilledButton.tonal(
                    onPressed: () =>
                        Navigator.of(context).pushNamed(action.route),
                    child: Text(action.label),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}
