/// The M0 contract, mirrored from `backend/m0_field/contract.py`.
///
/// Keep the two in step: this is the substrate M1 advisory, M3 crop scoring and
/// M5 regional aggregation all read.
library;

/// How far to trust one signal on stage.
enum SignalStatus {
  live,
  cached,
  reported,
  seeded,
  unavailable;

  static SignalStatus parse(String? raw) => switch (raw) {
        'live' => SignalStatus.live,
        'cached' => SignalStatus.cached,
        'reported' => SignalStatus.reported,
        'seeded' => SignalStatus.seeded,
        _ => SignalStatus.unavailable,
      };

  String get label => switch (this) {
        SignalStatus.live => 'Live',
        SignalStatus.cached => 'Cached',
        SignalStatus.reported => 'From your soil card',
        SignalStatus.seeded => 'District average',
        SignalStatus.unavailable => 'Unavailable',
      };
}

/// Where one signal came from.
class Provenance {
  const Provenance({
    required this.source,
    required this.status,
    this.fetchedAt,
    this.note,
  });

  final String source;
  final SignalStatus status;
  final String? fetchedAt;
  final String? note;

  factory Provenance.fromJson(Map<String, dynamic> json) => Provenance(
        source: json['source'] as String? ?? 'unknown',
        status: SignalStatus.parse(json['status'] as String?),
        fetchedAt: json['fetchedAt'] as String?,
        note: json['note'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'source': source,
        'status': status.name,
        if (fetchedAt != null) 'fetchedAt': fetchedAt,
        if (note != null) 'note': note,
      };
}

/// Soil chemistry. `p` and `k` are nullable by necessity — SoilGrids models
/// neither, so they arrive only from a seeded district Soil Health Card.
class Soil {
  const Soil({
    this.ph,
    this.n,
    this.p,
    this.k,
    this.cec,
    this.moisture,
    this.soc,
    this.clay,
  });

  final double? ph;
  final double? n;
  final double? p;
  final double? k;
  final double? cec;
  final double? moisture;
  final double? soc;
  final double? clay;

  factory Soil.fromJson(Map<String, dynamic> json) => Soil(
        ph: _toDouble(json['ph']),
        n: _toDouble(json['n']),
        p: _toDouble(json['p']),
        k: _toDouble(json['k']),
        cec: _toDouble(json['cec']),
        moisture: _toDouble(json['moisture']),
        soc: _toDouble(json['soc']),
        clay: _toDouble(json['clay']),
      );

  Map<String, dynamic> toJson() => {
        'ph': ph,
        'n': n,
        'p': p,
        'k': k,
        'cec': cec,
        'moisture': moisture,
        'soc': soc,
        'clay': clay,
      };

  /// Plain-language pH band — the annotated form M1 passes to Gemini rather
  /// than a raw number.
  String? get phBand {
    if (ph == null) return null;
    if (ph! < 6.0) return 'acidic';
    if (ph! > 7.8) return 'alkaline';
    return 'neutral';
  }

  /// Total nitrogen banding for Indian topsoils (g/kg).
  String? get nitrogenBand {
    if (n == null) return null;
    if (n! < 1.0) return 'low';
    if (n! < 2.0) return 'medium';
    return 'high';
  }
}

/// A day of the forecast.
class DailyTemp {
  const DailyTemp({required this.date, this.maxC, this.minC});

  final String date;
  final double? maxC;
  final double? minC;

  factory DailyTemp.fromJson(Map<String, dynamic> json) => DailyTemp(
        date: json['date'] as String? ?? '',
        maxC: _toDouble(json['maxC']),
        minC: _toDouble(json['minC']),
      );

  Map<String, dynamic> toJson() => {'date': date, 'maxC': maxC, 'minC': minC};
}

/// Field health, rendered as the chip on S2.
enum HealthChip {
  green,
  yellow,
  red;

  static HealthChip parse(String? raw) => switch (raw?.toUpperCase()) {
        'GREEN' => HealthChip.green,
        'RED' => HealthChip.red,
        _ => HealthChip.yellow,
      };

