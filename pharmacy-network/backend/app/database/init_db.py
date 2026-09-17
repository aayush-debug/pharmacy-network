"""
Database Initialization Script.
Creates tables and indexes defined in schema.sql.
"""

from pathlib import Path
from backend.app import config
from backend.app.database.connection import get_connection

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def init_database(db_path: Path | str | None = None) -> None:
    """
    Initializes the SQLite database by running schema.sql.
    Creates all tables, constraints, and indexes if they do not exist.
    """
    target_path = Path(db_path) if db_path else config.DB_PATH
    print(f"Initializing database schema at: {target_path}")

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = get_connection(target_path)
    try:
        conn.executescript(schema_sql)
        # Migrate existing columns if tables already existed
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(medicines);")
        med_cols = {row[1] for row in cursor.fetchall()}
        if "batch_no" not in med_cols:
            cursor.execute("ALTER TABLE medicines ADD COLUMN batch_no TEXT DEFAULT 'BT-1001';")
        if "expiry_date" not in med_cols:
            cursor.execute("ALTER TABLE medicines ADD COLUMN expiry_date TEXT DEFAULT '2028-01-01';")

        cursor.execute("PRAGMA table_info(inventory);")
        inv_cols = {row[1] for row in cursor.fetchall()}
        if "batch_no" not in inv_cols:
            cursor.execute("ALTER TABLE inventory ADD COLUMN batch_no TEXT;")
        if "expiry_date" not in inv_cols:
            cursor.execute("ALTER TABLE inventory ADD COLUMN expiry_date TEXT;")

        conn.commit()
        print("Database schema successfully initialized.")
    finally:
        conn.close()


if __name__ == "__main__":
    init_database()
