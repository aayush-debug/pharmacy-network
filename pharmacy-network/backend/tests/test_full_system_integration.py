"""
Automated End-to-End Test Suite for Phase 12: Full System Integration.
Verifies the complete 6-protocol architecture of the Pharmacy Stock Query System:
1. TCP/IP Socket Protocol (Interactive client-server requests and order processing)
2. UDP Discovery & Datagram Alerting (Server discovery & real-time low-stock push)
3. HTTP/1.1 REST API (Administrative inspection of catalog, inventory, and orders)
4. FTP File Transfer (Bulk CSV report generation and dual-channel retrieval)
5. SMTP Email (MIME order confirmations and low-stock administrator alerts)
6. SQLite Business Layer (Encapsulated transactions, strict isolation from frontend)

Tests 1 through 12 correspond directly to the Phase 12 verification criteria.
"""

import json
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.database.connection import get_connection
from backend.app.ftp import reports
from backend.app.ftp.server import PharmacyFTPServer
from backend.app.http.server import PharmacyHTTPServer
from backend.app.smtp.mailer import default_mailer
from backend.app.tcp.server import TCPServer
from backend.app.udp.discovery_server import DiscoveryServer
from frontend.network.ftp_client import PharmacyFTPClient
from frontend.network.tcp_client import PharmacyTCPClient
from frontend.network.udp_client import UDPAlertListener, discover_pharmacy_server


class TestFullSystemIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 1. Setup isolated temporary directory for test database and reports
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.temp_path = Path(cls.temp_dir.name)
        cls.test_db = cls.temp_path / "integration_pharmacy.db"
        cls.reports_dir = cls.temp_path / "reports"
        cls.reports_dir.mkdir(parents=True, exist_ok=True)
        cls.downloads_dir = cls.temp_path / "downloads"
        cls.downloads_dir.mkdir(parents=True, exist_ok=True)

        # Copy master production database to test database
        master_db = project_root / "backend" / "data" / "processed" / "pharmacy.db"
        if not master_db.is_file():
            raise FileNotFoundError(f"Master database not found at {master_db}")
        shutil.copyfile(master_db, cls.test_db)

        # 2. Reset SMTP outbox
        default_mailer.outbox.clear()

        # 3. Start UDP Alert Listener on port 5002
        cls.udp_listener = UDPAlertListener(listen_host="127.0.0.1", listen_port=5002)
        cls.udp_listener.start()

        # 4. Start TCP Server on ephemeral port (port 0)
        cls.tcp_server = TCPServer(host="127.0.0.1", port=0, db_path=cls.test_db)
        cls.tcp_server.start(blocking=False)
        time.sleep(0.15)
        cls.tcp_port = cls.tcp_server.port

        # 5. Start HTTP Server on ephemeral port (port 0)
        cls.http_server = PharmacyHTTPServer(host="127.0.0.1", port=0, db_path=cls.test_db)
        cls.http_server.start(blocking=False)
        time.sleep(0.15)
        cls.http_port = cls.http_server.port
        cls.http_base_url = f"http://127.0.0.1:{cls.http_port}"

        # 6. Start UDP Discovery Server on ephemeral port
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("127.0.0.1", 0))
        cls.udp_disc_port = s.getsockname()[1]
        s.close()

        cls.discovery_server = DiscoveryServer(
            host="127.0.0.1",
            port=cls.udp_disc_port,
            tcp_port=cls.tcp_port,
            http_port=cls.http_port,
        )
        cls.discovery_server.start(blocking=False)

        # 7. Start FTP Server on ephemeral port (port 0)
        cls.ftp_user = "admin_test"
        cls.ftp_pass = "pass_test_123"
        cls.ftp_server = PharmacyFTPServer(
            host="127.0.0.1",
            port=0,
            user=cls.ftp_user,
            password=cls.ftp_pass,
            reports_dir=cls.reports_dir,
        )
        cls.ftp_server.start(blocking=False)
        time.sleep(0.15)
        cls.ftp_port = cls.ftp_server.port

        # 8. Shared TCP client for sequential E2E steps
        cls.tcp_client = PharmacyTCPClient(host="127.0.0.1", port=cls.tcp_port)

    @classmethod
    def tearDownClass(cls):
        # Stop all servers and listeners cleanly
        try:
            cls.tcp_client.disconnect()
        except Exception:
            pass

        try:
            cls.udp_listener.stop()
        except Exception:
            pass

        try:
            cls.discovery_server.stop()
        except Exception:
            pass

        try:
            cls.tcp_server.stop()
        except Exception:
            pass

        try:
            cls.http_server.stop()
        except Exception:
            pass

        try:
            cls.ftp_server.stop()
        except Exception:
            pass

        cls.temp_dir.cleanup()

    # =========================================================================
    # Architectural Invariant Verification
    # =========================================================================

    def test_00_architectural_isolation(self):
        """Verify that frontend source files NEVER import sqlite3 or execute SQL."""
        frontend_dir = project_root / "frontend"
        disallowed_patterns = ["import sqlite3", "from sqlite3", "sqlite3.connect"]

        for py_file in frontend_dir.rglob("*.py"):
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
                for pattern in disallowed_patterns:
                    self.assertNotIn(
                        pattern,
                        content,
                        f"Architectural violation: {py_file.name} contains '{pattern}'! "
                        "Frontend must never access SQLite directly.",
                    )

    # =========================================================================
    # TEST 1: Frontend connects to backend
    # =========================================================================

    def test_01_frontend_connects_to_backend(self):
        """TEST 1: Frontend establishes TCP connection and exchanges PING/PONG handshake."""
        self.tcp_client.connect()
        self.assertTrue(self.tcp_client.is_connected(), "TCP client should be connected to server.")

        ping_resp = self.tcp_client.ping()
        self.assertEqual(ping_resp.get("status"), "success")
        self.assertEqual(ping_resp.get("message"), "pong")

    # =========================================================================
    # TEST 2: Frontend searches a real imported medicine
    # =========================================================================

    def test_02_frontend_searches_real_medicine(self):
        """TEST 2: Frontend searches the real Hugging Face catalog for 'Augmentin'."""
        results = self.tcp_client.search_medicines("Augmentin")
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Search for 'Augmentin' should return catalog results.")

        # Ensure top match is Augmentin 625 Duo Tablet
        brand_names = [m.get("brand_name", "") for m in results]
        self.assertTrue(
            any("Augmentin" in name for name in brand_names),
            f"Expected 'Augmentin' in search results, got: {brand_names[:3]}",
        )

    # =========================================================================
    # TEST 3: Backend returns medicine information
    # =========================================================================

    def test_03_backend_returns_medicine_information(self):
        """TEST 3: Backend returns complete catalog metadata for medicine_id=1."""
        med = self.tcp_client.get_medicine(1)
        self.assertIsNotNone(med, "Medicine ID 1 should exist.")
        self.assertEqual(med["id"], 1)
        self.assertIn("Augmentin", med["brand_name"])
        self.assertEqual(med.get("primary_ingredient"), "Amoxycillin")
        self.assertIn("price_inr", med)
        self.assertIn("dosage_form", med)
        self.assertIn("manufacturer", med)

    # =========================================================================
    # TEST 4: Frontend checks pharmacy availability
    # =========================================================================

    def test_04_frontend_checks_pharmacy_availability(self):
        """TEST 4: Frontend queries network branches carrying Augmentin 625 Duo Tablet."""
        availability = self.tcp_client.find_pharmacies(medicine_id=1)
        self.assertIsInstance(availability, list)
        self.assertGreater(len(availability), 0, "Medicine 1 should be stocked across pharmacies.")

        branch = availability[0]
        self.assertIn("pharmacy_id", branch)
        self.assertIn("pharmacy_name", branch)
        self.assertIn("stock_quantity", branch)
        self.assertIn("minimum_stock", branch)
        self.assertIn("location", branch)

    # =========================================================================
    # TEST 5: Frontend places an order
    # =========================================================================

    def test_05_frontend_places_order(self):
        """
        TEST 5: Frontend places an order of quantity 15 for medicine 1 at pharmacy 1.
        (Initial stock: 28, minimum: 17. Ordering 15 will reduce stock to 13, crossing the threshold).
        """
        # Capture initial stock
        stock_info = self.tcp_client.check_stock(pharmacy_id=1, medicine_id=1)
        initial_stock = stock_info["stock_quantity"]
        self.assertEqual(initial_stock, 28, "Initial stock for Augmentin at pharmacy 1 should be 28.")

        order_dict = self.tcp_client.place_order(pharmacy_id=1, medicine_id=1, quantity=15)
        self.assertIsInstance(order_dict, dict)
        self.assertIn("order_id", order_dict)
        self.assertEqual(order_dict["pharmacy_id"], 1)
        self.assertEqual(order_dict["medicine_id"], 1)
        self.assertEqual(order_dict["quantity"], 15)
        self.assertEqual(order_dict["status"], "confirmed")
        self.assertEqual(order_dict["remaining_stock"], 13)
        self.assertTrue(order_dict["is_now_low_stock"], "Remaining stock (13) is <= minimum (17).")

        # Save order_id on test instance for subsequent tests
        TestFullSystemIntegration.placed_order_id = order_dict["order_id"]

    # =========================================================================
    # TEST 6: Stock changes correctly
    # =========================================================================

    def test_06_stock_changes_correctly(self):
        """TEST 6: Validates that inventory stock was deducted and order is retrievable."""
        # 1. Verify stock deduction
        stock_info = self.tcp_client.check_stock(pharmacy_id=1, medicine_id=1)
        self.assertEqual(stock_info["stock_quantity"], 13, "Stock should have decremented from 28 to 13.")

        # 2. Verify order retrieval via TCP
        order = self.tcp_client.get_order(self.placed_order_id)
        self.assertIsNotNone(order)
        self.assertEqual(order["order_id"], self.placed_order_id)
        self.assertEqual(order["quantity"], 15)
        self.assertEqual(order["status"], "confirmed")

    # =========================================================================
    # TEST 7: Low-stock condition generates UDP alert
    # =========================================================================

    def test_07_low_stock_generates_udp_alert(self):
        """
        TEST 7: Verifies that:
        1. Low-stock trigger from TEST 5 generated a real-time UDP datagram alert.
        2. UDP Server Discovery resolves active network ports.
        """
        # Allow brief moment for UDP packet propagation
        time.sleep(0.2)

        # 1. UDP Alert Listener verification
        self.assertGreater(
            len(self.udp_listener.received_alerts),
            0,
            "UDP Alert Listener should have received the LOW_STOCK datagram alert.",
        )
        alert = self.udp_listener.received_alerts[-1]
        self.assertEqual(alert.get("type"), "LOW_STOCK")
        self.assertIn("Augmentin", alert.get("medicine", ""))
        self.assertEqual(alert.get("pharmacy"), "City Health Central")
        self.assertEqual(alert.get("stock"), 13)
        self.assertEqual(alert.get("minimum"), 17)

        # 2. UDP Discovery Probe verification
        disc_info = discover_pharmacy_server(
            discovery_host="127.0.0.1",
            discovery_port=self.udp_disc_port,
            timeout=2.0,
        )
        self.assertIsNotNone(disc_info, "Discovery probe should receive server metadata.")
        self.assertEqual(disc_info.get("type"), "SERVER_INFO")
        self.assertEqual(disc_info.get("tcp_port"), self.tcp_port)
        self.assertEqual(disc_info.get("http_port"), self.http_port)

    # =========================================================================
    # TEST 8: Low-stock condition triggers SMTP notification
    # =========================================================================

    def test_08_low_stock_triggers_smtp_notification(self):
        """
        TEST 8: Verifies that the order placement triggered:
        1. An Order Confirmation email.
        2. An Urgent Low-Stock alert email to the admin.
        """
        self.assertGreaterEqual(
            len(default_mailer.outbox),
            2,
            "SMTP outbox should contain at least 2 messages (Order Confirmation + Low Stock Alert).",
        )

        subjects = [msg["Subject"] for msg in default_mailer.outbox]
        order_subject_found = any("Confirmation" in subj and "Augmentin" in subj for subj in subjects)
        low_stock_subject_found = any("[URGENT ALERT]" in subj and "Augmentin" in subj for subj in subjects)

        self.assertTrue(order_subject_found, f"Order confirmation email missing. Outbox subjects: {subjects}")
        self.assertTrue(low_stock_subject_found, f"Low stock alert email missing. Outbox subjects: {subjects}")

        # Check content of low-stock alert
        low_stock_msg = next(msg for msg in default_mailer.outbox if "[URGENT ALERT]" in msg["Subject"])
        content = low_stock_msg.get_content()
        self.assertIn("Current Stock:  13 units", content)
        self.assertIn("Minimum Stock:  17 units", content)
        self.assertIn("City Health Central", content)

    # =========================================================================
    # TEST 9: HTTP API returns medicine/order information
    # =========================================================================

    def test_09_http_api_returns_information(self):
        """
        TEST 9: Queries the HTTP REST API server:
        1. GET /api/medicines/1 -> returns medicine catalog record.
        2. GET /api/orders/<id> -> returns order placed in TEST 5.
        3. GET /api/inventory?pharmacy_id=1&low_stock=true -> returns Augmentin in low stock list.
        """
        # 1. GET /api/medicines/1
        url_med = f"{self.http_base_url}/api/medicines/1"
        with urllib.request.urlopen(url_med, timeout=5.0) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["id"], 1)
            self.assertIn("Augmentin", data["brand_name"])

        # 2. GET /api/orders/<id>
        url_order = f"{self.http_base_url}/api/orders/{self.placed_order_id}"
        with urllib.request.urlopen(url_order, timeout=5.0) as resp:
            self.assertEqual(resp.status, 200)
            order_data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(order_data["order_id"], self.placed_order_id)
            self.assertEqual(order_data["quantity"], 15)
            self.assertEqual(order_data["status"], "confirmed")

        # 3. GET /api/inventory?pharmacy_id=1&low_stock=true
        url_low = f"{self.http_base_url}/api/inventory?pharmacy_id=1&low_stock=true"
        with urllib.request.urlopen(url_low, timeout=5.0) as resp:
            self.assertEqual(resp.status, 200)
            low_items = json.loads(resp.read().decode("utf-8"))
            aug_item = next((item for item in low_items if item["medicine_id"] == 1), None)
            self.assertIsNotNone(aug_item, "Augmentin should now be reported as low-stock over HTTP.")
            self.assertEqual(aug_item["stock_quantity"], 13)

    # =========================================================================
    # TEST 10: Inventory report is generated
    # =========================================================================

    def test_10_inventory_report_generation(self):
        """TEST 10: Generates fresh CSV reports reflecting current database state."""
        report_files = reports.generate_all_reports(output_dir=self.reports_dir, db_path=self.test_db)
        self.assertIn("inventory", report_files)
        self.assertIn("orders", report_files)
        self.assertIn("low_stock", report_files)

        inv_csv = self.reports_dir / "inventory_report.csv"
        self.assertTrue(inv_csv.is_file(), "inventory_report.csv should be generated.")
        self.assertGreater(inv_csv.stat().st_size, 0, "Report should not be empty.")

        # Verify content includes updated stock (13) for medicine 1 at pharmacy 1
        import csv
        with open(inv_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            aug_row = next((r for r in rows if r["medicine_id"] == "1" and r["pharmacy_id"] == "1"), None)
            self.assertIsNotNone(aug_row, "Row for medicine 1 at pharmacy 1 should exist.")
            self.assertEqual(aug_row["stock_quantity"], "13")
            self.assertEqual(aug_row["is_low_stock"], "YES")

    # =========================================================================
    # TEST 11: Report can be transferred using FTP
    # =========================================================================

    def test_11_report_transferred_using_ftp(self):
        """
        TEST 11: Connects via PharmacyFTPClient, lists available reports,
        and downloads inventory_report.csv over the TCP data channel.
        """
        ftp_client = PharmacyFTPClient(
            host="127.0.0.1",
            port=self.ftp_port,
            user=self.ftp_user,
            password=self.ftp_pass,
            timeout=5.0,
        )
        ftp_client.connect()
        try:
            self.assertTrue(ftp_client.is_connected(), "FTP client should be connected.")

            file_list = ftp_client.list_reports()
            self.assertIn("inventory_report.csv", file_list)

            download_target = self.downloads_dir / "downloaded_inventory.csv"
            downloaded_path = ftp_client.download_report("inventory_report.csv", download_target)
            self.assertTrue(downloaded_path.is_file(), "Downloaded file must exist on client filesystem.")

            # Validate integrity against source file
            source_content = (self.reports_dir / "inventory_report.csv").read_bytes()
            downloaded_content = downloaded_path.read_bytes()
            self.assertEqual(
                source_content,
                downloaded_content,
                "FTP downloaded file must match server file byte-for-byte.",
            )
        finally:
            ftp_client.disconnect()

    # =========================================================================
    # TEST 12: Multiple TCP clients can connect concurrently
    # =========================================================================

    def test_12_concurrent_tcp_clients(self):
        """
        TEST 12: Spawns 5 concurrent TCP client threads executing PING, search,
        and stock checks simultaneously without deadlock or socket errors.
        """
        num_clients = 5
        errors: list[str] = []
        barrier = threading.Barrier(num_clients)

        def worker_routine(worker_id: int):
            try:
                client = PharmacyTCPClient(host="127.0.0.1", port=self.tcp_port, timeout=5.0)
                client.connect()

                # Synchronize all threads to fire requests concurrently
                barrier.wait(timeout=5.0)

                # 1. PING
                pong = client.ping()
                if pong.get("status") != "success":
                    errors.append(f"Worker {worker_id}: Invalid ping response")

                # 2. Search
                results = client.search_medicines("Augmentin")
                if not results:
                    errors.append(f"Worker {worker_id}: Empty search results")

                # 3. Stock Check
                stock = client.check_stock(pharmacy_id=1, medicine_id=1)
                if stock.get("stock_quantity") != 13:
                    errors.append(f"Worker {worker_id}: Unexpected stock value {stock}")

                client.disconnect()
            except Exception as exc:
                errors.append(f"Worker {worker_id} exception: {exc}")

        threads = [
            threading.Thread(target=worker_routine, args=(i,), name=f"ConcurrentWorker-{i}")
            for i in range(num_clients)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join(timeout=10.0)

        self.assertEqual(
            errors,
            [],
            f"Concurrent client execution encountered errors: {errors}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
