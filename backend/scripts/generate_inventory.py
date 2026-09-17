"""
Fictional Inventory Generator.
Generates realistic stock and inventory distributions for 4 fictional pharmacies
using medicines from the master catalog.

ACADEMIC DISCLAIMER:
Pharmacy names, branch locations, and inventory stock levels are strictly
FICTIONAL demonstration data generated for network simulation.
The medicine master catalog is derived from the external Hugging Face dataset.
"""

from pathlib import Path
import random
import sqlite3
from typing import Any

from backend.app import config
from backend.app.database.connection import get_connection

FICTIONAL_PHARMACIES = [
    {
        "name": "City Health Central",
        "location": "Downtown Market Sector 1",
        "ip_address": "127.0.0.1",
        "tcp_port": 5000,
        "status": "online",
        "target_items": 1200,
    },
    {
        "name": "Metro Care Chemist",
        "location": "Uptown Medical Complex Sector 4",
        "ip_address": "127.0.0.1",
        "tcp_port": 5002,
        "status": "online",
        "target_items": 1000,
    },
    {
        "name": "Apollo Care Partner",
        "location": "Cyber City Tech Hub Sector 21",
        "ip_address": "127.0.0.1",
        "tcp_port": 5004,
        "status": "online",
        "target_items": 1400,
    },
    {
        "name": "MedPlus Express",
        "location": "Central Railway Station Plaza",
        "ip_address": "127.0.0.1",
        "tcp_port": 5006,
        "status": "online",
        "target_items": 800,
    },
]


def generate_fictional_inventory(
    db_path: Path | str | None = None,
    seed: int = 42,
    reset_inventory: bool = True,
) -> dict[str, Any]:
    """
    Populates 4 fictional pharmacies and assigns random, realistic stock quantities
    for a subset of medicines from the master catalog.
    """
    rng = random.Random(seed)
    target_db = Path(db_path) if db_path else config.DB_PATH

    print(f"[Inventory Generator] Connecting to {target_db}...")
    conn = get_connection(target_db)
    try:
        cursor = conn.cursor()

        # 1. Ensure pharmacies exist
        pharmacy_id_map: dict[str, int] = {}
        for p in FICTIONAL_PHARMACIES:
            cursor.execute(
                "SELECT id FROM pharmacies WHERE name = ?;", (p["name"],)
            )
            row = cursor.fetchone()
            if row:
                pharmacy_id_map[p["name"]] = row["id"]
            else:
                cursor.execute(
                    """
                    INSERT INTO pharmacies (name, location, ip_address, tcp_port, status)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (p["name"], p["location"], p["ip_address"], p["tcp_port"], p["status"]),
                )
                pharmacy_id_map[p["name"]] = cursor.lastrowid

        conn.commit()
        print(f"[Inventory Generator] Configured {len(pharmacy_id_map)} pharmacies: {list(pharmacy_id_map.keys())}")

        # 2. Get available medicine IDs
        cursor.execute("SELECT id, brand_name FROM medicines ORDER BY id ASC;")
        medicines = cursor.fetchall()
        if not medicines:
            raise RuntimeError("Medicines table is empty! Run clean_dataset.py first.")

        medicine_ids = [m["id"] for m in medicines]
        total_meds = len(medicine_ids)
        print(f"[Inventory Generator] Available master catalog medicines: {total_meds:,}")

        # 3. Reset existing inventory if requested
        if reset_inventory:
            cursor.execute("DELETE FROM transactions;")
            cursor.execute("DELETE FROM orders;")
            cursor.execute("DELETE FROM inventory;")
            conn.commit()
            print("[Inventory Generator] Cleared previous inventory, orders, and transactions.")

        # 4. Generate stock per pharmacy
        total_inventory_inserted = 0
        inventory_records = []

        for p in FICTIONAL_PHARMACIES:
            pharm_id = pharmacy_id_map[p["name"]]
            target_count = min(p["target_items"], total_meds)

            # Pick a deterministic subset of medicines
            selected_ids = rng.sample(medicine_ids, target_count)

            # Ensure the first 20 medicines (core staples) are stocked everywhere
            core_ids = medicine_ids[:min(20, total_meds)]
            combined_ids = list(set(selected_ids).union(core_ids))

            for med_id in combined_ids:
                # 10% chance of being low-stock (stock < min_stock)
                min_stock = rng.randint(10, 25)
                if rng.random() < 0.10:
                    stock_qty = rng.randint(0, min_stock - 1)
                else:
                    stock_qty = rng.randint(min_stock, 150)

                inventory_records.append((pharm_id, med_id, stock_qty, min_stock))

        cursor.executemany(
            """
            INSERT OR REPLACE INTO inventory (pharmacy_id, medicine_id, stock_quantity, minimum_stock)
            VALUES (?, ?, ?, ?);
            """,
            inventory_records,
        )
        total_inventory_inserted = len(inventory_records)

        # 5. Insert initial sample order
        cursor.execute(
            """
            INSERT INTO orders (pharmacy_id, medicine_id, quantity, status)
            VALUES (1, 1, 3, 'completed');
            """
        )
        order_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO transactions (pharmacy_id, medicine_id, transaction_type, quantity)
            VALUES (1, 1, 'SALE', 3);
            """
        )

        conn.commit()

        # Summary
        cursor.execute("SELECT COUNT(*) FROM inventory;")
        count_inv = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM inventory WHERE stock_quantity <= minimum_stock;")
        count_low = cursor.fetchone()[0]

        print(
            f"[Inventory Generator] Generated {count_inv:,} total inventory records across "
            f"{len(pharmacy_id_map)} pharmacies ({count_low:,} currently low stock)."
        )

        return {
            "pharmacies_count": len(pharmacy_id_map),
            "inventory_records": count_inv,
            "low_stock_records": count_low,
            "master_medicines_count": total_meds,
        }

    finally:
        conn.close()


if __name__ == "__main__":
    generate_fictional_inventory()
