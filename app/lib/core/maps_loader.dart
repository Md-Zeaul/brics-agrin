/// Loads the Google Maps SDK, if this platform and build have one.
///
/// The key is a build-time define rather than a literal in `web/index.html`,
/// so it never lands in source control. On web that means injecting the Maps
/// JS SDK at runtime; on Android/iOS the native SDK reads the key from the
/// platform manifest instead.
library;

export 'maps_loader_stub.dart'
    if (dart.library.js_interop) 'maps_loader_web.dart';
