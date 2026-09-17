"""
Order Service Layer.
Encapsulates business operations for placing orders, updating stock atomically,
and tracking order statuses across pharmacy branches.
"""

from pathlib import Path
from backend.app.database.connection import get_connection

VALID_STATUSES = {"pending", "confirmed", "completed", "cancelled"}


def place_order(
    pharmacy_id: int,
    medicine_id: int,
    quantity: int,
    db_path: Path | str | None = None,
) -> dict:
    """
    Places an order for a medicine at a specific pharmacy:
    1. Validates quantity (> 0).
    2. Checks whether medicine and pharmacy exist.
    3. Verifies stock availability.
    4. Atomically:
       - Deducts stock from inventory.
       - Records the order in 'orders'.
       - Records the 'SALE' in 'transactions'.
    Raises ValueError if stock is insufficient or inputs are invalid.
    """
    if quantity <= 0:
        raise ValueError(f"Order quantity must be greater than 0, got: {quantity}")

    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()

        # 1. Check pharmacy
        cursor.execute("SELECT id, name FROM pharmacies WHERE id = ?;", (pharmacy_id,))
        pharmacy = cursor.fetchone()
        if not pharmacy:
            raise ValueError(f"Pharmacy with id={pharmacy_id} does not exist.")

        # 2. Check medicine
        cursor.execute(
            "SELECT id, brand_name, price_inr FROM medicines WHERE id = ?;",
            (medicine_id,),
        )
        medicine = cursor.fetchone()
        if not medicine:
            raise ValueError(f"Medicine with id={medicine_id} does not exist.")

        # 3. Check inventory & stock
        cursor.execute(
            "SELECT id, stock_quantity, minimum_stock FROM inventory WHERE pharmacy_id = ? AND medicine_id = ?;",
            (pharmacy_id, medicine_id),
        )
        inv = cursor.fetchone()
        if not inv:
            raise ValueError(
                f"Pharmacy '{pharmacy['name']}' does not carry '{medicine['brand_name']}'."
            )

        available_stock = inv["stock_quantity"]
        if available_stock < quantity:
            raise ValueError(
                f"Insufficient stock for '{medicine['brand_name']}' at '{pharmacy['name']}'. "
                f"Requested: {quantity}, Available: {available_stock}."
            )

        new_stock = available_stock - quantity

        # 4. Atomic updates
        # Deduct stock
        cursor.execute(
            """
            UPDATE inventory
            SET stock_quantity = ?, last_updated = CURRENT_TIMESTAMP
            WHERE pharmacy_id = ? AND medicine_id = ?;
            """,
            (new_stock, pharmacy_id, medicine_id),
        )

        # Create order
        cursor.execute(
            """
            INSERT INTO orders (pharmacy_id, medicine_id, quantity, status)
            VALUES (?, ?, ?, 'confirmed');
            """,
            (pharmacy_id, medicine_id, quantity),
        )
        order_id = cursor.lastrowid

        # Record audit transaction
        cursor.execute(
            """
            INSERT INTO transactions (pharmacy_id, medicine_id, transaction_type, quantity)
            VALUES (?, ?, 'SALE', ?);
            """,
            (pharmacy_id, medicine_id, quantity),
        )

        conn.commit()

        # Fetch created order record
        cursor.execute(
            """
            SELECT
                o.id AS order_id,
                o.pharmacy_id,
                p.name AS pharmacy_name,
                o.medicine_id,
                m.brand_name,
                m.price_inr AS unit_price,
                o.quantity,
                ROUND(o.quantity * m.price_inr, 2) AS total_amount,
                o.status,
                o.created_at
            FROM orders o
            JOIN pharmacies p ON o.pharmacy_id = p.id
            JOIN medicines m ON o.medicine_id = m.id
            WHERE o.id = ?;
            """,
            (order_id,),
        )
        order_dict = dict(cursor.fetchone())
        order_dict["remaining_stock"] = new_stock
        order_dict["is_now_low_stock"] = new_stock <= inv["minimum_stock"]

        # Safe Notification Event Dispatch
        try:
            from backend.app.services import notification_service
            notification_service.notify_order_created(order_dict)

            if order_dict["is_now_low_stock"]:
                # 1. Trigger SMTP Low-Stock Email to Admin
                notification_service.notify_low_stock({
                    "medicine": order_dict["brand_name"],
                    "pharmacy": order_dict["pharmacy_name"],
                    "stock": new_stock,
                    "minimum": inv["minimum_stock"],
                })

                # 2. Trigger UDP Low-Stock Push Broadcast
                from backend.app.udp.alerts import UDPAlertBroadcaster
                UDPAlertBroadcaster().send_low_stock_alert(
                    medicine=order_dict["brand_name"],
                    pharmacy=order_dict["pharmacy_name"],
                    stock=new_stock,
                    minimum=inv["minimum_stock"],
                )
        except Exception as notify_err:
            print(f"[Order Event Warning]: Notification dispatch encountered an issue: {notify_err}")

        return order_dict

    finally:
        conn.close()


