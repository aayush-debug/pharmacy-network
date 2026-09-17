"""
Automated Test Suite for Phase 7: UDP Networking.
Tests:
1. UDP Server Discovery
2. UDP Low-Stock Datagram Alert Broadcasting
3. PySide6 Alerts GUI receiving and displaying real-time UDP alerts
"""

import os
import socket
import sys
import time
import unittest
from pathlib import Path

# Force Qt offscreen platform
os.environ["QT_QPA_PLATFORM"] = "offscreen"

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication
from backend.app.udp.alerts import UDPAlertBroadcaster
from backend.app.udp.discovery_server import DiscoveryServer
from frontend.gui.alerts import AlertsWidget
from frontend.network.tcp_client import PharmacyTCPClient
from frontend.network.udp_client import UDPAlertListener, discover_pharmacy_server

app = QApplication.instance() or QApplication(sys.argv)


def get_free_udp_port() -> int:
    """Finds an unused UDP port on localhost."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class TestUDPNetworking(unittest.TestCase):
    def test_01_udp_discovery(self):
        """
        Verify 1: UDP Discovery.
        Client sends 'DISCOVER_PHARMACY_SERVER' datagram,
        Server replies with SERVER_INFO containing tcp_port and http_port.
        """
        disc_port = get_free_udp_port()
        server = DiscoveryServer(
            host="127.0.0.1",
            port=disc_port,
            tcp_port=5000,
            http_port=8000,
        )
        server.start(blocking=False)
        time.sleep(0.1)

        try:
            info = discover_pharmacy_server(discovery_host="127.0.0.1", discovery_port=disc_port, timeout=2.0)
            self.assertIsNotNone(info, "Discovery probe timed out")
            self.assertEqual(info.get("type"), "SERVER_INFO")
            self.assertEqual(info.get("tcp_port"), 5000)
            self.assertEqual(info.get("http_port"), 8000)
            self.assertIn("Pharmacy Stock Network", info.get("server_name", ""))
        finally:
            server.stop()

    def test_02_udp_low_stock_broadcast(self):
        """
        Verify 2: UDP Low-Stock Alert.
        Broadcaster transmits a LOW_STOCK datagram, listener receives and parses it.
        """
        alert_port = get_free_udp_port()
        received_alerts = []

        def on_alert(data):
            received_alerts.append(data)

        listener = UDPAlertListener(listen_host="127.0.0.1", listen_port=alert_port, on_alert_received=on_alert)
        listener.start()
        time.sleep(0.1)

        broadcaster = UDPAlertBroadcaster(broadcast_host="127.0.0.1", broadcast_port=alert_port)

        try:
            sent_payload = broadcaster.send_low_stock_alert(
                medicine="Paracetamol 500mg",
                pharmacy="City Health Central",
                stock=3,
                minimum=10,
                target_port=alert_port,
            )

            # Wait for listener to receive datagram packet
            for _ in range(20):
                if received_alerts:
                    break
                time.sleep(0.05)

            self.assertEqual(len(received_alerts), 1)
            alert = received_alerts[0]
            self.assertEqual(alert.get("type"), "LOW_STOCK")
            self.assertEqual(alert.get("medicine"), "Paracetamol 500mg")
            self.assertEqual(alert.get("pharmacy"), "City Health Central")
            self.assertEqual(alert.get("stock"), 3)
            self.assertEqual(alert.get("minimum"), 10)
        finally:
            listener.stop()

    def test_03_gui_receiving_and_displaying_alert(self):
        """
        Verify 3: GUI receiving and displaying real-time UDP alerts.
        AlertsWidget starts UDP listener on port; broadcaster sends datagram;
        Qt signal fires and populates the live push alert table.
        """
        alert_port = get_free_udp_port()
        dummy_tcp_client = PharmacyTCPClient()

        alerts_widget = AlertsWidget(client=dummy_tcp_client, udp_port=alert_port)
        alerts_widget.show()
        time.sleep(0.1)

        broadcaster = UDPAlertBroadcaster(broadcast_host="127.0.0.1", broadcast_port=alert_port)

        try:
            self.assertEqual(alerts_widget.live_table.rowCount(), 0)

            # Send a real-time UDP alert datagram
            broadcaster.send_low_stock_alert(
                medicine="Amoxicillin 500mg",
                pharmacy="Metro Care Chemist",
                stock=2,
                minimum=10,
                target_port=alert_port,
            )

            # Process Qt event loop to dispatch Signal to main thread
            for _ in range(30):
                app.processEvents()
                if alerts_widget.live_table.rowCount() > 0:
                    break
                time.sleep(0.05)

            # Verify table row was inserted dynamically via UDP push!
            self.assertEqual(alerts_widget.live_table.rowCount(), 1)
            self.assertEqual(alerts_widget.live_table.item(0, 1).text(), "Metro Care Chemist")
            self.assertEqual(alerts_widget.live_table.item(0, 2).text(), "Amoxicillin 500mg")
            self.assertEqual(alerts_widget.live_table.item(0, 3).text(), "2")
            self.assertEqual(alerts_widget.live_table.item(0, 4).text(), "10")
            self.assertEqual(alerts_widget.live_table.item(0, 5).text(), "UDP Datagram")

        finally:
            if alerts_widget._udp_listener:
                alerts_widget._udp_listener.stop()
            alerts_widget.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
