"""
HTTP Server Implementation.
Implements a multi-threaded HTTP REST API server using Python's standard library
'http.server.ThreadingHTTPServer' and 'http.server.BaseHTTPRequestHandler'.

Layer 7 Protocol: HTTP/1.1
Transport: Layer 4 TCP (Stream Socket)
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from typing import Any
from backend.app import config
from backend.app.http.routes import dispatch_route


class PharmacyHTTPRequestHandler(BaseHTTPRequestHandler):
    """
    Standard library HTTP request handler for the Pharmacy Stock Query REST API.
    Dispatches GET requests to the service layer and returns JSON responses.
    """

    server_version = "PharmacyStockHTTP/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        """Custom formatted log message for clarity and cleaner test outputs."""
        print(f"[HTTP Server] {self.client_address[0]} - \"{args[0]}\"")

    def _send_json_response(self, status_code: int, data: Any) -> None:
        """Encodes python dictionary or list to JSON bytes and writes to socket."""
        try:
            body = json.dumps(data, indent=2, default=str).encode("utf-8")
        except Exception as err:
            status_code = 500
            body = json.dumps(
                {"error": "JSON Serialization Error", "details": str(err)}
            ).encode("utf-8")

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        """Handles HTTP GET requests."""
        db_path = getattr(self.server, "db_path", None)
        status_code, response_data = dispatch_route(self.path, db_path=db_path)
        self._send_json_response(status_code, response_data)

    def do_POST(self) -> None:
        """Handles HTTP POST requests (Method Not Allowed for this read API)."""
        self._send_json_response(
            405,
            {
                "error": "Method Not Allowed",
                "message": "POST method is not supported on this endpoint.",
            },
        )

    def do_PUT(self) -> None:
        """Handles HTTP PUT requests (Method Not Allowed)."""
        self._send_json_response(
            405,
            {
                "error": "Method Not Allowed",
                "message": "PUT method is not supported on this endpoint.",
            },
        )

    def do_DELETE(self) -> None:
        """Handles HTTP DELETE requests (Method Not Allowed)."""
        self._send_json_response(
            405,
            {
                "error": "Method Not Allowed",
                "message": "DELETE method is not supported on this endpoint.",
            },
        )


class PharmacyHTTPServer:
    """
    HTTP REST API Server wrapper managing lifecycle and background thread execution.
    Uses ThreadingHTTPServer to handle requests concurrently.
    """

    def __init__(
        self,
        host: str = config.HTTP_HOST,
        port: int = config.HTTP_PORT,
        db_path: Path | str | None = None,
    ):
        self.host = host
        self.port = port
        self.db_path = db_path
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.is_running = False

    def start(self, blocking: bool = True) -> None:
        """Starts the HTTP server listening on configured host and port."""
        self._httpd = ThreadingHTTPServer((self.host, self.port), PharmacyHTTPRequestHandler)
        # Attach db_path so handler instances have access
        self._httpd.db_path = self.db_path  # type: ignore[attr-defined]

        # Update port in case port 0 (ephemeral) was requested
        self.port = self._httpd.server_address[1]
        self.is_running = True

        print(f"[HTTP Server] Listening on http://{self.host}:{self.port} (HTTP/1.1 over TCP)")

        if blocking:
            try:
                self._httpd.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                self.stop()
        else:
            self._thread = threading.Thread(
                target=self._httpd.serve_forever,
                name="PharmacyHTTPServerThread",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        """Stops the HTTP server and frees the port."""
        self.is_running = False
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        print(f"[HTTP Server] Stopped on http://{self.host}:{self.port}")


if __name__ == "__main__":
    import signal
    import sys

    server = PharmacyHTTPServer()

    def handle_sigint(sig, frame):
        print("\n[HTTP Server] Shutting down...")
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)
    print("=== Pharmacy Network HTTP REST API Server ===")
    print(f"Base URL: http://{config.HTTP_HOST}:{config.HTTP_PORT}")
    print("Press Ctrl+C to stop.")
    server.start(blocking=True)