def get_order(order_id: int, db_path: Path | str | None = None) -> dict | None:
    """
    Retrieves detailed order information by order ID, including
    associated pharmacy and medicine names.
    """
    sql = """
        SELECT
            o.id AS order_id,
            o.pharmacy_id,
            p.name AS pharmacy_name,
            o.medicine_id,
            m.brand_name,
            m.price_inr AS unit_price,
            o.quantity,
            ROUND(o.quantity * m.price_inr, 2) AS total_amount,
            o.status,
            o.created_at
        FROM orders o
        JOIN pharmacies p ON o.pharmacy_id = p.id
        JOIN medicines m ON o.medicine_id = m.id
        WHERE o.id = ?;
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (order_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_pharmacy_orders(
    pharmacy_id: int, db_path: Path | str | None = None
) -> list[dict]:
    """
    Retrieves all orders placed at a specific pharmacy branch.
    """
    sql = """
        SELECT
            o.id AS order_id,
            o.pharmacy_id,
            p.name AS pharmacy_name,
            o.medicine_id,
            m.brand_name,
            m.price_inr AS unit_price,
            o.quantity,
            ROUND(o.quantity * m.price_inr, 2) AS total_amount,
            o.status,
            o.created_at
        FROM orders o
        JOIN pharmacies p ON o.pharmacy_id = p.id
        JOIN medicines m ON o.medicine_id = m.id
        WHERE o.pharmacy_id = ?
        ORDER BY o.created_at DESC;
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (pharmacy_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def update_order_status(
    order_id: int, status: str, db_path: Path | str | None = None
) -> dict:
    """
    Updates the status of an existing order (e.g., 'confirmed', 'completed', 'cancelled').
    Raises ValueError if the status is invalid or the order does not exist.
    """
    clean_status = status.strip().lower()
    if clean_status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status '{status}'. Must be one of: {sorted(list(VALID_STATUSES))}"
        )

    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM orders WHERE id = ?;", (order_id,))
        if not cursor.fetchone():
            raise ValueError(f"Order with id={order_id} does not exist.")

        cursor.execute(
            "UPDATE orders SET status = ? WHERE id = ?;", (clean_status, order_id)
        )
        conn.commit()

        return get_order(order_id, db_path)
    finally:
        conn.close()


