/// HTTP client for the M0 field-intelligence endpoint.
///
/// Talks to `backend/dev_server.py` in development and to the deployed Cloud
/// Function in production — identical JSON either way.
library;

import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/config.dart';
import '../domain/field_profile.dart';

class M0Exception implements Exception {
  const M0Exception(this.message);
  final String message;
  @override
  String toString() => 'M0Exception: $message';
}

class M0Client {
  M0Client({http.Client? client, String? endpoint})
      : _client = client ?? http.Client(),
        _endpoint = endpoint ?? AppConfig.m0Endpoint;

  final http.Client _client;
  final String _endpoint;

  /// Build a field profile from a dropped pin, or from a drawn boundary.
  ///
  /// Exactly one of [pin] and [polygon] is needed. A polygon is the farmer's
  /// own boundary and is used verbatim; a pin has a square derived from it.
  /// [fallbackNdvi] supplies a cached NDVI if Earth Engine is unreachable.
  /// [crop] is what the farmer says is growing — recorded for M3, not used by
  /// M0, whose health rule ranks against neighbours regardless of crop.
  /// [sowingDate] is likewise recorded rather than used: M1 needs it to place
  /// the crop in its growth stage, and M0 measures nothing that reveals one.
  /// [fertiliserLog] and [lastIrrigation] are the same kind of fact — things
  /// only the farmer knows, which stop M1 recommending a dose or an irrigation
  /// the field has already had.
  Future<FieldProfile> buildProfile({
    ({double lat, double lng})? pin,
    List<List<double>>? polygon,
    String fieldId = 'field-demo-narwana',
    double plotHa = AppConfig.defaultPlotHa,
    double? fallbackNdvi,
    Map<String, dynamic>? seededSoil,
    Map<String, dynamic>? crop,
    String? sowingDate,
    List<Map<String, dynamic>>? fertiliserLog,
    String? lastIrrigation,
    Duration timeout = const Duration(seconds: 60),
  }) async {
    assert(pin != null || polygon != null, 'need a pin or a polygon');

    final body = jsonEncode({
      'polygon': ?polygon,
      if (polygon == null && pin != null)
        'pin': {'lat': pin.lat, 'lng': pin.lng},
      'fieldId': fieldId,
      'plotHa': plotHa,
      'fallbackNdvi': ?fallbackNdvi,
      'seededSoil': ?seededSoil,
      'crop': ?crop,
      'sowingDate': ?sowingDate,
      if (fertiliserLog != null && fertiliserLog.isNotEmpty)
        'fertiliserLog': fertiliserLog,
      'lastIrrigation': ?lastIrrigation,
    });

    late final http.Response response;
    try {
      response = await _client
          .post(
            Uri.parse(_endpoint),
            headers: const {'Content-Type': 'application/json'},
            body: body,
          )
          .timeout(timeout);
    } catch (error) {
      throw M0Exception('could not reach M0 at $_endpoint ($error)');
    }

    if (response.statusCode != 200) {
      throw M0Exception('M0 returned ${response.statusCode}: ${response.body}');
    }

    try {
      return FieldProfile.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>,
      );
    } catch (error) {
      throw M0Exception('could not parse the M0 response ($error)');
    }
  }

  void dispose() => _client.close();
}
