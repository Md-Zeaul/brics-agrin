/// Web implementation: inject the Maps JavaScript SDK on demand.
library;

import 'dart:async';
import 'dart:js_interop';

import 'package:web/web.dart' as web;

const String _scriptId = 'agrisetu-google-maps-sdk';

Future<bool>? _pending;

/// Load the Maps JS SDK once, returning whether it is ready to use.
///
/// Failure is reported rather than thrown so a bad or rate-limited key
/// degrades to the schematic map instead of blanking the screen.
Future<bool> ensureMapsLoaded(String apiKey) {
  if (apiKey.isEmpty) return Future.value(false);
  return _pending ??= _load(apiKey);
}

Future<bool> _load(String apiKey) {
  if (web.document.getElementById(_scriptId) != null) {
    return Future.value(true);
  }

  final completer = Completer<bool>();
  final script = web.document.createElement('script') as web.HTMLScriptElement
    ..id = _scriptId
    ..src = 'https://maps.googleapis.com/maps/api/js?key=$apiKey'
    ..async = true
    ..defer = true;

  script.onload = ((web.Event _) {
    if (!completer.isCompleted) completer.complete(true);
  }).toJS;

  script.onerror = ((web.Event _) {
    if (!completer.isCompleted) completer.complete(false);
  }).toJS;

  web.document.head!.appendChild(script);

  // Never hang the field-capture screen on a slow or blocked CDN.
  return completer.future.timeout(
    const Duration(seconds: 10),
    onTimeout: () => false,
  );
}