def get_all_orders(
    pharmacy_id: int | None = None, db_path: Path | str | None = None
) -> list[dict]:
    """
    Retrieves all orders across all pharmacies (or for a specific pharmacy).
    Includes joined pharmacy name, medicine brand name, unit price, total amount, and status.
    """
    if pharmacy_id is not None:
        return get_pharmacy_orders(pharmacy_id, db_path)

    sql = """
        SELECT
            o.id AS order_id,
            o.pharmacy_id,
            p.name AS pharmacy_name,
            o.medicine_id,
            m.brand_name,
            m.price_inr AS unit_price,
            o.quantity,
            ROUND(o.quantity * m.price_inr, 2) AS total_amount,
            o.status,
            o.created_at
        FROM orders o
        JOIN pharmacies p ON o.pharmacy_id = p.id
        JOIN medicines m ON o.medicine_id = m.id
        ORDER BY o.created_at DESC;
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def process_pos_sale(
    pharmacy_id: int,
    items: list[dict],
    customer_name: str = "Walk-in Customer",
    payment_method: str = "Cash",
    db_path: Path | str | None = None,
) -> dict:
    """
    Executes an atomic Point of Sale (POS) transaction for multiple cart items.
    Enforces pharmacy safety rules:
    - Blocks sale if ANY medicine in cart is EXPIRED.
    - Validates available stock quantities.
    - Atomically updates inventory and logs transactions.
    - Computes GST and generates a complete sales receipt / invoice.
    """
    import time
    from datetime import date, datetime

    if not items:
        raise ValueError("Cannot checkout: Cart is empty.")

    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()

        # 1. Validate pharmacy
        cursor.execute("SELECT id, name, location FROM pharmacies WHERE id = ?;", (pharmacy_id,))
        pharma = cursor.fetchone()
        if not pharma:
            raise ValueError(f"Pharmacy ID {pharmacy_id} does not exist.")
        pharma_name = pharma["name"]

        today = date.today()
        line_items = []
        low_stock_triggers = []

        # 2. Pre-validate all items before making any modifications
        for entry in items:
            med_id = int(entry["medicine_id"])
            qty = int(entry["quantity"])
            if qty <= 0:
                raise ValueError("Item quantity must be greater than 0.")

            # Fetch medicine details
            cursor.execute(
                """
                SELECT id, brand_name, price_inr, batch_no, expiry_date, is_discontinued
                FROM medicines WHERE id = ?;
                """,
                (med_id,),
            )
            med = cursor.fetchone()
            if not med:
                raise ValueError(f"Medicine with ID {med_id} not found.")
            if med["is_discontinued"]:
                raise ValueError(f"Medicine '{med['brand_name']}' is discontinued.")

            # Safety Rule: Expiry validation
            exp_str = med["expiry_date"]
            if exp_str:
                try:
                    exp_date = datetime.strptime(exp_str.strip()[:10], "%Y-%m-%d").date()
                    if exp_date < today:
                        raise ValueError(
                            f"SAFETY BLOCK: Medicine '{med['brand_name']}' expired on {exp_str}. "
                            "Sale is legally blocked!"
                        )
                except ValueError as ve:
                    if "SAFETY BLOCK" in str(ve):
                        raise
                    pass

            # Check stock
            cursor.execute(
                """
                SELECT stock_quantity, minimum_stock, batch_no, expiry_date
                FROM inventory
                WHERE pharmacy_id = ? AND medicine_id = ?;
                """,
                (pharmacy_id, med_id),
            )
            inv = cursor.fetchone()
            if not inv:
                raise ValueError(f"Pharmacy '{pharma_name}' does not stock '{med['brand_name']}'.")

            avail = inv["stock_quantity"]
            if avail < qty:
                raise ValueError(
                    f"Insufficient stock for '{med['brand_name']}'. Requested: {qty}, Available: {avail}."
                )

            batch = inv["batch_no"] or med["batch_no"] or f"BT-{med_id}"
            unit_price = float(med["price_inr"] or 0.0)
            line_total = round(qty * unit_price, 2)

            line_items.append({
                "medicine_id": med_id,
                "brand_name": med["brand_name"],
                "batch_no": batch,
                "unit_price": unit_price,
                "quantity": qty,
                "line_total": line_total,
                "remaining_stock": avail - qty,
                "min_stock": inv["minimum_stock"],
            })

        # 3. Apply atomic updates
        total_subtotal = 0.0
        order_ids = []

        for item in line_items:
            med_id = item["medicine_id"]
            qty = item["quantity"]
            new_stock = item["remaining_stock"]
            total_subtotal += item["line_total"]

            # Deduct inventory
            cursor.execute(
                """
                UPDATE inventory
                SET stock_quantity = ?, last_updated = CURRENT_TIMESTAMP
                WHERE pharmacy_id = ? AND medicine_id = ?;
                """,
                (new_stock, pharmacy_id, med_id),
            )

            # Record order
            cursor.execute(
                """
                INSERT INTO orders (pharmacy_id, medicine_id, quantity, status)
                VALUES (?, ?, ?, 'completed');
                """,
                (pharmacy_id, med_id, qty),
            )
            order_ids.append(cursor.lastrowid)

            # Record transaction
            cursor.execute(
                """
                INSERT INTO transactions (pharmacy_id, medicine_id, transaction_type, quantity)
                VALUES (?, ?, 'POS_SALE', ?);
                """,
                (pharmacy_id, med_id, qty),
            )

            if new_stock <= item["min_stock"]:
                low_stock_triggers.append({
                    "medicine": item["brand_name"],
                    "pharmacy": pharma_name,
                    "stock": new_stock,
                    "minimum": item["min_stock"],
                })

        conn.commit()

        # 4. Generate invoice receipt
        tax_gst = round(total_subtotal * 0.05, 2)  # 5% GST
        grand_total = round(total_subtotal + tax_gst, 2)
        invoice_no = f"APOLLO-{int(time.time()) % 1000000:06d}"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Dispatch background UDP alerts if low stock
        try:
            from backend.app.services import notification_service
            for alert in low_stock_triggers:
                notification_service.notify_low_stock(alert)
        except Exception:
            pass

        return {
            "invoice_no": invoice_no,
            "pharmacy_id": pharmacy_id,
            "pharmacy_name": pharma_name,
            "customer_name": customer_name or "Walk-in Customer",
            "payment_method": payment_method or "Cash",
            "timestamp": now_str,
            "items": line_items,
            "subtotal": round(total_subtotal, 2),
            "tax_gst": tax_gst,
            "grand_total": grand_total,
            "order_ids": order_ids,
        }
    finally:
        conn.close()


def get_sales_history(
    pharmacy_id: int | None = None,
    limit: int = 100,
    db_path: Path | str | None = None,
) -> list[dict]:
    """
    Retrieves sales ledger including POS sales and orders.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        if pharmacy_id is not None:
            sql = """
                SELECT
                    t.id AS transaction_id,
                    t.timestamp,
                    t.transaction_type,
                    t.quantity,
                    p.name AS pharmacy_name,
                    m.brand_name,
                    m.price_inr AS unit_price,
                    ROUND(t.quantity * m.price_inr, 2) AS total_amount
                FROM transactions t
                JOIN pharmacies p ON t.pharmacy_id = p.id
                JOIN medicines m ON t.medicine_id = m.id
                WHERE t.pharmacy_id = ?
                ORDER BY t.timestamp DESC
                LIMIT ?;
            """
            cursor.execute(sql, (pharmacy_id, limit))
        else:
            sql = """
                SELECT
                    t.id AS transaction_id,
                    t.timestamp,
                    t.transaction_type,
                    t.quantity,
                    p.name AS pharmacy_name,
                    m.brand_name,
                    m.price_inr AS unit_price,
                    ROUND(t.quantity * m.price_inr, 2) AS total_amount
                FROM transactions t
                JOIN pharmacies p ON t.pharmacy_id = p.id
                JOIN medicines m ON t.medicine_id = m.id
                ORDER BY t.timestamp DESC
                LIMIT ?;
            """
            cursor.execute(sql, (limit,))

        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


