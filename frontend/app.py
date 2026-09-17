"""
Pharmacy Stock Query System — PySide6 Desktop Application Entrypoint.
Coordinates Login / Connection, Navigation Tabs, and Background TCP Socket Communication.
Strictly decoupled from SQLite and backend modules.
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from frontend.gui import (
    AlertsWidget,
    DashboardWidget,
    ExpiryAuditWidget,
    InventoryWidget,
    LoginWidget,
    OrdersWidget,
    SalesHistoryWidget,
    SearchWidget,
)
from frontend.gui.theme import apply_dark_theme
from frontend.gui.worker import NetworkWorker
from frontend.network.tcp_client import PharmacyTCPClient


class MainWindow(QMainWindow):
    """
    Main application window managing the Login screen,
    application tabs, and persistent status bar.
    """

    def __init__(self, client: PharmacyTCPClient):
        super().__init__()
        self.client = client
        self.setWindowTitle("Pharmacy Stock Query System — Client")
        self.resize(1060, 700)

        # Central stacked widget: 0 = Login, 1 = Main Tabs
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # 1. Login View
        self.login_view = LoginWidget(self.client)
        self.login_view.connection_successful.connect(self._on_connection_successful)
        self.stack.addWidget(self.login_view)

        # 2. Main Tabbed Application View
        self.main_app_view = QWidget()
        app_layout = QVBoxLayout(self.main_app_view)
        app_layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # Instantiate Tabs
        self.dashboard_tab = DashboardWidget(self.client)
        self.search_tab = SearchWidget(self.client)
        self.inventory_tab = InventoryWidget(self.client)
        self.orders_tab = OrdersWidget(self.client)
        self.alerts_tab = AlertsWidget(self.client)
        self.expiry_tab = ExpiryAuditWidget(self.client)
        self.sales_tab = SalesHistoryWidget(self.client)

        self.tabs.addTab(self.dashboard_tab, "📊 Dashboard")
        self.tabs.addTab(self.search_tab, "🔍 Medicine Search")
        self.tabs.addTab(self.inventory_tab, "📦 Inventory")
        self.tabs.addTab(self.orders_tab, "🛒 Orders")
        self.tabs.addTab(self.alerts_tab, "⚠️ Stock Alerts")
        self.tabs.addTab(self.expiry_tab, "⏳ Expiry Audit")
        self.tabs.addTab(self.sales_tab, "📑 Sales History")

        # When tabs change, reload the corresponding view
        self.tabs.currentChanged.connect(self._on_tab_changed)

        app_layout.addWidget(self.tabs)
        self.stack.addWidget(self.main_app_view)

        # Status Bar
        self._init_statusbar()

    def _init_statusbar(self) -> None:
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        self.status_icon = QLabel("○")
        self.status_icon.setStyleSheet("color: #f87171; font-size: 14px; font-weight: bold;")
        self.status_text = QLabel("Disconnected")
        self.status_text.setStyleSheet("color: #94a3b8;")

        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setStyleSheet(
            "background-color: #334155; color: #f8fafc; padding: 3px 10px; font-size: 11px; border-radius: 4px; border: 1px solid #475569;"
        )
        self.disconnect_btn.clicked.connect(self._on_disconnect_clicked)
        self.disconnect_btn.setVisible(False)

        self.statusbar.addWidget(self.status_icon)
        self.statusbar.addWidget(self.status_text)
        self.statusbar.addPermanentWidget(self.disconnect_btn)

    def _on_connection_successful(self, host: str, port: int) -> None:
        """Invoked when the Login screen successfully performs TCP 3-way handshake & PING."""
        self.status_icon.setText("●")
        self.status_icon.setStyleSheet("color: #4ade80; font-size: 14px; font-weight: bold;")
        self.status_text.setText(f"Connected to TCP Server at {host}:{port}")
        self.status_text.setStyleSheet("color: #f8fafc; font-weight: 500;")
        self.disconnect_btn.setVisible(True)

        # Switch from Login view to Main App Tabs
        self.stack.setCurrentIndex(1)

        # Load initial dashboard metrics
        self.dashboard_tab.load_metrics()

    def _on_tab_changed(self, index: int) -> None:
        """Trigger view reloads when tabs are selected."""
        if not self.client.is_connected():
            return
        if index == 0:
            self.dashboard_tab.load_metrics()
        elif index == 2:
            self.inventory_tab.reload_data()
        elif index == 3:
            self.orders_tab.reload_data()
        elif index == 4:
            self.alerts_tab.reload_alerts()
        elif index == 5:
            self.expiry_tab.reload_audit()
        elif index == 6:
            self.sales_tab.reload_sales()

    def _on_disconnect_clicked(self) -> None:
        """Closes TCP socket, clears background tasks, and returns to Login view."""
        self.client.disconnect()
        NetworkWorker.shutdown_all(timeout_ms=300)
        self.status_icon.setText("○")
        self.status_icon.setStyleSheet("color: #f87171; font-size: 14px; font-weight: bold;")
        self.status_text.setText("Disconnected from server")
        self.status_text.setStyleSheet("color: #94a3b8;")
        self.disconnect_btn.setVisible(False)
        self.stack.setCurrentIndex(0)

    def closeEvent(self, event) -> None:
        """Ensure clean shutdown when the user exits the desktop app."""
        try:
            # 1. Stop background UDP datagram listener
            if hasattr(self, "alerts_tab") and hasattr(self.alerts_tab, "_udp_listener"):
                if self.alerts_tab._udp_listener:
                    self.alerts_tab._udp_listener.stop()

            # 2. Disconnect TCP socket (immediately terminates any pending socket I/O)
            self.client.disconnect()

            # 3. Cleanly wait for any in-flight background worker threads
            NetworkWorker.shutdown_all(timeout_ms=500)
        except Exception:
            pass
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Pharmacy Stock Query Client")
    apply_dark_theme(app)

    client = PharmacyTCPClient()
    window = MainWindow(client)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
