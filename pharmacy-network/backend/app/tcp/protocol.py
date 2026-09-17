"""
TCP Protocol & Message Framing Module.
Implements Newline-Delimited JSON (NDJSON) framing and request routing to services.
Decoupled from socket creation and database access.
"""

import json
from pathlib import Path
from backend.app.services import (
    inventory_service,
    medicine_service,
    order_service,
    pharmacy_service,
)


def encode_message(data: dict) -> bytes:
    """
    Serializes a dictionary into JSON and appends a newline delimiter (NDJSON),
    then encodes it to UTF-8 bytes for transmission across a TCP stream.
    """
    json_str = json.dumps(data, separators=(",", ":"))
    return (json_str + "\n").encode("utf-8")


def decode_line(line: str) -> dict:
    """
    Parses a single newline-stripped string into a Python dictionary.
    Raises json.JSONDecodeError if invalid.
    """
    return json.loads(line.strip())


def create_success_response(data: dict | list | None = None, message: str | None = None, **kwargs) -> dict:
    """Constructs a standardized success response dictionary."""
    resp = {"status": "success"}
    if message is not None:
        resp["message"] = message
    if data is not None:
        resp["data"] = data
    resp.update(kwargs)
    return resp


def create_error_response(message: str, code: str | None = None) -> dict:
    """Constructs a standardized error response dictionary."""
    resp = {"status": "error", "message": message}
    if code:
        resp["code"] = code
    return resp


