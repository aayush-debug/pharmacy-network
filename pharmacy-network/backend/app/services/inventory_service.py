"""
Inventory Service Layer.
Encapsulates business operations for stock tracking, availability across branches,
stock updates, and low-stock threshold queries.
"""

from pathlib import Path
from backend.app.database.connection import get_connection


def get_stock(
    pharmacy_id: int, medicine_id: int, db_path: Path | str | None = None
) -> dict | None:
    """
    Retrieves the stock level of a specific medicine at a specific pharmacy.
    Returns None if the pharmacy does not carry this medicine.
    """
    sql = """
        SELECT
            i.id,
            i.pharmacy_id,
            p.name AS pharmacy_name,
            i.medicine_id,
            m.brand_name,
            i.stock_quantity,
            i.minimum_stock,
            i.last_updated
        FROM inventory i
        JOIN pharmacies p ON i.pharmacy_id = p.id
        JOIN medicines m ON i.medicine_id = m.id
        WHERE i.pharmacy_id = ? AND i.medicine_id = ?;
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (pharmacy_id, medicine_id))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_pharmacy_inventory(
    pharmacy_id: int, db_path: Path | str | None = None
) -> list[dict]:
    """
    Retrieves all inventory items carried by a specific pharmacy.
    """
    sql = """
        SELECT
            i.id,
            i.pharmacy_id,
            p.name AS pharmacy_name,
            i.medicine_id,
            m.brand_name,
            m.price_inr,
            i.stock_quantity,
            i.minimum_stock,
            (i.stock_quantity <= i.minimum_stock) AS is_low_stock,
            i.last_updated
        FROM inventory i
        JOIN pharmacies p ON i.pharmacy_id = p.id
        JOIN medicines m ON i.medicine_id = m.id
        WHERE i.pharmacy_id = ?
        ORDER BY m.brand_name ASC;
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (pharmacy_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_medicine_availability(
    medicine_id: int, db_path: Path | str | None = None
) -> list[dict]:
    """
    Cross-pharmacy query:
    Finds all pharmacies carrying a specific medicine, showing current stock,
    contact info, and whether stock is below minimum reorder level.
    """
    sql = """
        SELECT
            p.id AS pharmacy_id,
            p.name AS pharmacy_name,
            p.location,
            p.ip_address,
            p.tcp_port,
            p.status AS pharmacy_status,
            m.id AS medicine_id,
            m.brand_name,
            m.price_inr,
            i.stock_quantity,
            i.minimum_stock,
            (i.stock_quantity <= i.minimum_stock) AS is_low_stock,
            i.last_updated
        FROM inventory i
        JOIN pharmacies p ON i.pharmacy_id = p.id
        JOIN medicines m ON i.medicine_id = m.id
        WHERE i.medicine_id = ?
        ORDER BY i.stock_quantity DESC;
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (medicine_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def update_stock(
    pharmacy_id: int,
    medicine_id: int,
    quantity: int,
    db_path: Path | str | None = None,
) -> dict:
    """
    Sets the stock quantity for a medicine at a pharmacy.
    Logs an inventory adjustment transaction for auditing.
    Raises ValueError if quantity is negative or if the inventory record doesn't exist.
    """
    if quantity < 0:
        raise ValueError(f"Stock quantity cannot be negative: {quantity}")

    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()

        # Check existing record
        cursor.execute(
            "SELECT id, stock_quantity FROM inventory WHERE pharmacy_id = ? AND medicine_id = ?;",
            (pharmacy_id, medicine_id),
        )
        existing = cursor.fetchone()
        if not existing:
            raise ValueError(
                f"No inventory record found for pharmacy_id={pharmacy_id}, medicine_id={medicine_id}"
            )

        old_qty = existing["stock_quantity"]
        diff = quantity - old_qty
        transaction_type = "RESTOCK" if diff >= 0 else "ADJUSTMENT"

        # Update inventory
        cursor.execute(
            """
            UPDATE inventory
            SET stock_quantity = ?, last_updated = CURRENT_TIMESTAMP
            WHERE pharmacy_id = ? AND medicine_id = ?;
            """,
            (quantity, pharmacy_id, medicine_id),
        )

        # Log transaction
        cursor.execute(
            """
            INSERT INTO transactions (pharmacy_id, medicine_id, transaction_type, quantity)
            VALUES (?, ?, ?, ?);
            """,
            (pharmacy_id, medicine_id, transaction_type, abs(diff)),
        )

        conn.commit()

        # Return updated record
        cursor.execute(
            """
            SELECT i.id, i.pharmacy_id, p.name AS pharmacy_name, i.medicine_id,
                   m.brand_name, i.stock_quantity, i.minimum_stock, i.last_updated
            FROM inventory i
            JOIN pharmacies p ON i.pharmacy_id = p.id
            JOIN medicines m ON i.medicine_id = m.id
            WHERE i.pharmacy_id = ? AND i.medicine_id = ?;
            """,
            (pharmacy_id, medicine_id),
        )
        return dict(cursor.fetchone())
    finally:
        conn.close()


def get_low_stock(
    pharmacy_id: int | None = None, db_path: Path | str | None = None
) -> list[dict]:
    """
    Retrieves all inventory items where current stock is at or below the minimum stock level.
    If pharmacy_id is provided, filters for that pharmacy; otherwise checks network-wide.
    """
    if pharmacy_id is not None:
        sql = """
            SELECT
                p.id AS pharmacy_id,
                p.name AS pharmacy_name,
                p.location,
                m.id AS medicine_id,
                m.brand_name,
                m.price_inr,
                i.stock_quantity,
                i.minimum_stock,
                i.last_updated
            FROM inventory i
            JOIN pharmacies p ON i.pharmacy_id = p.id
            JOIN medicines m ON i.medicine_id = m.id
            WHERE i.pharmacy_id = ? AND i.stock_quantity <= i.minimum_stock
            ORDER BY i.stock_quantity ASC;
        """
        params = (pharmacy_id,)
    else:
        sql = """
            SELECT
                p.id AS pharmacy_id,
                p.name AS pharmacy_name,
                p.location,
                m.id AS medicine_id,
                m.brand_name,
                m.price_inr,
                i.stock_quantity,
                i.minimum_stock,
                i.last_updated
            FROM inventory i
            JOIN pharmacies p ON i.pharmacy_id = p.id
            JOIN medicines m ON i.medicine_id = m.id
            WHERE i.stock_quantity <= i.minimum_stock
            ORDER BY p.name ASC, i.stock_quantity ASC;
        """
        params = ()

    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_all_inventory(
    pharmacy_id: int | None = None, db_path: Path | str | None = None
) -> list[dict]:
    """
    Retrieves all inventory items across all pharmacies (or for a specific pharmacy).
    Includes medicine details, stock quantity, and minimum stock threshold.
    """
    if pharmacy_id is not None:
        sql = """
            SELECT
                i.id,
                i.pharmacy_id,
                p.name AS pharmacy_name,
                p.location,
                i.medicine_id,
                m.brand_name,
                m.price_inr,
                i.stock_quantity,
                i.minimum_stock,
                (i.stock_quantity <= i.minimum_stock) AS is_low_stock,
                i.last_updated
            FROM inventory i
            JOIN pharmacies p ON i.pharmacy_id = p.id
            JOIN medicines m ON i.medicine_id = m.id
            WHERE i.pharmacy_id = ?
            ORDER BY m.brand_name ASC;
        """
        params = (pharmacy_id,)
    else:
        sql = """
            SELECT
                i.id,
                i.pharmacy_id,
                p.name AS pharmacy_name,
                p.location,
                i.medicine_id,
                m.brand_name,
                m.price_inr,
                i.stock_quantity,
                i.minimum_stock,
                (i.stock_quantity <= i.minimum_stock) AS is_low_stock,
                i.last_updated
            FROM inventory i
            JOIN pharmacies p ON i.pharmacy_id = p.id
            JOIN medicines m ON i.medicine_id = m.id
            ORDER BY p.name ASC, m.brand_name ASC;
        """
        params = ()

    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def compute_stock_status(
    stock_qty: int,
    min_stock: int,
    expiry_str: str | None,
    ref_date: "date | None" = None,
) -> tuple[str, str, int]:
    """
    Computes stock status:
    - EXPIRED: expiry_date < ref_date (Sale Blocked)
    - EXPIRING SOON: expiry_date >= ref_date and days <= 30
    - LOW STOCK: stock_qty <= min_stock (and not expired)
    - IN STOCK: otherwise
    Returns (status_label, status_code, days_remaining)
    """
    from datetime import date, datetime

    if ref_date is None:
        # Standard local date
        ref_date = date.today()

    days_remaining = 9999
    if expiry_str:
        try:
            exp_date = datetime.strptime(expiry_str.strip()[:10], "%Y-%m-%d").date()
            days_remaining = (exp_date - ref_date).days
        except Exception:
            days_remaining = 9999

    if days_remaining < 0:
        return "EXPIRED", "EXPIRED", days_remaining
    elif days_remaining <= 30:
        return "EXPIRING SOON", "EXPIRING_SOON", days_remaining
    elif stock_qty <= min_stock:
        return "LOW STOCK", "LOW_STOCK", days_remaining
    else:
        return "IN STOCK", "IN_STOCK", days_remaining


def get_stock_query(
    pharmacy_id: int | None = None,
    search: str = "",
    category: str = "All",
    status: str = "All",
    limit: int | None = 50,
    db_path: Path | str | None = None,
) -> list[dict]:
    """
    Unified Medicine Inventory & Stock Query.
    Returns medicines matching search, category, and status filters,
    complete with batch_no, expiry_date, stock_quantity, reorder_level,
    and computed stock_status (IN STOCK, LOW STOCK, EXPIRING SOON, EXPIRED).
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()

        # Query all active medicines and join with inventory (grouped or specific pharmacy)
        if pharmacy_id is not None:
            sql = """
                SELECT
                    m.id AS id,
                    m.brand_name,
                    COALESCE(m.manufacturer, 'Generic') AS manufacturer,
                    COALESCE(m.therapeutic_class, 'General') AS category,
                    COALESCE(i.batch_no, m.batch_no, 'BT-' || m.id) AS batch_no,
                    COALESCE(i.expiry_date, m.expiry_date, '2028-01-01') AS expiry_date,
                    COALESCE(m.price_inr, 0.0) AS price_inr,
                    COALESCE(i.stock_quantity, 0) AS stock_quantity,
                    COALESCE(i.minimum_stock, 15) AS reorder_level,
                    p.name AS pharmacy_name,
                    i.pharmacy_id
                FROM medicines m
                LEFT JOIN inventory i ON m.id = i.medicine_id AND i.pharmacy_id = ?
                LEFT JOIN pharmacies p ON i.pharmacy_id = p.id
                WHERE m.is_discontinued = 0
                ORDER BY m.id ASC;
            """
            cursor.execute(sql, (pharmacy_id,))
        else:
            # Query cross-pharmacy unified view (coalesce first branch or max stock)
            sql = """
                SELECT
                    m.id AS id,
                    m.brand_name,
                    COALESCE(m.manufacturer, 'Generic') AS manufacturer,
                    COALESCE(m.therapeutic_class, 'General') AS category,
                    COALESCE(MAX(i.batch_no), m.batch_no, 'BT-' || m.id) AS batch_no,
                    COALESCE(MIN(i.expiry_date), m.expiry_date, '2028-01-01') AS expiry_date,
                    COALESCE(m.price_inr, 0.0) AS price_inr,
                    COALESCE(SUM(i.stock_quantity), 0) AS stock_quantity,
                    COALESCE(MAX(i.minimum_stock), 15) AS reorder_level,
                    'All Branches' AS pharmacy_name,
                    0 AS pharmacy_id
                FROM medicines m
                LEFT JOIN inventory i ON m.id = i.medicine_id
                WHERE m.is_discontinued = 0
                GROUP BY m.id
                ORDER BY m.id ASC;
            """
            cursor.execute(sql)

        rows = cursor.fetchall()
        results = []
        search_lower = search.strip().lower()

        for r in rows:
            d = dict(r)
            status_label, status_code, days_left = compute_stock_status(
                d["stock_quantity"], d["reorder_level"], d["expiry_date"]
            )
            d["stock_status"] = status_label
            d["status_code"] = status_code
            d["days_to_expiry"] = days_left

            # 1. Search text filter
            if search_lower:
                match_text = (
                    f"{d['brand_name']} {d['manufacturer']} {d['category']} {d['batch_no']}".lower()
                )
                if search_lower not in match_text:
                    continue

            # 2. Category filter
            if category and category != "All":
                if category.lower() not in d["category"].lower():
                    continue

            # 3. Status filter
            if status and status != "All":
                norm_status = status.upper().replace(" ", "_")
                if norm_status == "IN_STOCK" and status_code != "IN_STOCK":
                    continue
                elif norm_status == "LOW_STOCK" and status_code != "LOW_STOCK":
                    continue
                elif norm_status == "EXPIRING_SOON" and status_code != "EXPIRING_SOON":
                    continue
                elif norm_status == "EXPIRED" and status_code != "EXPIRED":
                    continue

            results.append(d)
            if limit is not None and len(results) >= limit:
                break

        return results
    finally:
        conn.close()


def add_medicine(
    brand_name: str,
    manufacturer: str,
    category: str,
    price_inr: float,
    batch_no: str,
    expiry_date: str,
    stock_quantity: int = 50,
    reorder_level: int = 15,
    pharmacy_id: int = 1,
    db_path: Path | str | None = None,
) -> dict:
    """
    Adds a new medicine to the master catalog and creates an initial inventory record.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO medicines (
                brand_name, manufacturer, price_inr, therapeutic_class,
                batch_no, expiry_date, is_discontinued
            ) VALUES (?, ?, ?, ?, ?, ?, 0);
            """,
            (brand_name, manufacturer, price_inr, category, batch_no, expiry_date),
        )
        med_id = cursor.lastrowid

        # Insert or update inventory for the specified pharmacy
        cursor.execute(
            """
            INSERT INTO inventory (pharmacy_id, medicine_id, stock_quantity, minimum_stock, batch_no, expiry_date)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(pharmacy_id, medicine_id) DO UPDATE SET
                stock_quantity = excluded.stock_quantity,
                minimum_stock = excluded.minimum_stock,
                batch_no = excluded.batch_no,
                expiry_date = excluded.expiry_date,
                last_updated = CURRENT_TIMESTAMP;
            """,
            (pharmacy_id, med_id, stock_quantity, reorder_level, batch_no, expiry_date),
        )
        conn.commit()

        return {
            "id": med_id,
            "brand_name": brand_name,
            "manufacturer": manufacturer,
            "category": category,
            "price_inr": price_inr,
            "batch_no": batch_no,
            "expiry_date": expiry_date,
            "stock_quantity": stock_quantity,
            "reorder_level": reorder_level,
        }
    finally:
        conn.close()


