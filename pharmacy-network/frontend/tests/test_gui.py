"""
Automated GUI Tests for PySide6 Desktop Application.
Runs headlessly using QT_QPA_PLATFORM=offscreen.
Verifies widget creation, signals, and end-to-end integration over TCP socket.
"""

import os
import socket
import sys
import tempfile
import time
import unittest
from pathlib import Path

# Force Qt offscreen platform for headless test execution
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Ensure project root is on sys.path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication
from backend.app.database.seed import seed_database
from backend.app.tcp.server import TCPServer
from frontend.app import MainWindow
from frontend.gui import (
    AlertsWidget,
    DashboardWidget,
    InventoryWidget,
    LoginWidget,
    OrdersWidget,
    SearchWidget,
)
from frontend.network.tcp_client import PharmacyTCPClient

app = QApplication.instance() or QApplication(sys.argv)


def wait_for_worker(worker, timeout_sec: float = 3.0):
    """Helper to process Qt events until a QThread worker finishes."""
    if not worker:
        return
    start = time.time()
    while worker.isRunning() and (time.time() - start < timeout_sec):
        app.processEvents()
        time.sleep(0.02)
    worker.wait(1000)
    app.processEvents()


class TestGUIComponents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Spin up backend TCP server on a free port."""
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.test_db_path = Path(cls.temp_dir.name) / "test_gui.db"
        seed_database(cls.test_db_path)

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        cls.port = s.getsockname()[1]
        s.close()

        cls.server = TCPServer(host="127.0.0.1", port=cls.port, db_path=cls.test_db_path)
        cls.server.start(blocking=False)
        time.sleep(0.15)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        cls.temp_dir.cleanup()

    def setUp(self):
        self.client = PharmacyTCPClient(host="127.0.0.1", port=self.port)

    def tearDown(self):
        self.client.disconnect()

    def test_login_widget_success(self):
        """Test LoginWidget connection and signal emission."""
        login = LoginWidget(self.client)
        login.ip_input.setText("127.0.0.1")
        login.port_input.setText(str(self.port))

        received_signal = []
        login.connection_successful.connect(lambda h, p: received_signal.append((h, p)))
        login._on_connect_clicked()

        wait_for_worker(login._worker)

        self.assertEqual(len(received_signal), 1)
        self.assertEqual(received_signal[0], ("127.0.0.1", self.port))
        self.assertIn("Connected", login.status_label.text())

    def test_search_widget_flow(self):
        """Test SearchWidget searching medicines and populating availability."""
        self.client.connect()
        search_view = SearchWidget(self.client)
        search_view.search_input.setText("Paracip")
        search_view.do_search()

        wait_for_worker(search_view._search_worker)
        self.assertEqual(search_view.results_table.rowCount(), 1)
        self.assertEqual(search_view.results_table.item(0, 1).text(), "Paracip 500")

        # Wait for stock worker
        wait_for_worker(search_view._stock_worker)
        self.assertEqual(search_view.stock_table.rowCount(), 2)
        self.assertEqual(search_view.stock_table.item(0, 0).text(), "City Health Central")

    def test_dashboard_widget_metrics(self):
        """Test DashboardWidget loading metrics over TCP."""
        self.client.connect()
        dash = DashboardWidget(self.client)
        dash.load_metrics()

        wait_for_worker(dash._worker)
        self.assertEqual(dash.card_medicines.val_lbl.text(), "5")
        self.assertEqual(dash.card_pharmacies.val_lbl.text(), "2")
        self.assertEqual(dash.card_low_stock.val_lbl.text(), "1")

    def test_inventory_widget_reload(self):
        """Test InventoryWidget populating dropdowns and stock table."""
        self.client.connect()
        inv = InventoryWidget(self.client)
        inv.reload_data()

        wait_for_worker(inv._worker)
        self.assertEqual(inv.pharmacy_combo.count(), 2)
        self.assertEqual(inv.medicine_combo.count(), 5)
        self.assertGreaterEqual(inv.table.rowCount(), 1)

    def test_orders_widget_reload(self):
        """Test OrdersWidget loading combo boxes and history."""
        self.client.connect()
        orders = OrdersWidget(self.client)
        orders.reload_data()

        wait_for_worker(orders._worker)
        self.assertEqual(orders.pharmacy_combo.count(), 2)
        self.assertEqual(orders.medicine_combo.count(), 5)

    def test_alerts_widget_reload(self):
        """Test AlertsWidget scanning for low-stock alerts."""
        self.client.connect()
        alerts = AlertsWidget(self.client, udp_port=0)
        try:
            alerts.reload_alerts()
            wait_for_worker(alerts._worker)
            self.assertEqual(alerts.alerts_table.rowCount(), 1)
            self.assertEqual(alerts.alerts_table.item(0, 2).text(), "Mox 500")
        finally:
            alerts.close()

    def test_main_window_transitions(self):
        """Test MainWindow stack transitions between login and app views."""
        main_win = MainWindow(self.client)
        main_win.show()
        self.assertEqual(main_win.stack.currentIndex(), 0)  # Login view

        # Simulate successful connection
        main_win._on_connection_successful("127.0.0.1", self.port)
        wait_for_worker(main_win.dashboard_tab._worker)

        self.assertEqual(main_win.stack.currentIndex(), 1)  # Tab view
        self.assertFalse(main_win.disconnect_btn.isHidden())

        # Simulate disconnect
        main_win._on_disconnect_clicked()
        self.assertEqual(main_win.stack.currentIndex(), 0)  # Back to Login
        self.assertTrue(main_win.disconnect_btn.isHidden())
        main_win.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