def handle_request(request: dict, db_path: Path | str | None = None) -> dict:
    """
    Validates the action and routes the request to the appropriate service function.
    Returns a standard response dictionary.
    """
    action = request.get("action")
    if not action or not isinstance(action, str):
        return create_error_response("Missing or invalid 'action' field")

    action_upper = action.strip().upper()

    try:
        # 1. PING
        if action_upper == "PING":
            return create_success_response(message="pong")

        # 2. SEARCH_MEDICINE
        elif action_upper == "SEARCH_MEDICINE":
            query = request.get("query", "")
            if not isinstance(query, str):
                return create_error_response("'query' must be a string")
            results = medicine_service.search_medicines(query, db_path=db_path)
            return create_success_response(results=results)

        # 3. GET_MEDICINE
        elif action_upper == "GET_MEDICINE":
            medicine_id = request.get("medicine_id")
            if medicine_id is None:
                return create_error_response("Missing required parameter: 'medicine_id'")
            try:
                med_id_int = int(medicine_id)
            except (ValueError, TypeError):
                return create_error_response("'medicine_id' must be an integer")

            medicine = medicine_service.get_medicine(med_id_int, db_path=db_path)
            if not medicine:
                return create_error_response(f"Medicine with id={med_id_int} not found")
            return create_success_response(medicine=medicine)

        # 4. CHECK_STOCK
        elif action_upper == "CHECK_STOCK":
            medicine_id = request.get("medicine_id")
            if medicine_id is None:
                return create_error_response("Missing required parameter: 'medicine_id'")
            try:
                med_id_int = int(medicine_id)
            except (ValueError, TypeError):
                return create_error_response("'medicine_id' must be an integer")

            pharmacy_id = request.get("pharmacy_id")
            if pharmacy_id is not None:
                # Specific pharmacy stock lookup
                try:
                    pharma_id_int = int(pharmacy_id)
                except (ValueError, TypeError):
                    return create_error_response("'pharmacy_id' must be an integer")
                stock = inventory_service.get_stock(pharma_id_int, med_id_int, db_path=db_path)
                if not stock:
                    return create_error_response(
                        f"No inventory record for pharmacy_id={pharma_id_int} and medicine_id={med_id_int}"
                    )
                return create_success_response(stock=stock)
            else:
                # Cross-pharmacy availability lookup
                availability = inventory_service.get_medicine_availability(med_id_int, db_path=db_path)
                return create_success_response(availability=availability)

        # 5. FIND_PHARMACIES
        elif action_upper == "FIND_PHARMACIES":
            pharmacies = pharmacy_service.get_all_pharmacies(db_path=db_path)
            return create_success_response(pharmacies=pharmacies)

        # 6. PLACE_ORDER
        elif action_upper == "PLACE_ORDER":
            pharmacy_id = request.get("pharmacy_id")
            medicine_id = request.get("medicine_id")
            quantity = request.get("quantity")

            if pharmacy_id is None or medicine_id is None or quantity is None:
                return create_error_response(
                    "Missing parameters. Required: 'pharmacy_id', 'medicine_id', 'quantity'"
                )

            try:
                p_id = int(pharmacy_id)
                m_id = int(medicine_id)
                qty = int(quantity)
            except (ValueError, TypeError):
                return create_error_response("Parameters 'pharmacy_id', 'medicine_id', and 'quantity' must be integers")

            order = order_service.place_order(p_id, m_id, qty, db_path=db_path)
            return create_success_response(order=order)

        # 7. GET_ORDER
        elif action_upper == "GET_ORDER":
            order_id = request.get("order_id")
            if order_id is None:
                return create_error_response("Missing required parameter: 'order_id'")
            try:
                o_id = int(order_id)
            except (ValueError, TypeError):
                return create_error_response("'order_id' must be an integer")

            order = order_service.get_order(o_id, db_path=db_path)
            if not order:
                return create_error_response(f"Order with id={o_id} not found")
            return create_success_response(order=order)

        # 8. GET_PHARMACY_ORDERS
        elif action_upper == "GET_PHARMACY_ORDERS":
            pharmacy_id = request.get("pharmacy_id")
            if pharmacy_id is None:
                return create_error_response("Missing required parameter: 'pharmacy_id'")
            try:
                p_id = int(pharmacy_id)
            except (ValueError, TypeError):
                return create_error_response("'pharmacy_id' must be an integer")

            orders = order_service.get_pharmacy_orders(p_id, db_path=db_path)
            return create_success_response(orders=orders)

        # 9. UPDATE_STOCK
        elif action_upper == "UPDATE_STOCK":
            pharmacy_id = request.get("pharmacy_id")
            medicine_id = request.get("medicine_id")
            quantity = request.get("quantity")

            if pharmacy_id is None or medicine_id is None or quantity is None:
                return create_error_response(
                    "Missing parameters. Required: 'pharmacy_id', 'medicine_id', 'quantity'"
                )

            try:
                p_id = int(pharmacy_id)
                m_id = int(medicine_id)
                qty = int(quantity)
            except (ValueError, TypeError):
                return create_error_response("Parameters must be integers")

            updated = inventory_service.update_stock(p_id, m_id, qty, db_path=db_path)
            return create_success_response(stock=updated)

        # 10. GET_PHARMACY_INVENTORY
        elif action_upper == "GET_PHARMACY_INVENTORY":
            pharmacy_id = request.get("pharmacy_id")
            if pharmacy_id is None:
                return create_error_response("Missing required parameter: 'pharmacy_id'")
            try:
                p_id = int(pharmacy_id)
            except (ValueError, TypeError):
                return create_error_response("'pharmacy_id' must be an integer")
            inventory_items = inventory_service.get_pharmacy_inventory(p_id, db_path=db_path)
            return create_success_response(inventory=inventory_items)

        # 11. GET_LOW_STOCK
        elif action_upper == "GET_LOW_STOCK":
            pharmacy_id = request.get("pharmacy_id")
            p_id = int(pharmacy_id) if pharmacy_id is not None else None
            alerts = inventory_service.get_low_stock(p_id, db_path=db_path)
            return create_success_response(alerts=alerts)

        # 12. GET_STOCK_QUERY (Apollo Stock Query & Inventory)
        elif action_upper == "GET_STOCK_QUERY":
            pharmacy_id = request.get("pharmacy_id")
            p_id = int(pharmacy_id) if pharmacy_id is not None else None
            search = str(request.get("search", ""))
            category = str(request.get("category", "All"))
            status = str(request.get("status", "All"))
            limit_val = request.get("limit", 50)
            limit = int(limit_val) if limit_val is not None else None
            items = inventory_service.get_stock_query(
                pharmacy_id=p_id, search=search, category=category, status=status, limit=limit, db_path=db_path
            )
            return create_success_response(items=items)

        # 13. ADD_MEDICINE
        elif action_upper == "ADD_MEDICINE":
            brand_name = request.get("brand_name")
            if not brand_name:
                return create_error_response("Missing required parameter: 'brand_name'")
            manufacturer = request.get("manufacturer", "Generic")
            category = request.get("category", "General")
            price_inr = float(request.get("price_inr", 0.0))
            batch_no = request.get("batch_no", "BT-1001")
            expiry_date = request.get("expiry_date", "2028-01-01")
            stock_qty = int(request.get("stock_quantity", 50))
            reorder_lvl = int(request.get("reorder_level", 15))
            pharma_id = int(request.get("pharmacy_id", 1))

            created = inventory_service.add_medicine(
                brand_name=brand_name,
                manufacturer=manufacturer,
                category=category,
                price_inr=price_inr,
                batch_no=batch_no,
                expiry_date=expiry_date,
                stock_quantity=stock_qty,
                reorder_level=reorder_lvl,
                pharmacy_id=pharma_id,
                db_path=db_path,
            )
            return create_success_response(medicine=created)

        # 14. EDIT_MEDICINE
        elif action_upper == "EDIT_MEDICINE":
            medicine_id = request.get("medicine_id")
            if medicine_id is None:
                return create_error_response("Missing required parameter: 'medicine_id'")
            m_id = int(medicine_id)
            brand_name = request.get("brand_name", "")
            manufacturer = request.get("manufacturer", "Generic")
            category = request.get("category", "General")
            price_inr = float(request.get("price_inr", 0.0))
            batch_no = request.get("batch_no", "BT-1001")
            expiry_date = request.get("expiry_date", "2028-01-01")
            stock_qty = int(request.get("stock_quantity", 50))
            reorder_lvl = int(request.get("reorder_level", 15))
            pharma_id = int(request.get("pharmacy_id", 1))

            updated = inventory_service.edit_medicine(
                medicine_id=m_id,
                brand_name=brand_name,
                manufacturer=manufacturer,
                category=category,
                price_inr=price_inr,
                batch_no=batch_no,
                expiry_date=expiry_date,
                stock_quantity=stock_qty,
                reorder_level=reorder_lvl,
                pharmacy_id=pharma_id,
                db_path=db_path,
            )
            return create_success_response(medicine=updated)

        # 15. DELETE_MEDICINE
        elif action_upper == "DELETE_MEDICINE":
            medicine_id = request.get("medicine_id")
            if medicine_id is None:
                return create_error_response("Missing required parameter: 'medicine_id'")
            res = inventory_service.delete_medicine(int(medicine_id), db_path=db_path)
            return create_success_response(result=res)

        # 16. PROCESS_POS_SALE (Point of Sale Checkout)
        elif action_upper == "PROCESS_POS_SALE":
            pharmacy_id = request.get("pharmacy_id")
            items = request.get("items")
            if pharmacy_id is None or not items:
                return create_error_response("Missing required parameters: 'pharmacy_id' and 'items'")
            customer_name = request.get("customer_name", "Walk-in Customer")
            payment_method = request.get("payment_method", "Cash")
            invoice = order_service.process_pos_sale(
                pharmacy_id=int(pharmacy_id),
                items=items,
                customer_name=customer_name,
                payment_method=payment_method,
                db_path=db_path,
            )
            return create_success_response(invoice=invoice)

        # 17. GET_EXPIRY_AUDIT
        elif action_upper == "GET_EXPIRY_AUDIT":
            pharmacy_id = request.get("pharmacy_id")
            p_id = int(pharmacy_id) if pharmacy_id is not None else None
            audit = inventory_service.get_expiry_audit(pharmacy_id=p_id, db_path=db_path)
            return create_success_response(audit=audit)

        # 18. GET_SALES_HISTORY
        elif action_upper == "GET_SALES_HISTORY":
            pharmacy_id = request.get("pharmacy_id")
            p_id = int(pharmacy_id) if pharmacy_id is not None else None
            limit = int(request.get("limit", 100))
            sales = order_service.get_sales_history(pharmacy_id=p_id, limit=limit, db_path=db_path)
            return create_success_response(sales=sales)

        else:
            return create_error_response(f"Unknown action: '{action}'")

    except ValueError as e:
        # Handles domain/business errors like insufficient stock
        return create_error_response(str(e))
    except Exception as e:
        # Unexpected server errors
        return create_error_response(f"Internal server error: {str(e)}")


def process_raw_line(raw_line: str, db_path: Path | str | None = None) -> dict:
    """
    Takes a single unparsed line from the TCP stream, decodes JSON,
    and routes it to handle_request. Returns the response dictionary.
    """
    clean_line = raw_line.strip()
    if not clean_line:
        return create_error_response("Empty request received")

    try:
        request_dict = decode_line(clean_line)
    except json.JSONDecodeError as err:
        return create_error_response(f"Invalid JSON format: {err.msg}")

    if not isinstance(request_dict, dict):
        return create_error_response("Request payload must be a JSON object")

    return handle_request(request_dict, db_path=db_path)
