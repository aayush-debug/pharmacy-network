"""
Automated Test Suite for Phase 2: Database Foundation.
Tests database initialization, table creation, record insertion,
SELECT queries, foreign-key constraint enforcement, and unique constraints.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path
import sys

# Ensure backend package can be imported
current_dir = Path(__file__).resolve().parent
backend_dir = current_dir.parent
if str(backend_dir.parent) not in sys.path:
    sys.path.insert(0, str(backend_dir.parent))

from backend.app.database.connection import get_connection
from backend.app.database.init_db import init_database
from backend.app.database.seed import seed_database


class TestDatabaseFoundation(unittest.TestCase):
    def setUp(self):
        """Create an isolated temporary SQLite database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_db_path = Path(self.temp_dir.name) / "test_pharmacy.db"
        seed_database(self.test_db_path)

    def tearDown(self):
        """Clean up the temporary directory."""
        self.temp_dir.cleanup()

    def test_database_and_tables_creation(self):
        """Verify that all 5 tables and their indexes were created."""
        conn = get_connection(self.test_db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
            )
            tables = {row["name"] for row in cursor.fetchall()}
            expected_tables = {"medicines", "pharmacies", "inventory", "orders", "transactions"}
            self.assertTrue(
                expected_tables.issubset(tables),
                f"Missing tables: {expected_tables - tables}",
            )

            # Check indexes
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%';"
            )
            indexes = {row["name"] for row in cursor.fetchall()}
            expected_indexes = {
                "idx_medicines_brand",
                "idx_medicines_ingredient",
                "idx_medicines_therapeutic",
                "idx_inventory_medicine",
                "idx_inventory_pharmacy",
                "idx_orders_pharmacy",
            }
            self.assertTrue(
                expected_indexes.issubset(indexes),
                f"Missing indexes: {expected_indexes - indexes}",
            )
        finally:
            conn.close()

    def test_seeding_counts(self):
        """Verify exact counts of fictional seed records (5 medicines, 2 pharmacies)."""
        conn = get_connection(self.test_db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM medicines;")
            self.assertEqual(cursor.fetchone()[0], 5, "Must have exactly 5 medicines")

            cursor.execute("SELECT COUNT(*) FROM pharmacies;")
            self.assertEqual(cursor.fetchone()[0], 2, "Must have exactly 2 pharmacies")

            cursor.execute("SELECT COUNT(*) FROM inventory;")
            self.assertEqual(cursor.fetchone()[0], 7, "Must have 7 inventory records")

            cursor.execute("SELECT COUNT(*) FROM orders;")
            self.assertEqual(cursor.fetchone()[0], 1, "Must have 1 sample order")

            cursor.execute("SELECT COUNT(*) FROM transactions;")
            self.assertEqual(cursor.fetchone()[0], 1, "Must have 1 sample transaction")
        finally:
            conn.close()

    def test_select_queries(self):
        """Verify SELECT queries by brand_name, primary_ingredient, and therapeutic_class."""
        conn = get_connection(self.test_db_path)
        try:
            cursor = conn.cursor()

            # Search by brand_name
            cursor.execute("SELECT * FROM medicines WHERE brand_name = ?;", ("Paracip 500",))
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["primary_ingredient"], "Paracetamol")
            self.assertEqual(row["price_inr"], 20.50)

            # Search by primary_ingredient
            cursor.execute(
                "SELECT brand_name FROM medicines WHERE primary_ingredient = ?;",
                ("Amoxicillin",),
            )
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["brand_name"], "Mox 500")

            # Search by therapeutic_class
            cursor.execute(
                "SELECT brand_name FROM medicines WHERE therapeutic_class = ? ORDER BY brand_name;",
                ("Antibiotic",),
            )
            antibiotics = [r["brand_name"] for r in cursor.fetchall()]
            self.assertEqual(antibiotics, ["Azithral 250", "Mox 500"])
        finally:
            conn.close()

    def test_cross_pharmacy_stock_select(self):
        """Verify JOIN query finding stock of a medicine across pharmacies."""
        conn = get_connection(self.test_db_path)
        try:
            cursor = conn.cursor()
            query = """
                SELECT p.name AS pharmacy_name, m.brand_name, i.stock_quantity, i.minimum_stock
                FROM inventory i
                JOIN pharmacies p ON i.pharmacy_id = p.id
                JOIN medicines m ON i.medicine_id = m.id
                WHERE m.brand_name = ?
                ORDER BY i.stock_quantity DESC;
            """
            cursor.execute(query, ("Paracip 500",))
            results = cursor.fetchall()
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0]["pharmacy_name"], "City Health Central")
            self.assertEqual(results[0]["stock_quantity"], 100)
            self.assertEqual(results[1]["pharmacy_name"], "Metro Care Chemist")
            self.assertEqual(results[1]["stock_quantity"], 60)
        finally:
            conn.close()

    def test_foreign_key_enforcement(self):
        """Verify PRAGMA foreign_keys = ON prevents invalid foreign key insertions."""
        conn = get_connection(self.test_db_path)
        try:
            cursor = conn.cursor()

            # Attempt inserting inventory with non-existent pharmacy_id=999
            with self.assertRaises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO inventory (pharmacy_id, medicine_id, stock_quantity) VALUES (?, ?, ?);",
                    (999, 1, 50),
                )
                conn.commit()

            # Attempt inserting inventory with non-existent medicine_id=999
            with self.assertRaises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO inventory (pharmacy_id, medicine_id, stock_quantity) VALUES (?, ?, ?);",
                    (1, 999, 50),
                )
                conn.commit()
        finally:
            conn.close()

    def test_unique_inventory_constraint(self):
        """Verify UNIQUE(pharmacy_id, medicine_id) prevents duplicate entries."""
        conn = get_connection(self.test_db_path)
        try:
            cursor = conn.cursor()
            # (1, 1) already exists in seed data
            with self.assertRaises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO inventory (pharmacy_id, medicine_id, stock_quantity) VALUES (?, ?, ?);",
                    (1, 1, 200),
                )
                conn.commit()
        finally:
            conn.close()

    def test_cascade_delete(self):
        """Verify deleting a pharmacy cascades to remove its inventory records."""
        conn = get_connection(self.test_db_path)
        try:
            cursor = conn.cursor()
            # Pharmacy 2 has 4 inventory records and no orders
            cursor.execute("SELECT COUNT(*) FROM inventory WHERE pharmacy_id = 2;")
            count_before = cursor.fetchone()[0]
            self.assertEqual(count_before, 4)

            # Delete pharmacy 2: inventory should cascade delete
            cursor.execute("DELETE FROM pharmacies WHERE id = 2;")
            conn.commit()

            # Inventory for pharmacy 2 should now be 0 due to CASCADE
            cursor.execute("SELECT COUNT(*) FROM inventory WHERE pharmacy_id = 2;")
            count_after = cursor.fetchone()[0]
            self.assertEqual(count_after, 0)

            # Pharmacy 1 has associated orders with ON DELETE RESTRICT,
            # so attempting to delete Pharmacy 1 directly must raise IntegrityError
            with self.assertRaises(sqlite3.IntegrityError):
                cursor.execute("DELETE FROM pharmacies WHERE id = 1;")
                conn.commit()
        finally:
            conn.close()

    def test_seed_database_reset(self):
        """Verify that seed_database(reset=True) resets and repopulates correctly."""
        seed_database(self.test_db_path, reset=True)
        conn = get_connection(self.test_db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM medicines;")
            self.assertEqual(cursor.fetchone()[0], 5)
            cursor.execute("SELECT COUNT(*) FROM pharmacies;")
            self.assertEqual(cursor.fetchone()[0], 2)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
