"""
Database Seeding Script.
Populates the database with exactly 5 fictional medicines and 2 fictional pharmacies,
plus sample inventory, order, and transaction records.
Uses ONLY fictional data; does NOT use the external Hugging Face dataset.
"""

from pathlib import Path
from backend.app import config
from backend.app.database.connection import get_connection
from backend.app.database.init_db import init_database


def seed_database(db_path: Path | str | None = None, reset: bool = False) -> None:
    """
    Initializes the schema and populates mock data.
    If reset is True, clears existing tables first.
    """
    target_path = Path(db_path) if db_path else config.DB_PATH

    # Ensure tables exist
    init_database(target_path)

    conn = get_connection(target_path)
    try:
        cursor = conn.cursor()

        if reset:
            cursor.execute("DELETE FROM transactions;")
            cursor.execute("DELETE FROM orders;")
            cursor.execute("DELETE FROM inventory;")
            cursor.execute("DELETE FROM pharmacies;")
            cursor.execute("DELETE FROM medicines;")
            try:
                cursor.execute(
                    "DELETE FROM sqlite_sequence WHERE name IN ('medicines', 'pharmacies', 'inventory', 'orders', 'transactions');"
                )
            except sqlite3.OperationalError:
                pass
            conn.commit()
            print("Cleared existing database records.")

        # Check if already seeded
        cursor.execute("SELECT COUNT(*) FROM medicines;")
        if cursor.fetchone()[0] > 0:
            print("Database already contains data. Skipping seeding.")
            return

        print("Seeding exactly 5 fictional medicines and 2 fictional pharmacies...")

        # 1. Five Fictional Medicines
        medicines = [
            (
                1001,
                "Paracip 500",
                "Cipla Ltd",
                20.50,
                "Tablet",
                10.0,
                "tablets",
                "Paracetamol",
                "500mg",
                "Analgesic / Antipyretic",
                0,
            ),
            (
                1002,
                "Mox 500",
                "Sun Pharma",
                85.00,
                "Capsule",
                10.0,
                "capsules",
                "Amoxicillin",
                "500mg",
                "Antibiotic",
                0,
            ),
            (
                1003,
                "Cetzine 10",
                "Dr. Reddy's",
                35.00,
                "Tablet",
                10.0,
                "tablets",
                "Cetirizine",
                "10mg",
                "Antihistamine",
                0,
            ),
            (
                1004,
                "Glycomet 500",
                "USV Ltd",
                45.00,
                "Tablet",
                20.0,
                "tablets",
                "Metformin",
                "500mg",
                "Antidiabetic",
                0,
            ),
            (
                1005,
                "Azithral 250",
                "Alembic Ltd",
                120.00,
                "Tablet",
                6.0,
                "tablets",
                "Azithromycin",
                "250mg",
                "Antibiotic",
                0,
            ),
        ]

        cursor.executemany(
            """
            INSERT INTO medicines (
                product_id, brand_name, manufacturer, price_inr, dosage_form,
                pack_size, pack_unit, primary_ingredient, primary_strength,
                therapeutic_class, is_discontinued
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            medicines,
        )

        # 2. Two Fictional Pharmacies
        pharmacies = [
            (
                "City Health Central",
                "Downtown Market Sector 1",
                "127.0.0.1",
                5000,
                "online",
            ),
            (
                "Metro Care Chemist",
                "Uptown Medical Complex Sector 4",
                "127.0.0.1",
                5002,
                "online",
            ),
        ]

        cursor.executemany(
            """
            INSERT INTO pharmacies (name, location, ip_address, tcp_port, status)
            VALUES (?, ?, ?, ?, ?);
            """,
            pharmacies,
        )

        # 3. Inventory Records
        # Pharmacy 1 (City Health Central): id=1
        # Pharmacy 2 (Metro Care Chemist): id=2
        # Metro Care has low stock on Mox 500 (4 units vs min 10)
        inventory_items = [
            # pharmacy_id, medicine_id, stock_quantity, minimum_stock
            (1, 1, 100, 15),  # Paracip at Pharmacy 1
            (1, 2, 35, 10),   # Mox at Pharmacy 1
            (1, 3, 80, 20),   # Cetzine at Pharmacy 1
            (2, 1, 60, 10),   # Paracip at Pharmacy 2
            (2, 2, 4, 10),    # Mox at Pharmacy 2 (LOW STOCK: 4 < 10)
            (2, 4, 150, 25),  # Glycomet at Pharmacy 2
            (2, 5, 40, 10),   # Azithral at Pharmacy 2
        ]

        cursor.executemany(
            """
            INSERT INTO inventory (pharmacy_id, medicine_id, stock_quantity, minimum_stock)
            VALUES (?, ?, ?, ?);
            """,
            inventory_items,
        )

        # 4. Sample Order
        cursor.execute(
            """
            INSERT INTO orders (pharmacy_id, medicine_id, quantity, status)
            VALUES (?, ?, ?, ?);
            """,
            (1, 1, 2, "completed"),
        )
        sample_order_id = cursor.lastrowid

        # 5. Sample Transaction
        cursor.execute(
            """
            INSERT INTO transactions (pharmacy_id, medicine_id, transaction_type, quantity)
            VALUES (?, ?, ?, ?);
            """,
            (1, 1, "SALE", 2),
        )

        conn.commit()
        print("Database seeding completed successfully.")
        print(f"  - {len(medicines)} medicines inserted.")
        print(f"  - {len(pharmacies)} pharmacies inserted.")
        print(f"  - {len(inventory_items)} inventory records inserted.")
        print("  - 1 sample order and 1 sample transaction recorded.")

    finally:
        conn.close()


if __name__ == "__main__":
    seed_database()
