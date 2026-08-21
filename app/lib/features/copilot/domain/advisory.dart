/// One day's advice for one field — what S2's card reads.
///
/// Mirrors the field profile's shape: camelCase JSON, a `sources` entry saying
/// how the advice was arrived at, and every claim traceable to a signal with a
/// status. The card can then answer "is that live?" for the advisory exactly as
/// it already does for the readings underneath it.
library;

import '../../field/domain/field_profile.dart' show Provenance, SignalStatus;

/// How loudly the card should present itself.
enum Urgency {
  routine,
  advisory,
  urgent;

  static Urgency parse(String? raw) => switch (raw) {
        'urgent' => Urgency.urgent,
        'advisory' => Urgency.advisory,
        _ => Urgency.routine,
      };
}

/// One signal the advice rests on, and how much it can be trusted.
class AdvisorySignal {
  const AdvisorySignal({required this.name, required this.status});

  final String name;
  final SignalStatus status;

  factory AdvisorySignal.fromJson(Map<String, dynamic> json) => AdvisorySignal(
        name: json['name'] as String? ?? 'unknown',
        status: SignalStatus.parse(json['status'] as String?),
      );

  Map<String, dynamic> toJson() => {'name': name, 'status': status.name};
}

class Advisory {
  const Advisory({
    required this.language,
    required this.headline,
    required this.actions,
    required this.reason,
    required this.urgency,
    required this.templateIds,
    required this.signalsUsed,
    required this.stage,
    required this.restsOnMeasurements,
    this.daysAfterSowing,
    this.generatedAt,
    this.sources = const {},
  });

  /// The language this text is in — not the one that was asked for, which may
  /// differ if a template had no entry for it.
  final String language;

  /// What is true right now.
  final String headline;

  /// One or two things to do about it, most urgent first.
  final List<String> actions;

  /// Why, in a sentence, including what we are unsure of.
  final String reason;

  final Urgency urgency;

  /// Which templates were chosen. The testable identity of this advisory —
  /// wording can be rewritten, these cannot drift.
  final List<String> templateIds;

  final List<AdvisorySignal> signalsUsed;

  /// `vegetative`, `unknown`, and so on.
  final String stage;

  /// False when every signal behind this advice was seeded or reported. The
  /// advice is still reasonable, but it is not a finding about *this* field
  /// and the card must not let it look like one.
  final bool restsOnMeasurements;

  final int? daysAfterSowing;
  final String? generatedAt;
  final Map<String, Provenance> sources;

  /// Who chose the templates — the rule set, or a model.
  Provenance? get chosenBy => sources['advisory'];

  bool get isInsufficientData =>
      templateIds.contains('advisory.insufficient_data');

  factory Advisory.fromJson(Map<String, dynamic> json) => Advisory(
        language: json['language'] as String? ?? 'en',
        headline: json['headline'] as String? ?? '',
        actions: ((json['actions'] as List?) ?? const [])
            .map((a) => a.toString())
            .toList(),
        reason: json['reason'] as String? ?? '',
        urgency: Urgency.parse(json['urgency'] as String?),
        templateIds: ((json['templateIds'] as List?) ?? const [])
            .map((t) => t.toString())
            .toList(),
        signalsUsed: ((json['signalsUsed'] as List?) ?? const [])
            .map((s) => AdvisorySignal.fromJson(
                (s as Map).cast<String, dynamic>()))
            .toList(),
        stage: json['stage'] as String? ?? 'unknown',
        restsOnMeasurements: json['restsOnMeasurements'] as bool? ?? false,
        daysAfterSowing: (json['daysAfterSowing'] as num?)?.toInt(),
        generatedAt: json['generatedAt'] as String?,
        sources: ((json['sources'] as Map?) ?? const {}).map(
          (key, value) => MapEntry(
            key.toString(),
            Provenance.fromJson((value as Map).cast<String, dynamic>()),
          ),
        ),
      );

  Map<String, dynamic> toJson() => {
        'language': language,
        'headline': headline,
        'actions': actions,
        'reason': reason,
        'urgency': urgency.name,
        'templateIds': templateIds,
        'signalsUsed': signalsUsed.map((s) => s.toJson()).toList(),
        'stage': stage,
        'restsOnMeasurements': restsOnMeasurements,
        'daysAfterSowing': daysAfterSowing,
        'generatedAt': generatedAt,
        'sources': sources.map((k, v) => MapEntry(k, v.toJson())),
      };
}