  String get code => name.toUpperCase();
}

/// M0's output: everything known about one field.
class FieldProfile {
  const FieldProfile({
    required this.fieldId,
    required this.polygon,
    required this.centroid,
    required this.areaHa,
    this.boundaryMode = 'pin',
    this.sowingDate,
    this.fertiliserLog = const [],
    this.lastIrrigation,
    this.crop,
    required this.soil,
    required this.healthChip,
    this.ndvi,
    this.ndviPercentile,
    this.neighbourhoodMedianNdvi,
    this.rainForecastMm,
    this.rainForecast7dMm,
    this.tempForecast = const [],
    this.radiationScore,
    this.soilRange = const {},
    this.climate = const {},
    this.terrain = const {},
    this.sources = const {},
    this.generatedAt,
  });

  final String fieldId;

  /// [lat, lng] pairs, closed ring — matches Firestore `Field.polygon`.
  final List<List<double>> polygon;
  final ({double lat, double lng}) centroid;
  final double areaHa;

  /// `drawn` when the farmer traced the boundary, `pin` when we generated a
  /// default square. Only the first makes [areaHa] a measurement.
  final String boundaryMode;

  /// What the farmer said is growing, e.g. `{id: wheat, label: गेहूँ}`.
  /// Recorded for M3; M0's health rule is deliberately crop-neutral.
  final Map<String, dynamic>? crop;

  /// When the farmer says they sowed, ISO yyyy-mm-dd.
  ///
  /// M0 measures nothing that reveals growth stage, so this is the only route
  /// to it, and M1's fertiliser advice depends on it. Stored on the profile
  /// rather than in app state so a cache resume does not lose it.
  final String? sowingDate;

  /// What the farmer says they have already put on this field this season,
  /// most recent last. Each entry is `{date, product?, bagsPerAcre?}` — the
  /// last two optional, because a date alone already fixes the timing and
  /// refusing an incomplete answer collects nothing at all.
  final List<Map<String, dynamic>> fertiliserLog;

  /// ISO date the field was last watered. Soil-water reanalysis lags a fresh
  /// irrigation by days, so without this the advisory can recommend water that
  /// is already in the ground.
  final String? lastIrrigation;

  /// True when [areaHa] came from the farmer's own boundary rather than the
  /// 1.5 ha default. The UI must not present the two alike.
  bool get areaIsMeasured => boundaryMode == 'drawn';

  String? get cropLabel => crop?['label'] as String?;
  final Soil soil;
  final HealthChip healthChip;
  final double? ndvi;

  /// Share of nearby cropland with a lower NDVI, 0-1. Null when no comparison
  /// was possible. This is what makes the health chip crop- and country-neutral.
  final double? ndviPercentile;
  final double? neighbourhoodMedianNdvi;
  final double? rainForecastMm;
  final double? rainForecast7dMm;
  final List<DailyTemp> tempForecast;
  final double? radiationScore;

  /// SoilGrids' own 90% interval per property. Wide — pH at the demo field is
  /// 6.2 to 10.3 — which is why a single number overstates what is known.
  final Map<String, ({double low, double high})> soilRange;

  /// Thermal, water-balance and atmospheric signals from the EE catalog.
  final Map<String, dynamic> climate;

  /// Elevation, slope and aspect from SRTM at 30 m.
  final Map<String, dynamic> terrain;
  final Map<String, Provenance> sources;
  final String? generatedAt;

