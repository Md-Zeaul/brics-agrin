/// The advisory card on S2 — the first thing a farmer reads.
///
/// Three states, and the third is the one worth designing for. Advice built
/// entirely on district averages is still reasonable advice, but it is not a
/// finding about *this* field, and a card that presents both the same way is
/// the quiet dishonesty this whole module exists to avoid.
library;

import 'package:flutter/material.dart';

import '../../../core/l10n/language_scope.dart';
import '../data/advisory_repository.dart';
import '../domain/advisory.dart';

class AdvisoryCard extends StatelessWidget {
  const AdvisoryCard({super.key, required this.result, this.loading = false});

  /// Null when M1 has neither answered nor left anything cached.
  final AdvisoryResult? result;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final t = LanguageScope.stringsOf(context);

    if (loading && result == null) {
      return _Shell(
        accent: theme.colorScheme.surfaceContainerHighest,
        child: Row(
          children: [
            const SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
            const SizedBox(width: 12),
            Text(t('advisory.loading'), style: theme.textTheme.bodyMedium),
          ],
        ),
      );
    }

    if (result == null) {
      return _Shell(
        accent: theme.colorScheme.surfaceContainerHighest,
        child: Text(t('advisory.none'), style: theme.textTheme.bodyMedium),
      );
    }

    final advisory = result!.advisory;
    final accent = switch (advisory.urgency) {
      Urgency.urgent => theme.colorScheme.error,
      Urgency.advisory => theme.colorScheme.primary,
      Urgency.routine => theme.colorScheme.outline,
    };

    return _Shell(
      accent: accent,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                t('home.today'),
                style: theme.textTheme.labelSmall?.copyWith(
                  color: accent,
                  letterSpacing: 1.2,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const Spacer(),
              if (result!.fromCache)
                Tooltip(
                  message: result!.warning ?? t('advisory.saved'),
                  child: Icon(Icons.history,
                      size: 16, color: theme.colorScheme.outline),
                ),
            ],
          ),
          const SizedBox(height: 8),

          Text(advisory.headline, style: theme.textTheme.titleMedium),
          const SizedBox(height: 12),

          for (final action in advisory.actions)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.arrow_right, size: 20, color: accent),
                  Expanded(
                    child: Text(
                      action,
                      style: theme.textTheme.bodyLarge
                          ?.copyWith(fontWeight: FontWeight.w500),
                    ),
                  ),
                ],
              ),
            ),

          if (advisory.reason.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              advisory.reason,
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
          ],

          // The honesty line. Shown only when it is true, so it means
          // something when it appears.
          if (!advisory.restsOnMeasurements &&
              !advisory.isInsufficientData) ...[
            const SizedBox(height: 12),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.info_outline,
                    size: 15, color: theme.colorScheme.outline),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    t('advisory.fromDefaults'),
                    style: theme.textTheme.labelSmall
                        ?.copyWith(color: theme.colorScheme.outline),
                  ),
                ),
              ],
            ),
          ],

          if (result!.origin == AdvisoryOrigin.restored) ...[
            const SizedBox(height: 10),
            Text(
              t('advisory.saved'),
              style: theme.textTheme.labelSmall
                  ?.copyWith(color: theme.colorScheme.outline),
            ),
          ],
        ],
      ),
    );
  }
}

/// The card body: a left rule in the urgency colour, so the three levels are
/// distinguishable at arm's length without relying on reading the words.
///
/// The rule is a border rather than a stretched sibling. A Row with
/// `CrossAxisAlignment.stretch` inside a scroll view is handed an unbounded
/// height, and a fixed-width coloured box then tries to be infinitely tall.
class _Shell extends StatelessWidget {
  const _Shell({required this.accent, required this.child});

  final Color accent;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      clipBehavior: Clip.antiAlias,
      child: Container(
        decoration: BoxDecoration(
          border: Border(left: BorderSide(color: accent, width: 4)),
        ),
        padding: const EdgeInsets.all(16),
        child: child,
      ),
    );
  }
}
