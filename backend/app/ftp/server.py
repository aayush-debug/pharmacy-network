"""
FTP Server Implementation using pyftpdlib.
Serves pharmacy CSV reports (inventory, orders, low-stock) over File Transfer Protocol (FTP).

Layer 7 Protocol: FTP
Transport: Layer 4 TCP (Dual-channel: Control channel port 21/2121 + Dynamic Data channel)
"""

import logging
from pathlib import Path
import threading
from typing import Any

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

from backend.app import config


class CustomFTPHandler(FTPHandler):
    """Custom FTP handler setting custom welcome banner."""
    banner = "Pharmacy Stock Network FTP Service Ready."

    def log(self, *args: Any, **kwargs: Any) -> None:
        """Custom logging suppressor."""
        pass


class PharmacyFTPServer:
    """
    FTP Server wrapping pyftpdlib.FTPServer.
    Allows starting asynchronously in a daemon thread or blocking in CLI.
    """

    def __init__(
        self,
        host: str = config.FTP_HOST,
        port: int = config.FTP_PORT,
        user: str = config.FTP_USER,
        password: str = config.FTP_PASS,
        reports_dir: Path | str | None = None,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.reports_dir = Path(reports_dir) if reports_dir else config.REPORTS_DIR
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        self._server: FTPServer | None = None
        self._thread: threading.Thread | None = None
        self.is_running = False

    def start(self, blocking: bool = True) -> None:
        """Configures authorizer, binds socket, and starts listening for FTP connections."""
        # 1. Authorizer - restricts permissions to reports directory
        authorizer = DummyAuthorizer()
        # elradfmwM:
        # e = change dir, l = list, r = retrieve (download)
        # a = append, d = delete, f = rename, m = make dir, w = write (upload), M = change mode
        authorizer.add_user(
            username=self.user,
            password=self.password,
            homedir=str(self.reports_dir),
            perm="elradfmwM",
        )

        # 2. Handler configuration
        handler = CustomFTPHandler
        handler.authorizer = authorizer

        # Configure passive ports (ephemeral range)
        handler.passive_ports = range(60000, 60100)

        # 3. Create FTP server instance
        self._server = FTPServer((self.host, self.port), handler)
        # In case port 0 (ephemeral) was requested, update self.port to actual port
        self.port = self._server.socket.getsockname()[1]
        self.is_running = True

        print(f"[FTP Server] Listening on ftp://{self.host}:{self.port} (Root: {self.reports_dir})")
        print(f"[FTP Server] User: '{self.user}' (Full read/write permissions)")

        if blocking:
            try:
                self._server.serve_forever()
            except (KeyboardInterrupt, SystemExit):
                pass
            finally:
                self.stop()
        else:
            self._thread = threading.Thread(
                target=self._run_loop,
                name="PharmacyFTPServerThread",
                daemon=True,
            )
            self._thread.start()

    def _run_loop(self) -> None:
        """Internal serve loop for non-blocking execution."""
        try:
            if self._server:
                self._server.serve_forever()
        except Exception:
            pass

    def stop(self) -> None:
        """Stops the FTP server and frees sockets."""
        self.is_running = False
        if self._server:
            try:
                self._server.close_all()
            except Exception:
                pass
            self._server = None
        print(f"[FTP Server] Stopped on ftp://{self.host}:{self.port}")


if __name__ == "__main__":
    import signal
    import sys
    from backend.app.ftp.reports import generate_all_reports

    print("=== Pharmacy Network FTP Server ===")
    # Ensure fresh reports exist prior to launch
    generate_all_reports()

    server = PharmacyFTPServer()

    def handle_sigint(sig, frame):
        print("\n[FTP Server] Shutting down...")
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)
    print(f"Server available at ftp://{config.FTP_HOST}:{config.FTP_PORT}")
    print(f"Credentials: {config.FTP_USER} / {config.FTP_PASS}")
    print("Press Ctrl+C to stop.")
    server.start(blocking=True)
