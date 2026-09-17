"""
Populate Batch Numbers, Expiry Dates, and Stock Statuses.
Ensures realistic shelf-life distributions (In Stock, Low Stock, Expiring Soon, Expired)
matching the Apollo Pharmacy enterprise standards.
"""

from datetime import date, timedelta
from pathlib import Path
import random
from backend.app import config
from backend.app.database.connection import get_connection


def populate_batches(db_path: Path | str | None = None) -> None:
    target_path = Path(db_path) if db_path else config.DB_PATH
    conn = get_connection(target_path)
    today = date.today()

    try:
        cursor = conn.cursor()

        # Prefixes for batch numbers
        prefixes = ["AG", "DL", "AZ", "TL", "GL", "ML", "BZ", "AT", "AL", "TH", "AS", "CP", "OF", "SP", "PD"]

        # 1. Update medicines master table defaults
        cursor.execute("SELECT id, brand_name FROM medicines;")
        meds = cursor.fetchall()
        print(f"Assigning batch numbers and default expiries to {len(meds)} catalog medicines...")

        update_meds = []
        for m in meds:
            m_id = m["id"]
            prefix = prefixes[m_id % len(prefixes)]
            batch = f"{prefix}-{1000 + (m_id * 37) % 9000}"
            # Default future expiry: 1 to 2 years ahead
            future_exp = (today + timedelta(days=180 + (m_id * 43) % 600)).isoformat()
            update_meds.append((batch, future_exp, m_id))

        cursor.executemany(
            "UPDATE medicines SET batch_no = ?, expiry_date = ? WHERE id = ?;",
            update_meds,
        )

        # 2. Update inventory table with varied realistic expiries and batches
        cursor.execute("SELECT id, pharmacy_id, medicine_id, stock_quantity, minimum_stock FROM inventory;")
        inv_items = cursor.fetchall()
        print(f"Updating {len(inv_items)} inventory records with dynamic shelf-life data...")

        update_inv = []
        for idx, item in enumerate(inv_items):
            i_id = item["id"]
            m_id = item["medicine_id"]
            prefix = prefixes[m_id % len(prefixes)]
            batch = f"{prefix}-{1000 + (m_id * 37 + i_id) % 9000}"

            # Create a deliberate realistic distribution:
            # 5% Expired (< today)
            # 8% Expiring soon (1 to 30 days)
            # 87% Safe future (60 to 700 days)
            mod = (idx * 17) % 100
            if mod < 5:
                # Expired: 10 to 45 days ago
                exp_date = (today - timedelta(days=5 + (idx % 40))).isoformat()
            elif mod < 13:
                # Expiring soon: 5 to 28 days ahead
                exp_date = (today + timedelta(days=3 + (idx % 27))).isoformat()
            else:
                # In stock / normal shelf life: 90 to 750 days ahead
                exp_date = (today + timedelta(days=90 + (idx * 23) % 650)).isoformat()

            update_inv.append((batch, exp_date, i_id))

        cursor.executemany(
            "UPDATE inventory SET batch_no = ?, expiry_date = ? WHERE id = ?;",
            update_inv,
        )

        conn.commit()
        print("Successfully updated batch numbers and expiry dates across database.")
    finally:
        conn.close()


if __name__ == "__main__":
    populate_batches()
