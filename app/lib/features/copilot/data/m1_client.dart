/// HTTP client for the M1 advisory endpoint.
///
/// Sends the profile back rather than a pin. Rebuilding one costs twenty
/// seconds of satellite and reanalysis calls, the app already holds it, and
/// posting it guarantees the advice describes the reading on screen rather
/// than a fresher one the farmer has not seen.
library;

import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/config.dart';
import '../../field/domain/field_profile.dart';
import '../domain/advisory.dart';

class M1Exception implements Exception {
  const M1Exception(this.message);
  final String message;
  @override
  String toString() => 'M1Exception: $message';
}

class M1Client {
  M1Client({http.Client? client, String? endpoint})
      : _client = client ?? http.Client(),
        _endpoint = endpoint ?? AppConfig.m1Endpoint;

  final http.Client _client;
  final String _endpoint;

  Future<Advisory> advise({
    required FieldProfile profile,
    String language = 'en',
    Duration timeout = const Duration(seconds: 30),
  }) async {
    final body = jsonEncode({
      'profile': profile.toJson(),
      'language': language,
      'sowingDate': ?profile.sowingDate,
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
      throw M1Exception('could not reach M1 at $_endpoint ($error)');
    }

    if (response.statusCode != 200) {
      throw M1Exception('M1 returned ${response.statusCode}: ${response.body}');
    }

    try {
      return Advisory.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>,
      );
    } catch (error) {
      throw M1Exception('could not parse the M1 response ($error)');
    }
  }

  void dispose() => _client.close();
}
