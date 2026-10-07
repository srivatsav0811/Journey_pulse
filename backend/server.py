"""
server.py
=========
Serves the JSON API (backend/api/routes.py) and the dashboard (frontend/)
from one process, using only the Python standard library.

    python -m backend.server            # http://127.0.0.1:8000
    python -m backend.server --open     # ...and open the browser when ready
    PORT=9000 python -m backend.server
"""

import json
import mimetypes
import sys
import time
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from . import config
from .api.routes import ROUTES, ApiError
from .services.workspace import Registry

REGISTRY = Registry()
MAX_BODY = 256 * 1024


class Handler(BaseHTTPRequestHandler):
    server_version = "JourneyPulse/1.0"

    def log_message(self, fmt, *args):  # quieter console: one line per API call
        if self.path.startswith("/api/"):
            sys.stderr.write(f"{time.strftime('%H:%M:%S')} {self.command} {self.path.split('?')[0]} {args[1] if len(args) > 1 else ''}\n")

    def _send(self, status, payload: bytes, ctype: str, cache: str = "no-store"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, status, obj):
        self._send(status, json.dumps(obj, allow_nan=False).encode(), "application/json; charset=utf-8")

    def _api(self, method):
        url = urlparse(self.path)
        handler = ROUTES.get((method, url.path))
        if handler is None:
            return self._json(404, {"error": f"no route {method} {url.path}"})
        query = {k: v[-1] for k, v in parse_qs(url.query).items()}
        body = {}
        if method == "POST":
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                return self._json(413, {"error": "request too large"})
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError
            except ValueError:
                return self._json(400, {"error": "body must be a JSON object"})
        try:
            self._json(200, handler(REGISTRY, query, body))
        except ApiError as exc:
            self._json(exc.status, {"error": exc.message})
        except Exception as exc:
            traceback.print_exc()
            self._json(500, {"error": f"{type(exc).__name__}: {exc}"})

    def _static(self):
        path = urlparse(self.path).path
        if path in ("", "/"):
            path = "/index.html"
        target = (config.FRONTEND_DIR / path.lstrip("/")).resolve()
        if config.FRONTEND_DIR.resolve() not in target.parents or not target.is_file():
            target = config.FRONTEND_DIR / "index.html"      # single-page app fallback
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        self._send(200, target.read_bytes(), ctype)

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self._api("GET")
        self._static()

    def do_POST(self):
        if self.path.startswith("/api/"):
            return self._api("POST")
        self._json(405, {"error": "POST only on /api/"})


def main():
    mimetypes.add_type("text/javascript", ".js")
    mimetypes.add_type("text/css", ".css")
    name = REGISTRY.default_name()
    print(f"Preparing dataset '{name}' (first run builds a cache, ~15 s)...")
    t0 = time.time()
    ws = REGISTRY.get(name)
    print(f"Ready in {time.time() - t0:.1f}s: {len(ws.labels)} monthly batches {ws.labels}; "
          f"advisor mode: {'Claude (' + config.ANTHROPIC_MODEL + ')' if config.ANTHROPIC_API_KEY else 'offline analyst'}")
    httpd = ThreadingHTTPServer((config.HOST, config.PORT), Handler)
    url = f"http://{config.HOST}:{config.PORT}"
    print(f"JourneyPulse running at {url}  (Ctrl+C to stop)")
    if "--open" in sys.argv:
        threading.Timer(0.6, webbrowser.open, args=(url,)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
