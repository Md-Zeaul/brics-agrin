/// The crop registry behind S1's picker.
///
/// Deliberately not exhaustive. The picker accepts free text, so a farmer
/// growing something unlisted is never blocked — those arrive as [Crop.other]
/// carrying the farmer's own label. Downstream modules key on [id], and should
/// treat an unknown id as "no crop-specific model available" rather than an
/// error, which is exactly the honest position for a crop nobody has curated.
library;

import 'dart:convert';

import 'package:flutter/services.dart' show rootBundle;

class Crop {
  const Crop({
    required this.id,
    required this.en,
    this.hi,
    this.pt,
    this.category,
  });

  final String id;
  final String en;
  final String? hi;
  final String? pt;
  final String? category;

  /// A crop the farmer typed themselves.
  factory Crop.other(String label) => Crop(id: 'other', en: label);

  /// Shown before the registry has loaded, and if loading ever fails. The
  /// picker must never open blank — a farmer with no crop selected cannot
  /// finish onboarding.
  static const Crop fallbackDefault = Crop(
    id: 'wheat',
    en: 'Wheat',
    hi: 'गेहूँ',
    pt: 'Trigo',
    category: 'cereal',
  );

  bool get isOther => id == 'other';

  factory Crop.fromJson(Map<String, dynamic> json) => Crop(
        id: json['id'] as String,
        en: json['en'] as String,
        hi: json['hi'] as String?,
        pt: json['pt'] as String?,
        category: json['category'] as String?,
      );

  /// The name to show, in the farmer's language where one exists.
  String label(String language) => switch (language) {
        'hi' => hi ?? en,
        'pt' => pt ?? en,
        _ => en,
      };

  /// Matches against every language, so "गेहूँ" and "trigo" both find wheat.
  bool matches(String query) {
    final q = query.trim().toLowerCase();
    if (q.isEmpty) return true;
    return [en, hi, pt, id]
        .whereType<String>()
        .any((name) => name.toLowerCase().contains(q));
  }

  @override
  bool operator ==(Object other) =>
      other is Crop && other.id == id && other.en == en;

  @override
  int get hashCode => Object.hash(id, en);
}

class CropRegistry {
  const CropRegistry(this.crops);

  final List<Crop> crops;

  static const String _assetPath = 'assets/crops.json';

  static Future<CropRegistry> load() async {
    try {
      final raw = await rootBundle.loadString(_assetPath);
      final decoded = jsonDecode(raw) as Map<String, dynamic>;
      return CropRegistry(
        (decoded['crops'] as List)
            .map((c) => Crop.fromJson(c as Map<String, dynamic>))
            .toList(),
      );
    } catch (_) {
      // A missing registry must not block field capture.
      return const CropRegistry([]);
    }
  }

  List<Crop> search(String query) =>
      crops.where((crop) => crop.matches(query)).toList();

  Crop? byId(String id) {
    for (final crop in crops) {
      if (crop.id == id) return crop;
    }
    return null;
  }
}