def edit_medicine(
    medicine_id: int,
    brand_name: str,
    manufacturer: str,
    category: str,
    price_inr: float,
    batch_no: str,
    expiry_date: str,
    stock_quantity: int,
    reorder_level: int,
    pharmacy_id: int = 1,
    db_path: Path | str | None = None,
) -> dict:
    """
    Updates medicine details, batch info, price, and stock levels.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE medicines
            SET brand_name = ?, manufacturer = ?, therapeutic_class = ?,
                price_inr = ?, batch_no = ?, expiry_date = ?
            WHERE id = ?;
            """,
            (brand_name, manufacturer, category, price_inr, batch_no, expiry_date, medicine_id),
        )

        cursor.execute(
            """
            INSERT INTO inventory (pharmacy_id, medicine_id, stock_quantity, minimum_stock, batch_no, expiry_date)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(pharmacy_id, medicine_id) DO UPDATE SET
                stock_quantity = excluded.stock_quantity,
                minimum_stock = excluded.minimum_stock,
                batch_no = excluded.batch_no,
                expiry_date = excluded.expiry_date,
                last_updated = CURRENT_TIMESTAMP;
            """,
            (pharmacy_id, medicine_id, stock_quantity, reorder_level, batch_no, expiry_date),
        )
        conn.commit()

        return {
            "id": medicine_id,
            "brand_name": brand_name,
            "manufacturer": manufacturer,
            "category": category,
            "price_inr": price_inr,
            "batch_no": batch_no,
            "expiry_date": expiry_date,
            "stock_quantity": stock_quantity,
            "reorder_level": reorder_level,
        }
    finally:
        conn.close()


