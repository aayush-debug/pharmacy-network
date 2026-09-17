"""
Pharmacy Service Layer.
Encapsulates business operations for querying registered pharmacy branches.
Returns plain Python dictionaries and lists.
"""

from pathlib import Path
from backend.app.database.connection import get_connection


def get_all_pharmacies(db_path: Path | str | None = None) -> list[dict]:
    """
    Retrieves all registered pharmacies in the network, ordered alphabetically by name.
    """
    sql = """
        SELECT
            id,
            name,
            location,
            ip_address,
            tcp_port,
            status
        FROM pharmacies
        ORDER BY name ASC;
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_pharmacy(pharmacy_id: int, db_path: Path | str | None = None) -> dict | None:
    """
    Retrieves a single pharmacy by its unique ID.
    Returns None if not found.
    """
    sql = """
        SELECT
            id,
            name,
            location,
            ip_address,
            tcp_port,
            status
        FROM pharmacies
        WHERE id = ?;
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (pharmacy_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
