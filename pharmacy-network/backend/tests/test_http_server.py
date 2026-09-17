"""
Automated Test Suite for Phase 8: HTTP REST API Server.
Tests:
1. API Root Index (GET /api)
2. Medicines list and query search (GET /api/medicines)
3. Medicine by ID (200, 400, 404) (GET /api/medicines/<id>)
4. Pharmacies list (GET /api/pharmacies)
5. Inventory query (GET /api/inventory, filter by pharmacy_id, low_stock)
6. Orders query and Order by ID (GET /api/orders, GET /api/orders/<id>)
7. Error conditions: 400 Bad Request, 404 Not Found, 405 Method Not Allowed
"""

import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.database.init_db import init_database
from backend.app.database.seed import seed_database
from backend.app.http.server import PharmacyHTTPServer


class TestHTTPServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create isolated temporary database for test suite
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.test_db = Path(cls.temp_dir.name) / "test_http.db"
        init_database(cls.test_db)
        seed_database(cls.test_db)

        # Start HTTP server on ephemeral port (port 0)
        cls.server = PharmacyHTTPServer(host="127.0.0.1", port=0, db_path=cls.test_db)
        cls.server.start(blocking=False)
        time.sleep(0.1)
        cls.base_url = f"http://127.0.0.1:{cls.server.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        cls.temp_dir.cleanup()

    def _http_request(self, path: str, method: str = "GET", data: bytes | None = None) -> tuple[int, dict | list]:
        """Helper to send HTTP request using standard library urllib.request."""
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, method=method, data=data)
        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                body = json.loads(resp.read().decode("utf-8"))
                return status, body
        except urllib.error.HTTPError as err:
            status = err.code
            body = json.loads(err.read().decode("utf-8"))
            return status, body

    def test_01_api_index(self):
        """GET / and GET /api return 200 with API sitemap."""
        status, body = self._http_request("/api")
        self.assertEqual(status, 200)
        self.assertEqual(body.get("title"), "Pharmacy Stock Query System — HTTP REST API")
        self.assertTrue(len(body.get("endpoints", [])) >= 6)

    def test_02_get_all_medicines(self):
        """GET /api/medicines returns 200 and list of all seeded medicines."""
        status, medicines = self._http_request("/api/medicines")
        self.assertEqual(status, 200)
        self.assertIsInstance(medicines, list)
        self.assertEqual(len(medicines), 5)
        names = [m["brand_name"] for m in medicines]
        self.assertIn("Paracip 500", names)
        self.assertIn("Mox 500", names)

    def test_03_search_medicines_query(self):
        """GET /api/medicines?query=paracip filters medicines matching search string."""
        status, medicines = self._http_request("/api/medicines?query=paracip")
        self.assertEqual(status, 200)
        self.assertEqual(len(medicines), 1)
        self.assertEqual(medicines[0]["brand_name"], "Paracip 500")

    def test_04_get_medicine_by_id_success(self):
        """GET /api/medicines/1 returns 200 and single medicine dictionary."""
        status, medicine = self._http_request("/api/medicines/1")
        self.assertEqual(status, 200)
        self.assertEqual(medicine.get("id"), 1)
        self.assertEqual(medicine.get("brand_name"), "Paracip 500")

    def test_05_get_medicine_by_id_not_found(self):
        """GET /api/medicines/999 returns 404 Not Found."""
        status, err = self._http_request("/api/medicines/999")
        self.assertEqual(status, 404)
        self.assertEqual(err.get("error"), "Not Found")

    def test_06_get_medicine_by_id_invalid(self):
        """GET /api/medicines/invalid_id returns 400 Bad Request."""
        status, err = self._http_request("/api/medicines/invalid_id")
        self.assertEqual(status, 400)
        self.assertEqual(err.get("error"), "Bad Request")

    def test_07_get_pharmacies(self):
        """GET /api/pharmacies returns 200 and all registered pharmacy branches."""
        status, pharmacies = self._http_request("/api/pharmacies")
        self.assertEqual(status, 200)
        self.assertEqual(len(pharmacies), 2)
        names = [p["name"] for p in pharmacies]
        self.assertIn("City Health Central", names)
        self.assertIn("Metro Care Chemist", names)

    def test_08_get_inventory(self):
        """GET /api/inventory returns 200 and inventory list with optional filters."""
        # 1. All inventory
        status, items = self._http_request("/api/inventory")
        self.assertEqual(status, 200)
        self.assertEqual(len(items), 7)

        # 2. Filter by pharmacy_id=1
        status, p1_items = self._http_request("/api/inventory?pharmacy_id=1")
        self.assertEqual(status, 200)
        self.assertEqual(len(p1_items), 3)

        # 3. Filter by low_stock=true
        status, low_items = self._http_request("/api/inventory?low_stock=true")
        self.assertEqual(status, 200)
        self.assertEqual(len(low_items), 1)
        self.assertEqual(low_items[0]["brand_name"], "Mox 500")

    def test_09_get_orders(self):
        """GET /api/orders returns 200 and list of recorded orders."""
        status, orders = self._http_request("/api/orders")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(orders), 1)
        self.assertEqual(orders[0]["brand_name"], "Paracip 500")

    def test_10_get_order_by_id(self):
        """GET /api/orders/1 returns 200; GET /api/orders/999 returns 404."""
        status, order = self._http_request("/api/orders/1")
        self.assertEqual(status, 200)
        self.assertEqual(order["order_id"], 1)

        status_nf, err = self._http_request("/api/orders/999")
        self.assertEqual(status_nf, 404)
        self.assertEqual(err.get("error"), "Not Found")

    def test_11_unknown_route_returns_404(self):
        """GET /api/unknown_endpoint returns 404 Not Found."""
        status, err = self._http_request("/api/unknown_endpoint")
        self.assertEqual(status, 404)
        self.assertEqual(err.get("error"), "Not Found")

    def test_12_unsupported_method_returns_405(self):
        """POST /api/medicines returns 405 Method Not Allowed."""
        status, err = self._http_request("/api/medicines", method="POST", data=b'{"name":"test"}')
        self.assertEqual(status, 405)
        self.assertEqual(err.get("error"), "Method Not Allowed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
