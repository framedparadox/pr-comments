"""Serve the generated dashboard over localhost."""

from __future__ import annotations

import http.server
import os
import socketserver
from pathlib import Path


class _Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        print("[%s] %s" % (self.log_date_time_string(), format % args))


def serve(directory: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    directory = directory.resolve()
    dashboard = directory / "dashboard.html"
    if not dashboard.is_file():
        raise SystemExit(f"no dashboard.html in {directory}. Run `pr-comments extract` first.")
    os.chdir(directory)
    with socketserver.TCPServer((host, port), _Handler) as httpd:
        print(f"Review dashboard: http://{host}:{port}/dashboard.html")
        print(f"Serving {directory}  (Ctrl+C to stop)")
        httpd.serve_forever()
