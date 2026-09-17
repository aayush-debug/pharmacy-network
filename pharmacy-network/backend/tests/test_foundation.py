"""
Verification tests for Phase 1: Project Foundation.
Validates directory structure, configuration defaults, and Python environment.
"""

import socket
import unittest
from pathlib import Path
import sys

# Ensure backend package can be imported
current_dir = Path(__file__).resolve().parent
backend_dir = current_dir.parent
if str(backend_dir.parent) not in sys.path:
    sys.path.insert(0, str(backend_dir.parent))

from backend.app import config


class TestProjectFoundation(unittest.TestCase):
    def test_directory_structure_exists(self):
        """Verify that all required backend directories exist."""
        self.assertTrue(config.BASE_DIR.exists(), "backend directory should exist")
        self.assertTrue(config.DATA_RAW_DIR.exists(), "data/raw directory should exist")
        self.assertTrue(config.DATA_PROCESSED_DIR.exists(), "data/processed directory should exist")
        self.assertTrue(config.REPORTS_DIR.exists(), "reports directory should exist")

    def test_default_ports_are_valid(self):
        """Verify that port configurations are valid port numbers."""
        for port_name, port_val in [
            ("TCP_PORT", config.TCP_PORT),
            ("UDP_PORT", config.UDP_PORT),
            ("HTTP_PORT", config.HTTP_PORT),
            ("FTP_PORT", config.FTP_PORT),
            ("SMTP_PORT", config.SMTP_PORT),
        ]:
            self.assertIsInstance(port_val, int, f"{port_name} must be an integer")
            self.assertGreater(port_val, 0, f"{port_name} must be > 0")
            self.assertLessEqual(port_val, 65535, f"{port_name} must be <= 65535")

    def test_ip_addresses_are_valid(self):
        """Verify that host configurations are valid IP addresses."""
        for host_name, host_val in [
            ("TCP_HOST", config.TCP_HOST),
            ("UDP_HOST", config.UDP_HOST),
            ("HTTP_HOST", config.HTTP_HOST),
            ("FTP_HOST", config.FTP_HOST),
        ]:
            # socket.inet_aton checks if host_val is a valid IPv4 string
            try:
                socket.inet_aton(host_val)
            except OSError:
                self.fail(f"{host_name} ({host_val}) is not a valid IPv4 address")

    def test_stdlib_networking_modules(self):
        """Verify that all standard-library modules required for future phases are available."""
        import http.server
        import smtplib
        import sqlite3
        import threading
        self.assertTrue(hasattr(socket, "AF_INET"))
        self.assertTrue(hasattr(socket, "SOCK_STREAM"))  # TCP
        self.assertTrue(hasattr(socket, "SOCK_DGRAM"))   # UDP
        self.assertTrue(hasattr(threading, "Thread"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