  factory FieldProfile.fromJson(Map<String, dynamic> json) {
    final rawPolygon = (json['polygon'] as List? ?? const [])
        .map((p) => (p as List).map((v) => (v as num).toDouble()).toList())
        .toList();

    final rawCentroid = json['centroid'] as Map<String, dynamic>? ?? const {};

    return FieldProfile(
      fieldId: json['fieldId'] as String? ?? 'field-demo',
      polygon: rawPolygon,
      centroid: (
        lat: _toDouble(rawCentroid['lat']) ?? 0,
        lng: _toDouble(rawCentroid['lng']) ?? 0,
      ),
      areaHa: _toDouble(json['areaHa']) ?? 0,
      boundaryMode: json['boundaryMode'] as String? ?? 'pin',
      crop: (json['crop'] as Map?)?.cast<String, dynamic>(),
      sowingDate: json['sowingDate'] as String?,
      fertiliserLog: ((json['fertiliserLog'] as List?) ?? const [])
          .whereType<Map>()
          .map((e) => e.cast<String, dynamic>())
          .toList(),
      lastIrrigation: json['lastIrrigation'] as String?,
      soil: Soil.fromJson(json['soil'] as Map<String, dynamic>? ?? const {}),
      healthChip: HealthChip.parse(json['healthChip'] as String?),
      ndvi: _toDouble(json['ndvi']),
      ndviPercentile: _toDouble(json['ndviPercentile']),
      neighbourhoodMedianNdvi: _toDouble(json['neighbourhoodMedianNdvi']),
      rainForecastMm: _toDouble(json['rainForecastMm']),
      rainForecast7dMm: _toDouble(json['rainForecast7dMm']),
      tempForecast: (json['tempForecast'] as List? ?? const [])
          .map((d) => DailyTemp.fromJson(d as Map<String, dynamic>))
          .toList(),
      radiationScore: _toDouble(json['radiationScore']),
      soilRange: (json['soilRange'] as Map<String, dynamic>? ?? const {}).map(
        (key, value) {
          final range = value as Map<String, dynamic>;
          return MapEntry(key, (
            low: _toDouble(range['low']) ?? 0,
            high: _toDouble(range['high']) ?? 0,
          ));
        },
      ),
      climate: json['climate'] as Map<String, dynamic>? ?? const {},
      terrain: json['terrain'] as Map<String, dynamic>? ?? const {},
      sources: (json['sources'] as Map<String, dynamic>? ?? const {}).map(
        (key, value) =>
            MapEntry(key, Provenance.fromJson(value as Map<String, dynamic>)),
      ),
      generatedAt: json['generatedAt'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'fieldId': fieldId,
        'polygon': polygon,
        'centroid': {'lat': centroid.lat, 'lng': centroid.lng},
        'areaHa': areaHa,
        'boundaryMode': boundaryMode,
        'crop': crop,
        'sowingDate': sowingDate,
        'fertiliserLog': fertiliserLog,
        'lastIrrigation': lastIrrigation,
        'ndvi': ndvi,
        'ndviPercentile': ndviPercentile,
        'neighbourhoodMedianNdvi': neighbourhoodMedianNdvi,
        'soil': soil.toJson(),
        'rainForecastMm': rainForecastMm,
        'rainForecast7dMm': rainForecast7dMm,
        'tempForecast': tempForecast.map((d) => d.toJson()).toList(),
        'radiationScore': radiationScore,
        'soilRange': soilRange.map(
          (k, v) => MapEntry(k, {'low': v.low, 'high': v.high}),
        ),
        'climate': climate,
        'terrain': terrain,
        'healthChip': healthChip.code,
        'sources': sources.map((k, v) => MapEntry(k, v.toJson())),
        'generatedAt': generatedAt,
      };

  /// True when every signal came from its real source this run — what the demo
  /// wants to be able to claim out loud.
  bool get isFullyLive =>
      sources.values.every((p) => p.status == SignalStatus.live);

  /// Rain received against water demanded over the same week. Negative means
  /// the crop is drawing down soil water — the number an irrigation call turns
  /// on, and one rainfall alone cannot express.
  double? get weeklyWaterBalanceMm {
    final rain = _toDouble(climate['observedRain7dMm']);
    final et0 = _toDouble(climate['et0MmPerDay']);
    if (rain == null || et0 == null) return null;
    return rain - et0 * 7;
  }

  /// "7.9 (likely 6.2-10.3)" — the honest way to show a modelled soil value.
  String? soilWithRange(String property, double? value) {
    if (value == null) return null;
    final range = soilRange[property];
    if (range == null) return value.toString();
    return '$value (likely ${range.low}-${range.high})';
  }

  /// Plain-language standing against nearby farms, for the advisory and the UI.
  String? get neighbourStanding {
    final p = ndviPercentile;
    if (p == null) return null;
    if (p >= 0.75) return 'ahead of most farms nearby';
    if (p >= 0.35) return 'about average for farms nearby';
    if (p >= 0.15) return 'behind most farms nearby';
    return 'among the weakest fields nearby';
  }

  /// Highest daily maximum in the forecast window; M3 penalises above ~32 C.
  double? get peakTempC {
    final maxima = tempForecast.map((d) => d.maxC).whereType<double>();
    return maxima.isEmpty ? null : maxima.reduce((a, b) => a > b ? a : b);
  }
}

double? _toDouble(Object? value) => switch (value) {
      null => null,
      final num n => n.toDouble(),
      final String s => double.tryParse(s),
      _ => null,
    };
