"""
Medicine Service Layer.
Encapsulates business operations for medicine master catalog search and lookup.
Returns plain Python dictionaries and lists.
"""

from pathlib import Path
from backend.app.database.connection import get_connection


def search_medicines(query: str, db_path: Path | str | None = None) -> list[dict]:
    """
    Searches medicines matching the query across brand_name, primary_ingredient,
    and therapeutic_class (case-insensitive substring match).
    Returns an empty list if query is empty or whitespace.
    """
    clean_query = query.strip()
    if not clean_query:
        return []

    pattern = f"%{clean_query}%"
    sql = """
        SELECT
            id,
            product_id,
            brand_name,
            manufacturer,
            price_inr,
            dosage_form,
            pack_size,
            pack_unit,
            primary_ingredient,
            primary_strength,
            therapeutic_class,
            is_discontinued
        FROM medicines
        WHERE brand_name LIKE ? OR primary_ingredient LIKE ? OR therapeutic_class LIKE ?
        ORDER BY brand_name ASC;
    """

    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (pattern, pattern, pattern))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_medicine(medicine_id: int, db_path: Path | str | None = None) -> dict | None:
    """
    Retrieves a single medicine record by its unique database ID.
    Returns None if not found.
    """
    sql = """
        SELECT
            id,
            product_id,
            brand_name,
            manufacturer,
            price_inr,
            dosage_form,
            pack_size,
            pack_unit,
            primary_ingredient,
            primary_strength,
            therapeutic_class,
            is_discontinued
        FROM medicines
        WHERE id = ?;
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (medicine_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all_medicines(db_path: Path | str | None = None) -> list[dict]:
    """
    Retrieves the entire catalog of medicines, ordered alphabetically by brand name.
    """
    sql = """
        SELECT
            id,
            product_id,
            brand_name,
            manufacturer,
            price_inr,
            dosage_form,
            pack_size,
            pack_unit,
            primary_ingredient,
            primary_strength,
            therapeutic_class,
            is_discontinued
        FROM medicines
        ORDER BY brand_name ASC;
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

