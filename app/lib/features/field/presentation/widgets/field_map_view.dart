/// The field map on S1.
///
/// The Tech Spec mandates Google Maps Platform for the field render. When a key
/// is present and the platform has a Maps SDK, this shows the real hybrid map;
/// otherwise it falls back to a schematic render of the same geometry. Same
/// degradation pattern as NDVI: never let a missing credential blank a screen.
///
/// Build with the key to get the real map:
///   flutter run -d chrome --dart-define=MAPS_KEY=...
library;

import 'dart:ui' show PointMode;

import 'package:flutter/material.dart';

import '../../../../core/config.dart';
import '../../../../core/maps_loader.dart';
import '../../domain/geometry.dart';
import 'google_field_map.dart';

class FieldMapView extends StatefulWidget {
  const FieldMapView({
    super.key,
    required this.centre,
    required this.polygon,
    this.draftVertices = const [],
    this.onMapTap,
    this.showPin = true,
    this.spanDegrees = 0.004,
  });

  final ({double lat, double lng}) centre;

  /// The committed boundary, filled and outlined.
  final List<List<double>> polygon;

  /// Vertices placed so far while drawing, drawn as an open chain.
  final List<List<double>> draftVertices;

  /// Tap anywhere on the map — the parent decides whether that moves the pin
  /// or adds a boundary vertex.
  final void Function(double lat, double lng)? onMapTap;

  /// Hidden while drawing, when the vertices carry the meaning instead.
  final bool showPin;

  /// Latitude range covered by the view — the schematic's "zoom".
  final double spanDegrees;

  @override
  State<FieldMapView> createState() => _FieldMapViewState();
}

class _FieldMapViewState extends State<FieldMapView> {
  /// Resolved once per mount, not per rebuild — the pin moves constantly.
  late final Future<bool> _mapsReady = ensureMapsLoaded(AppConfig.mapsApiKey);

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<bool>(
      future: _mapsReady,
      builder: (context, snapshot) {
        // While the SDK loads, show the schematic rather than a spinner: the
        // boundary must be visible immediately.
        if (snapshot.data == true) {
          return GoogleFieldMap(
            centre: widget.centre,
            polygon: widget.polygon,
            draftVertices: widget.draftVertices,
            onMapTap: widget.onMapTap,
            showPin: widget.showPin,
          );
        }
        return _SchematicMap(
          centre: widget.centre,
          polygon: widget.polygon,
          draftVertices: widget.draftVertices,
          onMapTap: widget.onMapTap,
          showPin: widget.showPin,
          spanDegrees: widget.spanDegrees,
        );
      },
    );
  }
}

/// The no-key fallback: the same geometry, drawn honestly as a diagram.
class _SchematicMap extends StatelessWidget {
  const _SchematicMap({
    required this.centre,
    required this.polygon,
    required this.draftVertices,
    required this.onMapTap,
    required this.showPin,
    required this.spanDegrees,
  });

  final ({double lat, double lng}) centre;
  final List<List<double>> polygon;
  final List<List<double>> draftVertices;
  final void Function(double lat, double lng)? onMapTap;
  final bool showPin;
  final double spanDegrees;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final size = Size(constraints.maxWidth, constraints.maxHeight);
        return GestureDetector(
          onTapDown: onMapTap == null
              ? null
              : (details) {
                  final local = details.localPosition;
                  final lngSpan = spanDegrees * (size.width / size.height);
                  final lat =
                      centre.lat + (0.5 - local.dy / size.height) * spanDegrees;
                  final lng =
                      centre.lng + (local.dx / size.width - 0.5) * lngSpan;
                  onMapTap!(lat, lng);
                },
          child: Stack(
            fit: StackFit.expand,
            children: [
              CustomPaint(
                painter: _FieldPainter(
                  centre: centre,
                  polygon: polygon,
                  draftVertices: draftVertices,
                  showPin: showPin,
                  spanDegrees: spanDegrees,
                  surface: Theme.of(context).colorScheme.surfaceContainerHighest,
                  outline: Theme.of(context).colorScheme.primary,
                ),
              ),
              if (!AppConfig.hasMapsKey)
                const Positioned(
                  left: 8,
                  bottom: 8,
                  child: _Badge(
                    text: 'Schematic view — set MAPS_KEY for Google Maps',
                  ),
                ),
              Positioned(
                right: 8,
                top: 8,
                child: _Badge(
                  text: '${areaHaOf(polygon).toStringAsFixed(2)} ha',
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _Badge extends StatelessWidget {
  const _Badge({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: Colors.black.withValues(alpha: 0.55),
          borderRadius: BorderRadius.circular(6),
        ),
        child: Text(
          text,
          style: const TextStyle(color: Colors.white, fontSize: 11),
        ),
      );
}

class _FieldPainter extends CustomPainter {
  _FieldPainter({
    required this.centre,
    required this.polygon,
    required this.draftVertices,
    required this.showPin,
    required this.spanDegrees,
    required this.surface,
    required this.outline,
  });

  final ({double lat, double lng}) centre;
  final List<List<double>> polygon;
  final List<List<double>> draftVertices;
  final bool showPin;
  final double spanDegrees;
  final Color surface;
  final Color outline;

  @override
  void paint(Canvas canvas, Size size) {
    final lngSpan = spanDegrees * (size.width / size.height);

    Offset project(double lat, double lng) => Offset(
          ((lng - centre.lng) / lngSpan + 0.5) * size.width,
          (0.5 - (lat - centre.lat) / spanDegrees) * size.height,
        );

    canvas.drawRect(Offset.zero & size, Paint()..color = surface);

    // Field-scale grid, ~50 m per cell, purely to give the eye a sense of scale.
    final grid = Paint()
      ..color = outline.withValues(alpha: 0.10)
      ..strokeWidth = 1;
    const cells = 8;
    for (var i = 1; i < cells; i++) {
      final dx = size.width * i / cells;
      final dy = size.height * i / cells;
      canvas.drawLine(Offset(dx, 0), Offset(dx, size.height), grid);
      canvas.drawLine(Offset(0, dy), Offset(size.width, dy), grid);
    }

    if (polygon.length > 2) {
      final ring = openRing(polygon);
      final path = Path()
        ..addPolygon([for (final p in ring) project(p[0], p[1])], true);

      canvas.drawPath(path, Paint()..color = outline.withValues(alpha: 0.22));
      canvas.drawPath(
        path,
        Paint()
          ..color = outline
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.5,
      );
    }

    // The boundary being drawn: an open chain of numbered vertices.
    if (draftVertices.isNotEmpty) {
      final points = [for (final v in draftVertices) project(v[0], v[1])];

      if (points.length > 1) {
        canvas.drawPoints(
          PointMode.polygon,
          points,
          Paint()
            ..color = outline
            ..strokeWidth = 2
            ..style = PaintingStyle.stroke,
        );
      }

      for (final point in points) {
        canvas.drawCircle(point, 6, Paint()..color = Colors.white);
        canvas.drawCircle(point, 4, Paint()..color = outline);
      }
    }

    if (showPin) {
      final pin = project(centre.lat, centre.lng);
      canvas.drawCircle(pin, 7, Paint()..color = Colors.white);
      canvas.drawCircle(pin, 5, Paint()..color = outline);
    }
  }

  @override
  bool shouldRepaint(covariant _FieldPainter old) =>
      old.centre != centre ||
      old.polygon != polygon ||
      old.draftVertices != draftVertices ||
      old.showPin != showPin ||
      old.spanDegrees != spanDegrees;
}
