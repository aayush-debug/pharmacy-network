"""
Automated Test Suite for Phase 3: Service Layer.
Tests business logic in medicine_service, inventory_service, pharmacy_service,
order_service, and notification_service using the seeded 5 medicines and 2 pharmacies.
"""

import json
import tempfile
import unittest
from pathlib import Path
import sys

# Ensure backend package can be imported
current_dir = Path(__file__).resolve().parent
backend_dir = current_dir.parent
if str(backend_dir.parent) not in sys.path:
    sys.path.insert(0, str(backend_dir.parent))

from backend.app.database.seed import seed_database
from backend.app.services import (
    inventory_service,
    medicine_service,
    notification_service,
    order_service,
    pharmacy_service,
)


class TestServiceLayer(unittest.TestCase):
    def setUp(self):
        """Create an isolated seeded SQLite database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_db_path = Path(self.temp_dir.name) / "test_services.db"
        seed_database(self.test_db_path)

    def tearDown(self):
        """Clean up the temporary directory."""
        self.temp_dir.cleanup()

    # =========================================================================
    # 1. Medicine Service Tests
    # =========================================================================
    def test_search_medicines_by_brand(self):
        """Search medicines by brand name substring."""
        results = medicine_service.search_medicines("paracip", db_path=self.test_db_path)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["brand_name"], "Paracip 500")
        self.assertEqual(results[0]["primary_ingredient"], "Paracetamol")

    def test_search_medicines_by_therapeutic_class(self):
        """Search medicines by therapeutic category."""
        results = medicine_service.search_medicines("Antibiotic", db_path=self.test_db_path)
        self.assertEqual(len(results), 2)
        names = [r["brand_name"] for r in results]
        self.assertEqual(names, ["Azithral 250", "Mox 500"])

    def test_search_medicines_empty(self):
        """Empty query should return empty list."""
        self.assertEqual(medicine_service.search_medicines("", db_path=self.test_db_path), [])
        self.assertEqual(medicine_service.search_medicines("   ", db_path=self.test_db_path), [])

    def test_get_medicine_by_id(self):
        """Fetch single medicine by primary key."""
        med = medicine_service.get_medicine(1, db_path=self.test_db_path)
        self.assertIsNotNone(med)
        self.assertEqual(med["brand_name"], "Paracip 500")

        missing = medicine_service.get_medicine(999, db_path=self.test_db_path)
        self.assertIsNone(missing)

    # =========================================================================
    # 2. Pharmacy Service Tests
    # =========================================================================
    def test_get_all_pharmacies(self):
        """Fetch list of all pharmacies."""
        pharmacies = pharmacy_service.get_all_pharmacies(db_path=self.test_db_path)
        self.assertEqual(len(pharmacies), 2)
        names = [p["name"] for p in pharmacies]
        self.assertIn("City Health Central", names)
        self.assertIn("Metro Care Chemist", names)

    def test_get_pharmacy_by_id(self):
        """Fetch single pharmacy by ID."""
        pharma = pharmacy_service.get_pharmacy(1, db_path=self.test_db_path)
        self.assertIsNotNone(pharma)
        self.assertEqual(pharma["name"], "City Health Central")

        missing = pharmacy_service.get_pharmacy(999, db_path=self.test_db_path)
        self.assertIsNone(missing)

    # =========================================================================
    # 3. Inventory Service Tests
    # =========================================================================
    def test_get_stock(self):
        """Fetch stock for a specific pharmacy and medicine."""
        stock = inventory_service.get_stock(1, 1, db_path=self.test_db_path)
        self.assertIsNotNone(stock)
        self.assertEqual(stock["stock_quantity"], 100)

        # Pharmacy 1 does not stock medicine 5 (Azithral 250)
        not_carried = inventory_service.get_stock(1, 5, db_path=self.test_db_path)
        self.assertIsNone(not_carried)

    def test_get_medicine_availability(self):
        """Verify cross-pharmacy availability query."""
        # Paracip 500 (id=1) is stocked at both pharmacies
        avail = inventory_service.get_medicine_availability(1, db_path=self.test_db_path)
        self.assertEqual(len(avail), 2)
        # Should be ordered descending by stock_quantity
        self.assertEqual(avail[0]["pharmacy_name"], "City Health Central")
        self.assertEqual(avail[0]["stock_quantity"], 100)
        self.assertEqual(avail[1]["pharmacy_name"], "Metro Care Chemist")
        self.assertEqual(avail[1]["stock_quantity"], 60)

    def test_update_stock(self):
        """Update stock quantity and verify transaction logging."""
        updated = inventory_service.update_stock(1, 1, 125, db_path=self.test_db_path)
        self.assertEqual(updated["stock_quantity"], 125)

        # Negative quantity must raise ValueError
        with self.assertRaises(ValueError):
            inventory_service.update_stock(1, 1, -10, db_path=self.test_db_path)

    def test_get_low_stock(self):
        """Verify detection of low stock condition."""
        # Metro Care Chemist has Mox 500 with stock 4 <= min 10
        low_items = inventory_service.get_low_stock(db_path=self.test_db_path)
        self.assertEqual(len(low_items), 1)
        self.assertEqual(low_items[0]["pharmacy_name"], "Metro Care Chemist")
        self.assertEqual(low_items[0]["brand_name"], "Mox 500")
        self.assertEqual(low_items[0]["stock_quantity"], 4)

    # =========================================================================
    # 4. Order Service Tests
    # =========================================================================
    def test_place_order_success(self):
        """Verify placing an order deducts stock and records order/transaction."""
        # Pharmacy 1 has 100 units of Paracip 500 (id=1)
        order = order_service.place_order(1, 1, 10, db_path=self.test_db_path)
        self.assertEqual(order["pharmacy_id"], 1)
        self.assertEqual(order["medicine_id"], 1)
        self.assertEqual(order["quantity"], 10)
        self.assertEqual(order["status"], "confirmed")
        self.assertEqual(order["remaining_stock"], 90)
        self.assertEqual(order["total_amount"], 205.0)

        # Verify inventory table reflects the new stock (90)
        stock = inventory_service.get_stock(1, 1, db_path=self.test_db_path)
        self.assertEqual(stock["stock_quantity"], 90)

    def test_place_order_insufficient_stock(self):
        """Placing an order exceeding available stock must raise ValueError."""
        # Pharmacy 1 only has 100 units
        with self.assertRaises(ValueError):
            order_service.place_order(1, 1, 500, db_path=self.test_db_path)

    def test_place_order_invalid_inputs(self):
        """Placing order with zero or negative quantity or invalid IDs must raise ValueError."""
        with self.assertRaises(ValueError):
            order_service.place_order(1, 1, 0, db_path=self.test_db_path)
        with self.assertRaises(ValueError):
            order_service.place_order(999, 1, 5, db_path=self.test_db_path)
        with self.assertRaises(ValueError):
            order_service.place_order(1, 999, 5, db_path=self.test_db_path)

    def test_get_pharmacy_orders_and_update_status(self):
        """Retrieve pharmacy orders and update order status."""
        # Place a new order
        order = order_service.place_order(1, 2, 5, db_path=self.test_db_path)
        order_id = order["order_id"]

        # Fetch orders for Pharmacy 1
        orders = order_service.get_pharmacy_orders(1, db_path=self.test_db_path)
        self.assertGreaterEqual(len(orders), 1)

        # Update status
        updated = order_service.update_order_status(order_id, "completed", db_path=self.test_db_path)
        self.assertEqual(updated["status"], "completed")

        # Invalid status should raise ValueError
        with self.assertRaises(ValueError):
            order_service.update_order_status(order_id, "invalid_status_value", db_path=self.test_db_path)

    # =========================================================================
    # 5. Notification Service Tests
    # =========================================================================
    def test_notification_payloads(self):
        """Verify notification helper formatting."""
        low_stock_alerts = notification_service.get_pending_low_stock_alerts(db_path=self.test_db_path)
        self.assertEqual(len(low_stock_alerts), 1)
        alert = low_stock_alerts[0]
        self.assertEqual(alert["event_type"], "LOW_STOCK_ALERT")
        self.assertEqual(alert["medicine_name"], "Mox 500")

        text = notification_service.format_alert_message(alert)
        self.assertIn("Low Stock at Metro Care Chemist", text)
        self.assertIn("Mox 500", text)

    # =========================================================================
    # 6. JSON Serializability Tests (Crucial for Networking)
    # =========================================================================
    def test_service_returns_are_json_serializable(self):
        """All service returns must serialize cleanly to JSON for networking layers."""
        meds = medicine_service.search_medicines("Paracip", db_path=self.test_db_path)
        json_meds = json.dumps(meds)
        self.assertTrue(isinstance(json_meds, str))

        avail = inventory_service.get_medicine_availability(1, db_path=self.test_db_path)
        json_avail = json.dumps(avail)
        self.assertTrue(isinstance(json_avail, str))

        order = order_service.get_order(1, db_path=self.test_db_path)
        json_order = json.dumps(order)
        self.assertTrue(isinstance(json_order, str))


if __name__ == "__main__":
    unittest.main(verbosity=2)
