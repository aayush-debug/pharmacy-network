"""
Automated Test Suite for Phase 5: Frontend TCP Client.
Tests the 7-step client journey: Connect, PING, Search, Check Stock,
Place Order, Retrieve Order, and Disconnect, plus error handling.
"""

import socket
import tempfile
import time
import unittest
from pathlib import Path
import sys

# Ensure frontend and backend packages are on sys.path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.database.seed import seed_database
from backend.app.tcp.server import TCPServer
from frontend.network import ClientProtocolError, PharmacyTCPClient, ServerError
from frontend.network.protocol import decode_response, encode_request


class TestFrontendTCPClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Start a dedicated backend TCPServer on a dynamic port."""
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.test_db_path = Path(cls.temp_dir.name) / "test_frontend_tcp.db"
        seed_database(cls.test_db_path)

        # Allocate dynamic free port
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        cls.port = s.getsockname()[1]
        s.close()

        cls.server = TCPServer(host="127.0.0.1", port=cls.port, db_path=cls.test_db_path)
        cls.server.start(blocking=False)
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        cls.temp_dir.cleanup()

    def test_protocol_encoding_and_decoding(self):
        """Test NDJSON framing unit functions in protocol.py."""
        raw = encode_request("SEARCH_MEDICINE", query="Paracip")
        self.assertTrue(raw.endswith(b"\n"))
        self.assertIn(b'"action":"SEARCH_MEDICINE"', raw)
        self.assertIn(b'"query":"Paracip"', raw)

        parsed = decode_response('{"status":"success","message":"pong"}\n')
        self.assertEqual(parsed["status"], "success")
        self.assertEqual(parsed["message"], "pong")

        with self.assertRaises(ClientProtocolError):
            decode_response("NOT VALID JSON\n")

    def test_complete_7_step_client_journey(self):
        """
        Verify the required 7-step client journey:
        1. Connect
        2. PING
        3. Search medicine
        4. Check stock
        5. Place an order
        6. Retrieve order
        7. Disconnect
        """
        client = PharmacyTCPClient(host="127.0.0.1", port=self.port)

        # 1. Connect
        client.connect()
        self.assertTrue(client.is_connected())

        try:
            # 2. PING
            ping_resp = client.ping()
            self.assertEqual(ping_resp.get("status"), "success")
            self.assertEqual(ping_resp.get("message"), "pong")

            # 3. Search medicine
            search_results = client.search_medicines("Paracip")
            self.assertIsInstance(search_results, list)
            self.assertEqual(len(search_results), 1)
            med = search_results[0]
            self.assertEqual(med["brand_name"], "Paracip 500")
            med_id = med["id"]

            # 4. Check stock
            stock = client.check_stock(pharmacy_id=1, medicine_id=med_id)
            self.assertEqual(stock["stock_quantity"], 100)

            # Also check cross-pharmacy availability via find_pharmacies(med_id)
            avail = client.find_pharmacies(medicine_id=med_id)
            self.assertEqual(len(avail), 2)

            # 5. Place an order
            order = client.place_order(pharmacy_id=1, medicine_id=med_id, quantity=4)
            self.assertIsNotNone(order)
            self.assertEqual(order["pharmacy_id"], 1)
            self.assertEqual(order["medicine_id"], med_id)
            self.assertEqual(order["quantity"], 4)
            self.assertEqual(order["remaining_stock"], 96)
            order_id = order["order_id"]

            # Verify stock deduction
            updated_stock = client.check_stock(pharmacy_id=1, medicine_id=med_id)
            self.assertEqual(updated_stock["stock_quantity"], 96)

            # 6. Retrieve order
            retrieved_order = client.get_order(order_id)
            self.assertIsNotNone(retrieved_order)
            self.assertEqual(retrieved_order["order_id"], order_id)
            self.assertEqual(retrieved_order["brand_name"], "Paracip 500")

        finally:
            # 7. Disconnect
            client.disconnect()
            self.assertFalse(client.is_connected())

    def test_error_handling_insufficient_stock(self):
        """Verify client raises ServerError when order exceeds available stock."""
        with PharmacyTCPClient(host="127.0.0.1", port=self.port) as client:
            with self.assertRaises(ServerError) as ctx:
                client.place_order(pharmacy_id=1, medicine_id=1, quantity=99999)
            self.assertIn("Insufficient stock", str(ctx.exception))

    def test_connection_refused_error(self):
        """Verify client raises ConnectionError if server is unreachable."""
        # Port 59999 is unlikely to be listening
        client = PharmacyTCPClient(host="127.0.0.1", port=59999, timeout=1.0)
        with self.assertRaises(ConnectionError):
            client.connect()


if __name__ == "__main__":
    unittest.main(verbosity=2)
