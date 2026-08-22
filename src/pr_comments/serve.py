"""Serve the generated dashboard over localhost."""

from __future__ import annotations

import functools
import http.server
import socketserver
from pathlib import Path


class _Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        print("[%s] %s" % (self.log_date_time_string(), format % args))


class _Server(socketserver.TCPServer):
    allow_reuse_address = True


def make_server(directory: Path, host: str = "127.0.0.1", port: int = 8765) -> socketserver.TCPServer:
    directory = directory.resolve()
    dashboard = directory / "dashboard.html"
    if not dashboard.is_file():
        raise SystemExit(f"no dashboard.html in {directory}. Run `pr-comments extract` first.")
    handler = functools.partial(_Handler, directory=str(directory))
    return _Server((host, port), handler)


def serve(directory: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    with make_server(directory, host=host, port=port) as httpd:
        bound_host, bound_port = httpd.server_address[:2]
        print(f"Review dashboard: http://{bound_host}:{bound_port}/dashboard.html")
        print(f"Serving {directory.resolve()}  (Ctrl+C to stop)")
        httpd.serve_forever()
