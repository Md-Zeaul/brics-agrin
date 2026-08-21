/// S1 — Onboarding / field capture.
///
/// Build Brief: "capture the field in under 30 seconds with almost no typing",
/// from a farmer who "drops a pin (or draws a boundary)". Both are here: the
/// pin is pre-dropped on the demo field with a derived square, and draw mode
/// lets the farmer tap their actual corners when the square is not good enough.
library;

import 'package:flutter/material.dart';

import '../../../core/config.dart';
import '../../../core/l10n/app_language.dart';
import '../../../core/l10n/language_scope.dart';
import '../data/field_repository.dart';
import '../domain/crop.dart';
import '../domain/geometry.dart';
import 'widgets/coordinate_sheet.dart';
import 'home_screen.dart';
import 'widgets/crop_picker.dart';
import 'widgets/field_map_view.dart';
import 'widgets/soil_card_input.dart';

/// How the field boundary is being captured.
enum CaptureMode { pin, draw }

class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key, required this.repository});

  final FieldRepository repository;

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  /// A boundary needs at least a triangle.
  static const _minVertices = 3;

  CaptureMode _mode = CaptureMode.pin;

  double _lat = AppConfig.demoLat;
  double _lng = AppConfig.demoLng;

  /// Held fixed while drawing so the view does not jump under the farmer's
  /// finger as they place corners.
  late ({double lat, double lng}) _viewCentre = (lat: _lat, lng: _lng);

  late List<List<double>> _pinPolygon = squarePolygonAround(_lat, _lng);
  List<List<double>> _draft = [];

  CropRegistry _registry = const CropRegistry([]);
  Crop? _crop = Crop.fallbackDefault;
  /// Unset until the farmer says otherwise.
  ///
  /// A pre-filled date would be friendlier and would also be fabricated: it
  /// feeds M1's growth stage, which decides whether a fertiliser window is
  /// open. Left null, the stage stays `unknown` and stage-dependent advice is
  /// simply not offered — which is the correct outcome for a field nobody has
  /// told us about.
  DateTime? _sowingDate;

  /// ISO yyyy-mm-dd, or null. The shape M0 stores and M1 reads.
  String? get _sowingDateIso =>
      _sowingDate?.toIso8601String().split('T').first;
  /// Fallback only. When the app shell is above us the shared controller is
  /// the source of truth, so the toggle here and the one on S2 cannot disagree.
  String _language = 'hi';

  String get _activeLanguage =>
      LanguageScope.maybeOf(context)?.language.code ?? _language;

  void _setLanguage(String code) {
    setState(() => _language = code);
    LanguageScope.maybeOf(context)?.switchTo(AppLanguage.fromCode(code));
  }
  bool _building = false;

  /// Optional Soil Health Card values; these outrank the district average.
  double? _phosphorus;
  double? _potassium;

  @override
  void initState() {
    super.initState();
    CropRegistry.load().then((registry) {
      if (!mounted) return;
      setState(() {
        _registry = registry;
        _crop = registry.byId(_crop?.id ?? 'wheat') ?? _crop;
      });
    });
  }

  bool get _drawing => _mode == CaptureMode.draw;
  bool get _draftIsUsable => _draft.length >= _minVertices;

  /// A crossed boundary shoelaces to ~0 ha, which would silently poison every
  /// per-hectare number downstream. The backend refuses it too; catching it
  /// here explains the problem while the lines are still on screen.
  bool get _draftCrossesItself =>
      _draftIsUsable && !isSimple([..._draft, _draft.first]);

  bool get _draftIsValid => _draftIsUsable && !_draftCrossesItself;

  /// The boundary as it currently stands, whichever mode produced it.
  List<List<double>> get _boundary {
    if (!_drawing) return _pinPolygon;
    if (!_draftIsUsable) return const [];
    return [..._draft, _draft.first]; // close the ring
  }

  void _handleTap(double lat, double lng) {
    setState(() {
      if (_drawing) {
        _draft = [
          ..._draft,
          [double.parse(lat.toStringAsFixed(6)), double.parse(lng.toStringAsFixed(6))],
        ];
      } else {
        _lat = lat;
        _lng = lng;
        _viewCentre = (lat: lat, lng: lng);
        _pinPolygon = squarePolygonAround(lat, lng);
      }
    });
  }

  void _setMode(CaptureMode mode) {
    setState(() {
      _mode = mode;
      if (mode == CaptureMode.pin) _draft = [];
    });
  }

  /// Jump the pin to a typed coordinate.
  ///
  /// Only meaningful in pin mode: a drawn boundary is already a set of real
  /// corners, so moving its centre would misrepresent what the farmer traced.
  Future<void> _enterCoordinates() async {
    final entered = await showCoordinateSheet(
      context,
      initialLat: _lat,
      initialLng: _lng,
    );
    if (entered == null || !mounted) return;
    setState(() {
      _lat = entered.lat;
      _lng = entered.lng;
      _pinPolygon = squarePolygonAround(_lat, _lng);
      _viewCentre = (lat: _lat, lng: _lng);
    });
  }

  void _undoVertex() {
    if (_draft.isEmpty) return;
    setState(() => _draft = _draft.sublist(0, _draft.length - 1));
  }

  void _clearDraft() => setState(() => _draft = []);

  Future<void> _confirmField() async {
    final boundary = _boundary;
    if (_drawing && !_draftIsUsable) return;

    setState(() => _building = true);
    try {
      final soilCard = (_phosphorus == null && _potassium == null)
          ? null
          : <String, dynamic>{
              'p': _phosphorus,
              'k': _potassium,
              '_reported': true,
            };

      // The farmer's answer travels with the profile even though M0 does not
      // consult it — M3's crop scoring will, and capture is the only cheap
      // moment to ask.
      final crop = _crop == null
          ? null
          : <String, dynamic>{
              'id': _crop!.id,
              'label': _crop!.label(_activeLanguage),
              'language': _activeLanguage,
            };

      final result = _drawing
          ? await widget.repository.profileForPolygon(
              polygon: boundary,
              seededSoil: soilCard,
              crop: crop,
              sowingDate: _sowingDateIso,
            )
          : await widget.repository.profileForPin(
              lat: _lat,
              lng: _lng,
              seededSoil: soilCard,
              crop: crop,
              sowingDate: _sowingDateIso,
            );

      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => HomeScreen(
            result: result,
            repository: widget.repository,
            crop: _crop?.label(_activeLanguage) ?? 'Crop',
            language: _activeLanguage,
          ),
        ),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Could not build the field profile: $error')),
      );
    } finally {
      if (mounted) setState(() => _building = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final boundary = _boundary;
    final area = boundary.isEmpty ? 0.0 : areaHaOf(boundary);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Your field'),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: SegmentedButton<String>(
              showSelectedIcon: false,
              segments: const [
                ButtonSegment(value: 'hi', label: Text('हिं')),
                ButtonSegment(value: 'en', label: Text('EN')),
                ButtonSegment(value: 'pt', label: Text('PT')),
              ],
              selected: {_activeLanguage},
              onSelectionChanged: (s) => _setLanguage(s.first),
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: FieldMapView(
              centre: _viewCentre,
              polygon: boundary,
              draftVertices: _drawing ? _draft : const [],
              onMapTap: _handleTap,
              showPin: !_drawing,
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SegmentedButton<CaptureMode>(
                  segments: const [
                    ButtonSegment(
                      value: CaptureMode.pin,
                      icon: Icon(Icons.place_outlined),
                      label: Text('Drop a pin'),
                    ),
                    ButtonSegment(
                      value: CaptureMode.draw,
                      icon: Icon(Icons.timeline),
                      label: Text('Draw boundary'),
                    ),
                  ],
                  selected: {_mode},
                  onSelectionChanged: (s) => _setMode(s.first),
                ),
                const SizedBox(height: 12),
                _instructions(theme),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        _drawing
                            ? '${_draft.length} corner${_draft.length == 1 ? '' : 's'}'
                                '${area > 0 ? ' · ${area.toStringAsFixed(2)} ha' : ''}'
                            : '${_lat.toStringAsFixed(5)}, ${_lng.toStringAsFixed(5)}'
                                ' · ${area.toStringAsFixed(2)} ha',
                        style: theme.textTheme.bodySmall,
                      ),
                    ),
                    // Pin mode only: a drawn boundary is already real corners.
                    if (!_drawing)
                      TextButton.icon(
                        onPressed: _enterCoordinates,
                        icon: const Icon(Icons.edit_location_alt_outlined,
                            size: 18),
                        label: const Text('Enter coordinates'),
                      ),
                  ],
                ),
                if (_drawing) ...[
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      TextButton.icon(
                        onPressed: _draft.isEmpty ? null : _undoVertex,
                        icon: const Icon(Icons.undo, size: 18),
                        label: const Text('Undo'),
                      ),
                      const SizedBox(width: 8),
                      TextButton.icon(
                        onPressed: _draft.isEmpty ? null : _clearDraft,
                        icon: const Icon(Icons.clear, size: 18),
                        label: const Text('Clear'),
                      ),
                    ],
                  ),
                ],
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: CropPicker(
                        registry: _registry,
                        selected: _crop,
                        language: _activeLanguage,
                        onChanged: (crop) => setState(() => _crop = crop),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: InkWell(
                        onTap: () async {
                          final picked = await showDatePicker(
                            context: context,
                            initialDate: _sowingDate ?? DateTime.now(),
                            firstDate: DateTime(2024),
                            lastDate: DateTime.now().add(
                              const Duration(days: 365),
                            ),
                          );
                          if (picked != null) {
                            setState(() => _sowingDate = picked);
                          }
                        },
                        child: InputDecorator(
                          decoration: const InputDecoration(
                            labelText: 'Sowing date',
                            border: OutlineInputBorder(),
                          ),
                          child: Text(
                            _sowingDate == null
                                ? 'Not set'
                                : '${_sowingDate!.day}/${_sowingDate!.month}/'
                                    '${_sowingDate!.year}',
                            style: _sowingDate == null
                                ? TextStyle(
                                    color: Theme.of(context).colorScheme.outline,
                                  )
                                : null,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                SoilCardInput(
                  phosphorus: _phosphorus,
                  potassium: _potassium,
                  onChanged: (p, k) => setState(() {
                    _phosphorus = p;
                    _potassium = k;
                  }),
                ),
                const SizedBox(height: 8),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    onPressed: _building || (_drawing && !_draftIsValid)
                        ? null
                        : _confirmField,
                    child: Padding(
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      child: _building
                          ? const Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                SizedBox(
                                  width: 18,
                                  height: 18,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
                                ),
                                SizedBox(width: 12),
                                Text('Reading satellite and soil…'),
                              ],
                            )
                          : Text(
                              !_drawing || _draftIsValid
                                  ? 'Confirm field'
                                  : _draftCrossesItself
                                      ? 'Lines cross — undo and redraw'
                                      : 'Tap at least $_minVertices corners',
                            ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _instructions(ThemeData theme) => Text(
        _drawing
            ? 'Tap each corner of your field'
            : 'Tap the map to move your field',
        style: theme.textTheme.bodyMedium,
      );
}
