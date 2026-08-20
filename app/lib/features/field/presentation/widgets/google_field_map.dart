/// The real Google Maps render of the field — the Tech Spec's S1 map.
///
/// Only mounted once [ensureMapsLoaded] confirms an SDK is available; see
/// `field_map_view.dart`, which decides between this and the schematic view.
library;

import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';

class GoogleFieldMap extends StatelessWidget {
  const GoogleFieldMap({
    super.key,
    required this.centre,
    required this.polygon,
    this.draftVertices = const [],
    this.onMapTap,
    this.showPin = true,
  });

  final ({double lat, double lng}) centre;
  final List<List<double>> polygon;
  final List<List<double>> draftVertices;
  final void Function(double lat, double lng)? onMapTap;
  final bool showPin;

  @override
  Widget build(BuildContext context) {
    final target = LatLng(centre.lat, centre.lng);
    final colour = Theme.of(context).colorScheme.primary;

    return GoogleMap(
      initialCameraPosition: CameraPosition(target: target, zoom: 17),
      // Satellite is the right base layer: the farmer recognises their own
      // field by what is growing on it, not by road names.
      mapType: MapType.hybrid,
      myLocationButtonEnabled: false,
      zoomControlsEnabled: false,
      onTap: onMapTap == null
          ? null
          : (position) => onMapTap!(position.latitude, position.longitude),
      markers: {
        if (showPin)
          Marker(
            markerId: const MarkerId('field-pin'),
            position: target,
            draggable: onMapTap != null,
            onDragEnd: (position) =>
                onMapTap?.call(position.latitude, position.longitude),
          ),
        // Each placed corner, so the farmer can see what they have tapped.
        for (var i = 0; i < draftVertices.length; i++)
          Marker(
            markerId: MarkerId('draft-$i'),
            position: LatLng(draftVertices[i][0], draftVertices[i][1]),
            icon: BitmapDescriptor.defaultMarkerWithHue(
              BitmapDescriptor.hueAzure,
            ),
            infoWindow: InfoWindow(title: 'Corner ${i + 1}'),
          ),
      },
      polylines: {
        if (draftVertices.length > 1)
          Polyline(
            polylineId: const PolylineId('field-draft'),
            points: [
              for (final v in draftVertices) LatLng(v[0], v[1]),
            ],
            width: 3,
            color: colour,
          ),
      },
      polygons: {
        if (polygon.length > 2)
          Polygon(
            polygonId: const PolygonId('field-boundary'),
            points: [
              for (final point in polygon) LatLng(point[0], point[1]),
            ],
            strokeWidth: 3,
            strokeColor: colour,
            fillColor: colour.withValues(alpha: 0.25),
          ),
      },
    );
  }
}
