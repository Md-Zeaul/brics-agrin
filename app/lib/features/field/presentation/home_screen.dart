/// S2 — Home, showing what M0 built.
///
/// The advisory card itself is M1 and is not built yet, so this renders the
/// field profile M0 produced: the health chip, the soil and weather signals the
/// advisory will reason over, and the provenance of each one.
library;

import 'package:flutter/material.dart';

import '../../../core/l10n/language_button.dart';
import '../../copilot/data/advisory_repository.dart';
import '../../copilot/presentation/advisory_card.dart';
import '../../../core/l10n/language_scope.dart';
import '../../../core/routes.dart';
import '../data/field_repository.dart';
import '../domain/field_profile.dart';
import 'onboarding_screen.dart';
import 'widgets/health_chip_badge.dart';
import 'widgets/provenance_list.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({
    super.key,
    required this.result,
    required this.repository,
    this.advisories,
    this.crop = 'Wheat',
    this.language = 'hi',
  });

  final FieldProfileResult result;
  final FieldRepository repository;

  /// Injectable so widget tests can drive the card without a server. Null
  /// means "make one" rather than "do without", because a screen that silently
  /// shows no advice is indistinguishable from one whose endpoint is down.
  final AdvisoryRepository? advisories;
  final String crop;
  final String language;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late FieldProfileResult _result = widget.result;
  late final AdvisoryRepository _advisories =
      widget.advisories ?? AdvisoryRepository();

  bool _refreshing = false;
  AdvisoryResult? _advisory;
  bool _advising = false;
  String? _advisedLanguage;

  FieldProfile get _profile => _result.profile;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // The language lives in an inherited notifier, so S10's flip to Portuguese
    // arrives here as a dependency change. Re-advise rather than leave Hindi
    // text under a Portuguese interface.
    final language = LanguageScope.languageOf(context).code;
    if (language != _advisedLanguage) {
      _advisedLanguage = language;
      _loadAdvisory(language);
    }
  }

  @override
  void dispose() {
    if (widget.advisories == null) _advisories.dispose();
    super.dispose();
  }

  /// Cache first, then the network — the same order the profile follows, and
  /// the reason S2 has something to show before any call completes.
  Future<void> _loadAdvisory(String language) async {
    final restored =
        await _advisories.restored(_profile.fieldId, language);
    if (!mounted || _advisedLanguage != language) return;
    setState(() {
      _advisory = restored;
      _advising = true;
    });

    final live = await _advisories.adviseFor(_profile, language: language);
    if (!mounted || _advisedLanguage != language) return;
    setState(() {
      if (live != null) _advisory = live;
      _advising = false;
    });
  }

  /// Back to capture. Without this the first cached profile is a dead end —
  /// the farmer can never add a second plot and the demo can never show S1
  /// again without clearing browser storage by hand.
  void _startNewField() {
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => OnboardingScreen(repository: widget.repository),
      ),
    );
  }

  Future<void> _refresh() async {
    setState(() => _refreshing = true);
    try {
      // Refreshing a drawn field through profileForPin would silently replace
      // the farmer's boundary with a default square and change its area.
      final refreshed = _profile.areaIsMeasured
          ? await widget.repository.profileForPolygon(
              polygon: _profile.polygon,
              fieldId: _profile.fieldId,
              crop: _profile.crop,
            )
          : await widget.repository.profileForPin(
              lat: _profile.centroid.lat,
              lng: _profile.centroid.lng,
              fieldId: _profile.fieldId,
              crop: _profile.crop,
            );
      if (mounted) {
        setState(() => _result = refreshed);
        await _loadAdvisory(_advisedLanguage ?? 'en');
      }
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Refresh failed: $error')));
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final t = LanguageScope.stringsOf(context);
    final soil = _profile.soil;
    final chipDriver = _explainDriver(
      _profile.sources['healthChip']?.note?.replaceFirst('driver: ', ''),
      _profile.ndviPercentile,
    );

    return Scaffold(
      appBar: AppBar(
        title: Text(t('home.greeting')),
        actions: [
          const LanguageButton(),
          IconButton(
            onPressed: _refreshing ? null : _startNewField,
            icon: const Icon(Icons.add_location_alt_outlined),
            tooltip: 'Capture a different field',
          ),
          IconButton(
            onPressed: _refreshing ? null : _refresh,
            icon: _refreshing
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.refresh),
            tooltip: 'Rebuild the field profile',
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (_result.origin == ProfileOrigin.restored)
            const _Banner(
              icon: Icons.history,
              text: 'Saved profile from your last visit. '
                  'Refresh to fetch today\'s readings.',
            ),
          if (_result.origin == ProfileOrigin.stale)
            _Banner(
              icon: Icons.cloud_off,
              text: 'Offline — showing the last saved profile. '
                  '${_result.warning ?? ''}',
            ),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Flexible(
                flex: 3,
                child: HealthChipBadge(
                  chip: _profile.healthChip,
                  driver: chipDriver,
                ),
              ),
              const SizedBox(width: 12),
              Flexible(
                flex: 2,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      '${_profile.areaHa.toStringAsFixed(2)} ha · '
                      '${_profile.cropLabel ?? widget.crop}',
                      style: theme.textTheme.bodySmall,
                      textAlign: TextAlign.end,
                    ),
                    // A pin-derived area is the default square echoed back, not
                    // a measurement. Saying so is the difference between a
                    // number and a claim.
                    Text(
                      _profile.areaIsMeasured
                          ? 'measured from your boundary'
                          : 'default size · draw to measure',
                      style: theme.textTheme.labelSmall?.copyWith(
                        color: theme.colorScheme.outline,
                      ),
                      textAlign: TextAlign.end,
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // The brief's two primary actions. They navigate today, into stubs,
          // so the happy path can be walked end-to-end before M2 and M3 land.
          Row(
            children: [
              Expanded(
                child: FilledButton.icon(
                  onPressed: () =>
                      Navigator.of(context).pushNamed(Routes.scan),
                  icon: const Icon(Icons.center_focus_strong_outlined),
                  label: Text(t('home.scanCrop')),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: FilledButton.tonalIcon(
                  onPressed: () =>
                      Navigator.of(context).pushNamed(Routes.planner),
                  icon: const Icon(Icons.calendar_month_outlined),
                  label: Text(t('home.planSeason')),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          AdvisoryCard(result: _advisory, loading: _advising),
          const SizedBox(height: 16),

          _Section(
            title: 'Field',
            rows: [
              ('NDVI', _profile.ndvi?.toStringAsFixed(3) ?? 'awaiting Earth Engine'),
              (
                'Compared to nearby farms',
                _profile.neighbourStanding == null
                    ? 'no comparison available'
                    : '${_profile.neighbourStanding!} '
                        '(${(_profile.ndviPercentile! * 100).round()}th pct)'
              ),
              (
                'Neighbourhood NDVI',
                _profile.neighbourhoodMedianNdvi?.toStringAsFixed(3) ?? '—'
              ),
              ('Rain, next 7 days', _mm(_profile.rainForecast7dMm)),
              ('Peak temperature', _degrees(_profile.peakTempC)),
              (
                'Radiation score',
                _profile.radiationScore?.toStringAsFixed(2) ?? '—'
              ),
            ],
          ),
          const SizedBox(height: 8),
          _Section(
            title: 'Soil',
            rows: [
              (
                'pH',
                soil.ph == null
                    ? '—'
                    : '${_profile.soilWithRange('ph', soil.ph)} '
                        '· ${soil.phBand}'
              ),
              (
                'Nitrogen',
                soil.n == null
                    ? '—'
                    : '${_profile.soilWithRange('n', soil.n)} g/kg '
                        '· ${soil.nitrogenBand}'
              ),
              ('Phosphorus', soil.p?.toString() ?? 'no remote source'),
              ('Potassium', soil.k?.toString() ?? 'no remote source'),
              ('CEC', soil.cec == null ? '—' : '${soil.cec} cmol/kg'),
              (
                'Root-zone moisture',
                soil.moisture?.toStringAsFixed(2) ?? '—'
              ),
            ],
          ),
          const SizedBox(height: 8),
          _Section(
            title: 'Water balance',
            rows: [
              ('Rain received, 7 days', _mm(_num('observedRain7dMm'))),
              (
                'Water demand (ET₀)',
                _num('et0MmPerDay') == null
                    ? '—'
                    : '${_num('et0MmPerDay')!.toStringAsFixed(1)} mm/day'
              ),
              (
                'Net balance, 7 days',
                _profile.weeklyWaterBalanceMm == null
                    ? '—'
                    : '${_profile.weeklyWaterBalanceMm!.toStringAsFixed(0)} mm'
                        '${_profile.weeklyWaterBalanceMm! < 0 ? ' deficit' : ' surplus'}'
              ),
              (
                'Air dryness (VPD)',
                _num('vpdKpa') == null
                    ? '—'
                    : '${_num('vpdKpa')!.toStringAsFixed(2)} kPa'
              ),
              ('Soil water 0–7 cm', _vol('0_7cm')),
              ('Soil water 7–28 cm', _vol('7_28cm')),
            ],
          ),
          const SizedBox(height: 8),
          _Section(
            title: 'Land',
            rows: [
              (
                'Surface temperature',
                _degrees(_num('surfaceTempDayC') ?? _num('surfaceTempNightC'))
              ),
              ('Soil temperature', _degrees(_num('soilTempC'))),
              (
                'Elevation',
                _profile.terrain['elevationM'] == null
                    ? '—'
                    : '${_profile.terrain['elevationM']} m'
              ),
              (
                'Slope',
                _profile.terrain['slopeDeg'] == null
                    ? '—'
                    : '${_profile.terrain['slopeDeg']}°'
              ),
            ],
          ),
          const SizedBox(height: 16),

          Text('Where these numbers come from',
              style: theme.textTheme.titleSmall),
          const SizedBox(height: 8),
          ProvenanceList(sources: _profile.sources),
          const SizedBox(height: 24),
        ],
      ),
      bottomNavigationBar: _SideSwitch(
        farmerLabel: t('nav.farmer'),
        commandLabel: t('nav.commandCenter'),
      ),
    );
  }

  double? _num(String key) {
    final value = _profile.climate[key];
    return value is num ? value.toDouble() : null;
  }

  String _vol(String depth) {
    final water = _profile.climate['soilWater'];
    if (water is! Map) return '—';
    final value = water[depth];
    return value is num ? '${value.toStringAsFixed(3)} m³/m³' : '—';
  }

  String _mm(double? value) =>
      value == null ? '—' : '${value.toStringAsFixed(1)} mm';

  String _degrees(double? value) =>
      value == null ? '—' : '${value.toStringAsFixed(1)} °C';
}

class _Section extends StatelessWidget {
  const _Section({required this.title, required this.rows});

  final String title;
  final List<(String, String)> rows;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 8),
            for (final (label, value) in rows)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 3),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(flex: 2, child: Text(label)),
                    Expanded(
                      flex: 3,
                      child: Text(
                        value,
                        style: const TextStyle(fontWeight: FontWeight.w600),
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _Banner extends StatelessWidget {
  const _Banner({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: scheme.tertiaryContainer,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(icon, size: 18, color: scheme.onTertiaryContainer),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: TextStyle(color: scheme.onTertiaryContainer, fontSize: 12),
            ),
          ),
        ],
      ),
    );
  }
}

/// Turn a rule-engine driver code into something a farmer can act on.
///
/// The raw codes are written for the log, not the screen: GREEN arrives as
/// `healthy`, which renders as "Healthy · healthy" and explains nothing. Where
/// the chip came from the relative rule we can do better than a label and give
/// the actual standing — "ahead of 60% of nearby farms" is a reason, not a
/// restatement.
String? _explainDriver(String? driver, double? percentile) {
  if (driver == null) return null;

  switch (driver) {
    case 'healthy':
      if (percentile == null) return 'canopy on target';
      final ahead = (percentile * 100).round();
      return 'ahead of $ahead% of nearby farms';
    case 'below_neighbours':
      final behind = percentile == null ? null : (percentile * 100).round();
      return behind == null
          ? 'behind most nearby farms'
          : 'only $behind% of nearby farms are worse';
    case 'trailing_neighbours':
      return 'trailing nearby farms';
    case 'soil_drying':
      return 'root zone drying';
    case 'soil_moisture_critical':
      return 'root zone nearly dry';
    case 'canopy_stress':
      return 'canopy thin for this crop';
    case 'canopy_below_target':
      return 'canopy below target';
    case 'no_active_crop':
      return 'no crop in the ground yet';
    case 'ndvi_unavailable':
      return 'no satellite reading yet';
    default:
      return driver.replaceAll('_', ' ');
  }
}

/// The brief's top switch between the two sides of the app, put at the foot
/// where a thumb reaches it. The farmer side is already here, so tapping it is
/// a no-op rather than a redundant push.
class _SideSwitch extends StatelessWidget {
  const _SideSwitch({required this.farmerLabel, required this.commandLabel});

  final String farmerLabel;
  final String commandLabel;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SafeArea(
      child: Container(
        height: 52,
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
        child: Row(
          children: [
            Expanded(
              child: Center(
                child: Text(
                  farmerLabel,
                  style: theme.textTheme.labelLarge?.copyWith(
                    color: theme.colorScheme.primary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ),
            Expanded(
              child: TextButton(
                onPressed: () =>
                    Navigator.of(context).pushNamed(Routes.commandCenter),
                child: Text(commandLabel),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
