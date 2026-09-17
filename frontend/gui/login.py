"""
Login / Connection Screen for PySide6 Desktop GUI.
Prompts for Server IP and Port, and verifies connection over TCP using PING.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from frontend.gui.worker import NetworkWorker
from frontend.network import config
from frontend.network.tcp_client import PharmacyTCPClient


class LoginWidget(QWidget):
    """
    Connection view allowing the user to configure and connect to the backend server.
    Emits connection_successful when a TCP socket connection and PING succeed.
    """
    connection_successful = Signal(str, int)

    def __init__(self, client: PharmacyTCPClient, parent=None):
        super().__init__(parent)
        self.client = client
        self._worker: NetworkWorker | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        # Title / Header
        title_label = QLabel("Pharmacy Stock Query System")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 5px; color: #f8fafc;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        subtitle_label = QLabel("Client-Server Network Connection")
        subtitle_label.setStyleSheet("font-size: 13px; color: #94a3b8; margin-bottom: 20px;")
        subtitle_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle_label)

        # Form fields
        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.ip_input = QLineEdit(self.client.host or config.TCP_SERVER_HOST)
        self.ip_input.setPlaceholderText("e.g., 127.0.0.1")
        form_layout.addRow("Server IP Address:", self.ip_input)

        self.port_input = QLineEdit(str(self.client.port or config.TCP_SERVER_PORT))
        self.port_input.setPlaceholderText("e.g., 5000")
        form_layout.addRow("TCP Port Number:", self.port_input)

        layout.addLayout(form_layout)

        # Buttons Layout (Auto-Discover UDP & Connect TCP)
        btn_layout = QHBoxLayout()

        self.discover_btn = QPushButton("🔍 Auto-Discover Server (UDP)")
        self.discover_btn.setStyleSheet(
            "padding: 8px 12px; font-weight: bold; background-color: #242424; color: white; border-radius: 4px; border: 1px solid #383838;"
        )
        self.discover_btn.clicked.connect(self._on_discover_clicked)
        btn_layout.addWidget(self.discover_btn)

        self.connect_btn = QPushButton("Connect via TCP")
        self.connect_btn.setStyleSheet(
            "padding: 8px 16px; font-weight: bold; background-color: #16a34a; color: white; border-radius: 4px; border: none;"
        )
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        btn_layout.addWidget(self.connect_btn)

        layout.addLayout(btn_layout)

        # Status label
        self.status_label = QLabel("Status: Disconnected")
        self.status_label.setStyleSheet("margin-top: 10px; color: #94a3b8;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

    def _on_discover_clicked(self) -> None:
        """Sends UDP broadcast probe to find server TCP port dynamically."""
        from frontend.network.udp_client import discover_pharmacy_server

        self.discover_btn.setEnabled(False)
        self.status_label.setText("Broadcasting UDP discovery request on port 5001...")
        self.status_label.setStyleSheet("margin-top: 10px; color: #c084fc;")

        def do_discover():
            return discover_pharmacy_server()

        self._discover_worker = NetworkWorker(do_discover)
        self._discover_worker.result_ready.connect(self._on_discover_success)
        self._discover_worker.error_occurred.connect(
            lambda err: self._on_discover_failed("Discovery error: " + err)
        )
        self._discover_worker.start()

    def _on_discover_success(self, info: dict | None) -> None:
        self.discover_btn.setEnabled(True)
        if not info:
            self._on_discover_failed("No pharmacy server responded to UDP probe on port 5001.")
            return

        discovered_ip = info.get("tcp_host", "127.0.0.1")
        discovered_port = info.get("tcp_port", 5000)

        self.ip_input.setText(discovered_ip)
        self.port_input.setText(str(discovered_port))
        self.status_label.setText(
            f"Discovered: '{info.get('server_name')}' (TCP Port {discovered_port})"
        )
        self.status_label.setStyleSheet("margin-top: 10px; color: #4ade80; font-weight: bold;")
        QMessageBox.information(
            self,
            "Server Discovered via UDP",
            f"Found: {info.get('server_name')}\n"
            f"IP: {discovered_ip}\n"
            f"Discovered TCP Port: {discovered_port}\n"
            f"HTTP Port: {info.get('http_port')}\n\n"
            "Ready to connect over TCP!",
        )

    def _on_discover_failed(self, msg: str) -> None:
        self.discover_btn.setEnabled(True)
        self.status_label.setText("Discovery timed out")
        self.status_label.setStyleSheet("margin-top: 10px; color: #fb923c;")
        QMessageBox.warning(self, "Discovery Timeout", f"{msg}\n\nYou can still enter IP and Port manually.")

    def _on_connect_clicked(self) -> None:
        host = self.ip_input.text().strip()
        port_str = self.port_input.text().strip()

        if not host:
            QMessageBox.warning(self, "Input Error", "Please enter a valid Server IP Address.")
            return

        try:
            port = int(port_str)
            if not (1 <= port <= 65535):
                raise ValueError()
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Port must be an integer between 1 and 65535.")
            return

        self.connect_btn.setEnabled(False)
        self.status_label.setText("Connecting and verifying PING...")
        self.status_label.setStyleSheet("margin-top: 10px; color: #38bdf8;")

        # Update client host and port
        self.client.host = host
        self.client.port = port
        self.client.disconnect()

        def do_connect_and_ping():
            self.client.connect()
            return self.client.ping()

        # Non-blocking connection worker
        self._worker = NetworkWorker(do_connect_and_ping)
        self._worker.result_ready.connect(lambda resp: self._on_connect_success(host, port, resp))
        self._worker.error_occurred.connect(self._on_connect_failed)
        self._worker.start()

    def _on_connect_success(self, host: str, port: int, resp: dict) -> None:
        self.connect_btn.setEnabled(True)
        self.status_label.setText(f"Connected to {host}:{port} (Server PING: OK)")
        self.status_label.setStyleSheet("margin-top: 10px; color: #4ade80; font-weight: bold;")
        self.connection_successful.emit(host, port)

    def _on_connect_failed(self, error_msg: str) -> None:
        self.connect_btn.setEnabled(True)
        self.status_label.setText("Connection Failed")
        self.status_label.setStyleSheet("margin-top: 10px; color: #f87171; font-weight: bold;")
        QMessageBox.critical(
            self,
            "Connection Error",
            f"Could not establish TCP connection to {self.client.host}:{self.client.port}.\n\n"
            f"Details: {error_msg}\n\n"
            "Ensure the backend TCP server is running:\n"
            "  python3 -m backend.app.tcp.server",
        )
