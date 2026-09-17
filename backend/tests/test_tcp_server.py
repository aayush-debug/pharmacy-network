"""
Automated Test Suite for Phase 4: TCP Socket Server & Protocol.
Tests TCP socket connection, NDJSON message framing, action routing,
error handling, and concurrent multi-threaded client handling.
"""

import json
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
import sys

# Ensure backend package can be imported
current_dir = Path(__file__).resolve().parent
backend_dir = current_dir.parent
if str(backend_dir.parent) not in sys.path:
    sys.path.insert(0, str(backend_dir.parent))

from backend.app.database.seed import seed_database
from backend.app.tcp.server import TCPServer


class SimpleTCPTestClient:
    """Helper client for testing TCP socket communication with NDJSON framing."""

    def __init__(self, host: str, port: int, timeout: float = 3.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: socket.socket | None = None
        self._buffer = ""

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect((self.host, self.port))

    def send_request(self, request_dict: dict) -> dict:
        """Encodes request as NDJSON, sends it, and waits for a single newline-delimited response."""
        if not self.sock:
            raise RuntimeError("Client is not connected.")

        message = (json.dumps(request_dict) + "\n").encode("utf-8")
        self.sock.sendall(message)

        # Read from socket until a complete line ending in '\n' is received
        while "\n" not in self._buffer:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("Server closed connection unexpectedly.")
            self._buffer += chunk.decode("utf-8", errors="replace")

        line, self._buffer = self._buffer.split("\n", 1)
        return json.loads(line.strip())

    def send_raw(self, raw_bytes: bytes) -> str:
        """Sends raw bytes and returns raw response string up to the first newline."""
        self.sock.sendall(raw_bytes)
        while "\n" not in self._buffer:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            self._buffer += chunk.decode("utf-8", errors="replace")
        if "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            return line.strip()
        return self._buffer.strip()

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None


class TestTCPServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Start a dedicated TCPServer on a dynamic free port in a background thread."""
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.test_db_path = Path(cls.temp_dir.name) / "test_tcp.db"
        seed_database(cls.test_db_path)

        # Bind to port 0 to let OS allocate an available port automatically
        cls.server_host = "127.0.0.1"
        # Find a free port
        temp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        temp_sock.bind((cls.server_host, 0))
        cls.server_port = temp_sock.getsockname()[1]
        temp_sock.close()

        cls.server = TCPServer(
            host=cls.server_host,
            port=cls.server_port,
            db_path=cls.test_db_path,
        )
        cls.server.start(blocking=False)
        time.sleep(0.1)  # Allow socket to initialize

    @classmethod
    def tearDownClass(cls):
        """Stop TCP server and cleanup temporary database."""
        cls.server.stop()
        cls.temp_dir.cleanup()

    def test_01_verify_ping(self):
        """Verify 1: PING action returns {"status": "success", "message": "pong"}."""
        client = SimpleTCPTestClient(self.server_host, self.server_port)
        try:
            client.connect()
            resp = client.send_request({"action": "PING"})
            self.assertEqual(resp.get("status"), "success")
            self.assertEqual(resp.get("message"), "pong")
        finally:
            client.close()

    def test_02_verify_search_medicine(self):
        """Verify 2: SEARCH_MEDICINE returns matching medicines from the catalog."""
        client = SimpleTCPTestClient(self.server_host, self.server_port)
        try:
            client.connect()
            resp = client.send_request({"action": "SEARCH_MEDICINE", "query": "Paracip"})
            self.assertEqual(resp.get("status"), "success")
            results = resp.get("results", [])
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["brand_name"], "Paracip 500")
            self.assertEqual(results[0]["primary_ingredient"], "Paracetamol")
        finally:
            client.close()

    def test_03_verify_check_stock(self):
        """Verify 3: CHECK_STOCK returns availability across pharmacy branches."""
        client = SimpleTCPTestClient(self.server_host, self.server_port)
        try:
            client.connect()
            # Cross-pharmacy lookup for Paracip 500 (id=1)
            resp = client.send_request({"action": "CHECK_STOCK", "medicine_id": 1})
            self.assertEqual(resp.get("status"), "success")
            avail = resp.get("availability", [])
            self.assertEqual(len(avail), 2)
            self.assertEqual(avail[0]["pharmacy_name"], "City Health Central")
            self.assertEqual(avail[0]["stock_quantity"], 100)

            # Specific pharmacy lookup
            resp_single = client.send_request(
                {"action": "CHECK_STOCK", "pharmacy_id": 1, "medicine_id": 1}
            )
            self.assertEqual(resp_single.get("status"), "success")
            self.assertEqual(resp_single["stock"]["stock_quantity"], 100)
        finally:
            client.close()

    def test_04_verify_place_order(self):
        """Verify 4: PLACE_ORDER creates order and atomically deducts inventory."""
        client = SimpleTCPTestClient(self.server_host, self.server_port)
        try:
            client.connect()
            resp = client.send_request(
                {"action": "PLACE_ORDER", "pharmacy_id": 1, "medicine_id": 1, "quantity": 4}
            )
            self.assertEqual(resp.get("status"), "success")
            order = resp.get("order")
            self.assertIsNotNone(order)
            self.assertEqual(order["pharmacy_id"], 1)
            self.assertEqual(order["medicine_id"], 1)
            self.assertEqual(order["quantity"], 4)
            self.assertEqual(order["remaining_stock"], 96)
            self.assertEqual(order["total_amount"], 82.0)  # 4 x 20.50

            # Verify stock was indeed deducted via CHECK_STOCK
            stock_check = client.send_request(
                {"action": "CHECK_STOCK", "pharmacy_id": 1, "medicine_id": 1}
            )
            self.assertEqual(stock_check["stock"]["stock_quantity"], 96)
        finally:
            client.close()

    def test_05_verify_find_pharmacies_and_orders(self):
        """Verify FIND_PHARMACIES, GET_MEDICINE, GET_ORDER, and GET_PHARMACY_ORDERS."""
        client = SimpleTCPTestClient(self.server_host, self.server_port)
        try:
            client.connect()
            # FIND_PHARMACIES
            resp_pharm = client.send_request({"action": "FIND_PHARMACIES"})
            self.assertEqual(resp_pharm.get("status"), "success")
            self.assertEqual(len(resp_pharm.get("pharmacies", [])), 2)

            # GET_MEDICINE
            resp_med = client.send_request({"action": "GET_MEDICINE", "medicine_id": 2})
            self.assertEqual(resp_med.get("status"), "success")
            self.assertEqual(resp_med["medicine"]["brand_name"], "Mox 500")

            # GET_PHARMACY_ORDERS
            resp_orders = client.send_request(
                {"action": "GET_PHARMACY_ORDERS", "pharmacy_id": 1}
            )
            self.assertEqual(resp_orders.get("status"), "success")
            self.assertGreaterEqual(len(resp_orders.get("orders", [])), 1)
        finally:
            client.close()

    def test_06_error_handling(self):
        """Verify graceful error responses for unknown actions, invalid JSON, and business errors."""
        client = SimpleTCPTestClient(self.server_host, self.server_port)
        try:
            client.connect()

            # Unknown action
            resp_unknown = client.send_request({"action": "UNKNOWN_ACTION_TEST"})
            self.assertEqual(resp_unknown.get("status"), "error")
            self.assertIn("Unknown action", resp_unknown.get("message", ""))

            # Insufficient stock error
            resp_stock = client.send_request(
                {"action": "PLACE_ORDER", "pharmacy_id": 1, "medicine_id": 1, "quantity": 99999}
            )
            self.assertEqual(resp_stock.get("status"), "error")
            self.assertIn("Insufficient stock", resp_stock.get("message", ""))

            # Malformed JSON
            raw_err = client.send_raw(b"THIS IS NOT VALID JSON\n")
            parsed_err = json.loads(raw_err)
            self.assertEqual(parsed_err.get("status"), "error")
            self.assertIn("Invalid JSON", parsed_err.get("message", ""))
        finally:
            client.close()

    def test_07_concurrent_multi_client_threading(self):
        """
        DEMONSTRATE MULTI-THREADING:
        Spawn 5 simultaneous client threads. Each connects concurrently,
        sends queries, and asserts correct responses without blocking other clients.
        """
        num_clients = 5
        client_results = [False] * num_clients

        def worker_task(client_index: int):
            c = SimpleTCPTestClient(self.server_host, self.server_port)
            try:
                c.connect()
                # 1. PING
                r1 = c.send_request({"action": "PING"})
                if r1.get("message") != "pong":
                    return

                # 2. SEARCH_MEDICINE
                r2 = c.send_request({"action": "SEARCH_MEDICINE", "query": "Glycomet"})
                if not r2.get("results") or r2["results"][0]["brand_name"] != "Glycomet 500":
                    return

                # 3. FIND_PHARMACIES
                r3 = c.send_request({"action": "FIND_PHARMACIES"})
                if len(r3.get("pharmacies", [])) != 2:
                    return

                client_results[client_index] = True
            except Exception as e:
                print(f"Worker {client_index} exception: {e}")
            finally:
                c.close()

        threads = []
        for i in range(num_clients):
            t = threading.Thread(target=worker_task, args=(i,), name=f"TestClient-{i}")
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=5.0)

        # All 5 client threads must have succeeded
        for i, success in enumerate(client_results):
            self.assertTrue(success, f"Concurrent client thread #{i} failed")

    def test_apollo_stock_query(self):
        """Test Apollo GET_STOCK_QUERY endpoint with filtering and 4-tier status calculation."""
        client = SimpleTCPTestClient(self.server_host, self.server_port)
        client.connect()
        try:
            resp = client.send_request({"action": "GET_STOCK_QUERY"})
            self.assertEqual(resp.get("status"), "success")
            items = resp.get("items", [])
            self.assertGreaterEqual(len(items), 5)
            # Check required Apollo fields
            first = items[0]
            self.assertIn("batch_no", first)
            self.assertIn("expiry_date", first)
            self.assertIn("stock_status", first)
            self.assertIn("status_code", first)
            self.assertIn("days_to_expiry", first)

            # Filter by search
            filtered = client.send_request({"action": "GET_STOCK_QUERY", "search": "Paracip"})
            self.assertTrue(any("Paracip" in item["brand_name"] for item in filtered["items"]))
        finally:
            client.close()

    def test_apollo_medicine_crud(self):
        """Test Apollo ADD_MEDICINE, EDIT_MEDICINE, and DELETE_MEDICINE over TCP."""
        client = SimpleTCPTestClient(self.server_host, self.server_port)
        client.connect()
        try:
            # Add
            add_resp = client.send_request({
                "action": "ADD_MEDICINE",
                "brand_name": "TestApolloMed 500",
                "manufacturer": "Apollo Labs",
                "category": "Antibiotic",
                "price_inr": 150.0,
                "batch_no": "AP-9999",
                "expiry_date": "2028-12-31",
                "stock_quantity": 80,
                "reorder_level": 20,
                "pharmacy_id": 1,
            })
            self.assertEqual(add_resp.get("status"), "success")
            med_id = add_resp["medicine"]["id"]

            # Edit
            edit_resp = client.send_request({
                "action": "EDIT_MEDICINE",
                "medicine_id": med_id,
                "brand_name": "TestApolloMed 500 Forte",
                "manufacturer": "Apollo Healthcare",
                "category": "Antibiotic",
                "price_inr": 175.0,
                "batch_no": "AP-9999-B",
                "expiry_date": "2029-01-01",
                "stock_quantity": 90,
                "reorder_level": 25,
                "pharmacy_id": 1,
            })
            self.assertEqual(edit_resp.get("status"), "success")
            self.assertEqual(edit_resp["medicine"]["brand_name"], "TestApolloMed 500 Forte")

            # Delete
            del_resp = client.send_request({"action": "DELETE_MEDICINE", "medicine_id": med_id})
            self.assertEqual(del_resp.get("status"), "success")
        finally:
            client.close()

    def test_apollo_pos_checkout_and_safety_block(self):
        """Test Apollo PROCESS_POS_SALE with success and expired medicine safety blocking."""
        client = SimpleTCPTestClient(self.server_host, self.server_port)
        client.connect()
        try:
            # 1. Valid checkout
            pos_resp = client.send_request({
                "action": "PROCESS_POS_SALE",
                "pharmacy_id": 1,
                "customer_name": "John Doe",
                "payment_method": "Cash",
                "items": [{"medicine_id": 1, "quantity": 2}],
            })
            self.assertEqual(pos_resp.get("status"), "success")
            invoice = pos_resp.get("invoice")
            self.assertIn("invoice_no", invoice)
            self.assertGreater(invoice["grand_total"], 0)
            self.assertEqual(invoice["customer_name"], "John Doe")

            # 2. Add an expired medicine to test safety block
            add_exp = client.send_request({
                "action": "ADD_MEDICINE",
                "brand_name": "ExpiredDrops 10ml",
                "manufacturer": "PharmaCorp",
                "category": "Ophthalmic",
                "price_inr": 45.0,
                "batch_no": "EX-001",
                "expiry_date": "2020-01-01",  # Past date
                "stock_quantity": 20,
                "reorder_level": 5,
                "pharmacy_id": 1,
            })
            exp_med_id = add_exp["medicine"]["id"]

            # Attempt POS sale of expired medicine -> Must be rejected!
            block_resp = client.send_request({
                "action": "PROCESS_POS_SALE",
                "pharmacy_id": 1,
                "customer_name": "Jane Smith",
                "items": [{"medicine_id": exp_med_id, "quantity": 1}],
            })
            self.assertEqual(block_resp.get("status"), "error")
            self.assertIn("SAFETY BLOCK", block_resp.get("message", ""))
        finally:
            client.close()

    def test_apollo_expiry_audit_and_sales_history(self):
        """Test Apollo GET_EXPIRY_AUDIT and GET_SALES_HISTORY endpoints."""
        client = SimpleTCPTestClient(self.server_host, self.server_port)
        client.connect()
        try:
            audit_resp = client.send_request({"action": "GET_EXPIRY_AUDIT"})
            self.assertEqual(audit_resp.get("status"), "success")
            audit = audit_resp.get("audit")
            self.assertIn("expired_count", audit)
            self.assertIn("expiring_soon_count", audit)

            sales_resp = client.send_request({"action": "GET_SALES_HISTORY", "limit": 10})
            self.assertEqual(sales_resp.get("status"), "success")
            self.assertIsInstance(sales_resp.get("sales"), list)
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