def delete_medicine(
    medicine_id: int, db_path: Path | str | None = None
) -> dict:
    """
    Marks a medicine as discontinued and clears inventory.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE medicines SET is_discontinued = 1 WHERE id = ?;", (medicine_id,)
        )
        cursor.execute("DELETE FROM inventory WHERE medicine_id = ?;", (medicine_id,))
        conn.commit()
        return {"id": medicine_id, "status": "deleted"}
    finally:
        conn.close()


def get_expiry_audit(
    pharmacy_id: int | None = None, db_path: Path | str | None = None
) -> dict:
    """
    Aggregates shelf-life metrics and lists batches requiring attention:
    - Expired (immediate disposal / quarantine, sale blocked)
    - Expiring in <= 30 Days (urgent clearance / discount)
    - Expiring in <= 90 Days (monitoring watchlist)
    """
    items = get_stock_query(pharmacy_id=pharmacy_id, db_path=db_path)

    expired_items = [i for i in items if i["status_code"] == "EXPIRED"]
    expiring_soon_items = [i for i in items if i["status_code"] == "EXPIRING_SOON"]
    watch_items = [i for i in items if 30 < i["days_to_expiry"] <= 90]

    loss_value = sum(i["stock_quantity"] * i["price_inr"] for i in expired_items)
    at_risk_value = sum(i["stock_quantity"] * i["price_inr"] for i in expiring_soon_items)

    return {
        "expired_count": len(expired_items),
        "expiring_soon_count": len(expiring_soon_items),
        "watchlist_count": len(watch_items),
        "loss_value_inr": round(loss_value, 2),
        "at_risk_value_inr": round(at_risk_value, 2),
        "expired_items": expired_items,
        "expiring_soon_items": expiring_soon_items,
        "watchlist_items": watch_items,
        "all_audited_items": expired_items + expiring_soon_items + watch_items,
    }


