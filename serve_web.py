"""Static server for the built Flutter web app.

The dev server's module-split debug build kept being served from browser cache,
so a rebuilt app looked unchanged. This serves the release bundle with caching
switched off, which makes "did my change ship?" answerable by reloading.

    .venv/bin/python serve_web.py [port]
"""

from __future__ import annotations

import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parent / "app" / "build" / "web"
DEFAULT_PORT = 8080


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, fmt, *args):  # quieter than the default one-line-per-asset
        if "GET / " in (fmt % args) or "error" in (fmt % args).lower():
            super().log_message(fmt, *args)


def main() -> int:
    if not ROOT.exists():
        print(f"no build at {ROOT}", file=sys.stderr)
        print("run: flutter build web --release --dart-define=...", file=sys.stderr)
        return 1

    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    handler = partial(NoCacheHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"AgriSetu on http://127.0.0.1:{port}  (serving {ROOT})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
