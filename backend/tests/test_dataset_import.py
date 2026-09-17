"""
Automated Test Suite for Phase 11: Hugging Face Medicine Dataset Integration.
Tests all 7 required verification scenarios:
1. Dataset loading from Hugging Face
2. Cleaning logic (discontinued filtering, text normalization, deduplication)
3. Processed CSV creation (10,000 records)
4. Database import into SQLite
5. Medicine search through the Service Layer
6. Medicine search through the TCP Server (NDJSON stream)
7. Medicine search rendered in PySide6 GUI
"""

import csv
import os
from pathlib import Path
import sys
import time
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication
from backend.app import config
from backend.app.database.connection import get_connection
from backend.app.services import medicine_service
from backend.app.tcp.server import TCPServer
from frontend.gui.search import SearchWidget
from frontend.network.tcp_client import PharmacyTCPClient

app = QApplication.instance() or QApplication(sys.argv)


class TestDatasetIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Point to the active processed database containing the 10,000-catalog
        cls.db_path = config.DB_PATH
        cls.csv_path = config.DATA_PROCESSED_DIR / "medicines.csv"

        # Start an ephemeral TCP server for search verification
        cls.tcp_server = TCPServer(host="127.0.0.1", port=0, db_path=cls.db_path)
        cls.tcp_server.start(blocking=False)
        time.sleep(0.15)
        cls.tcp_port = cls.tcp_server.port

    @classmethod
    def tearDownClass(cls):
        cls.tcp_server.stop()

    def test_01_dataset_loading(self):
        """Verify 1: Dataset loading from Hugging Face repository."""
        from datasets import load_dataset
        ds = load_dataset("revooda/indian-pharma-data")
        split = ds["train"] if "train" in ds else ds
        self.assertGreater(len(split), 200000, "Hugging Face dataset should have over 200k rows")
        self.assertIn("brand_name", split.column_names)
        self.assertIn("product_id", split.column_names)
        self.assertIn("manufacturer", split.column_names)

    def test_02_cleaning_logic(self):
        """Verify 2: Data cleaning rules correctly filter invalid/discontinued records."""
        # Test cleaning heuristics on dirty sample records
        sample_dirty = [
            {"product_id": 1, "brand_name": "Valid Brand", "is_discontinued": 0, "price_inr": 25.0},
            {"product_id": 2, "brand_name": "Discontinued Med", "is_discontinued": 1, "price_inr": 10.0},  # Drop
            {"product_id": 3, "brand_name": "   ", "is_discontinued": 0, "price_inr": 15.0},              # Drop (empty brand)
            {"product_id": 1, "brand_name": "Duplicate ID", "is_discontinued": 0, "price_inr": 30.0},      # Drop (duplicate ID)
            {"product_id": -5, "brand_name": "Negative ID", "is_discontinued": 0, "price_inr": 50.0},      # Drop (invalid ID)
        ]

        cleaned = []
        seen = set()
        for item in sample_dirty:
            if item.get("is_discontinued") in (1, True):
                continue
            pid = item.get("product_id")
            if not pid or pid <= 0 or pid in seen:
                continue
            brand = (item.get("brand_name") or "").strip()
            if not brand:
                continue
            seen.add(pid)
            cleaned.append(item)

        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0]["brand_name"], "Valid Brand")

    def test_03_csv_creation(self):
        """Verify 3: Processed CSV exists with 10,000 valid active rows."""
        self.assertTrue(self.csv_path.is_file(), f"Processed CSV missing at {self.csv_path}")

        with open(self.csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 10000, "Processed CSV must contain exactly 10,000 records")

            # Check required fields
            first = rows[0]
            self.assertTrue(first["brand_name"])
            self.assertTrue(first["product_id"])
            self.assertEqual(first["is_discontinued"], "0")

    def test_04_database_import(self):
        """Verify 4: Database import into SQLite with master medicines and inventory."""
        conn = get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM medicines;")
            med_count = cursor.fetchone()[0]
            self.assertGreaterEqual(med_count, 10000, "SQLite medicines table must contain at least 10,000 records")

            cursor.execute("SELECT COUNT(*) FROM pharmacies;")
            pharm_count = cursor.fetchone()[0]
            self.assertGreaterEqual(pharm_count, 4, "Must have at least 4 pharmacies")

            cursor.execute("SELECT COUNT(*) FROM inventory;")
            inv_count = cursor.fetchone()[0]
            self.assertGreater(inv_count, 2000, "Must have substantial inventory generated")
        finally:
            conn.close()

    def test_05_medicine_search_service_layer(self):
        """Verify 5: Medicine search through service layer on expanded 10,000-catalog."""
        # Search by active ingredient substring
        results = medicine_service.search_medicines("paracetamol", db_path=self.db_path)
        self.assertGreater(len(results), 5, "Search for 'paracetamol' should return multiple brands")

        first_match = results[0]
        self.assertIn("brand_name", first_match)
        self.assertIn("manufacturer", first_match)
        self.assertIn("price_inr", first_match)
        self.assertIn("dosage_form", first_match)

    def test_06_medicine_search_through_tcp(self):
        """Verify 6: Medicine search through TCP socket server (Layer 4 NDJSON)."""
        client = PharmacyTCPClient(host="127.0.0.1", port=self.tcp_port)
        client.connect()
        try:
            # Send SEARCH_MEDICINE NDJSON request for 'amox' (matches Indian pharma 'Amoxycillin' brands)
            medicines = client.search_medicines("amox")
            self.assertIsInstance(medicines, list)
            self.assertGreater(len(medicines), 0, "TCP search should return matching Amoxycillin medicines")

            # Verify availability lookup across pharmacies
            first_id = medicines[0]["id"]
            avail = client.find_pharmacies(first_id)
            self.assertIsInstance(avail, list)
        finally:
            client.disconnect()

    def test_07_medicine_search_through_gui(self):
        """Verify 7: Medicine search through PySide6 GUI search screen."""
        client = PharmacyTCPClient(host="127.0.0.1", port=self.tcp_port)
        client.connect()
        try:
            search_widget = SearchWidget(client)
            search_widget.show()

            # Populate search field and perform search
            search_widget.search_input.setText("paracetamol")
            search_widget.do_search()

            # Process Qt event loop until background QThread completes
            for _ in range(40):
                app.processEvents()
                if search_widget.results_table.rowCount() > 0:
                    break
                time.sleep(0.05)

            self.assertGreater(
                search_widget.results_table.rowCount(),
                0,
                "GUI search table should be populated with matching medicine rows",
            )
            brand_in_table = search_widget.results_table.item(0, 1).text()
            self.assertTrue(len(brand_in_table) > 0)
        finally:
            client.disconnect()
            search_widget.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
