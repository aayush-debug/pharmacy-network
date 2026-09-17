"""
HTTP REST API Routes Module.
Dispatches incoming HTTP request URLs and query parameters to the backend service layer.

IMPORTANT:
This module contains ZERO direct SQL queries.
All database access is delegated to:
- medicine_service
- pharmacy_service
- inventory_service
- order_service
"""

from pathlib import Path
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from backend.app.services import (
    inventory_service,
    medicine_service,
    order_service,
    pharmacy_service,
)


def handle_api_index(query_params: dict, db_path: Path | str | None = None) -> tuple[int, dict]:
    """API Root Index / Directory."""
    return 200, {
        "title": "Pharmacy Stock Query System — HTTP REST API",
        "version": "1.0.0",
        "protocol": "HTTP/1.1 over TCP",
        "endpoints": [
            {"method": "GET", "path": "/api/medicines", "description": "List all medicines or search via ?query=..."},
            {"method": "GET", "path": "/api/medicines/<id>", "description": "Retrieve medicine by ID"},
            {"method": "GET", "path": "/api/pharmacies", "description": "List all registered pharmacies"},
            {"method": "GET", "path": "/api/inventory", "description": "List inventory (optional ?pharmacy_id=...&low_stock=true)"},
            {"method": "GET", "path": "/api/orders", "description": "List orders (optional ?pharmacy_id=...)"},
            {"method": "GET", "path": "/api/orders/<id>", "description": "Retrieve order by ID"},
        ],
    }


def handle_get_medicines(query_params: dict, db_path: Path | str | None = None) -> tuple[int, Any]:
    """GET /api/medicines (supports ?query=...)"""
    query = query_params.get("query", [None])[0]
    if query and query.strip():
        results = medicine_service.search_medicines(query.strip(), db_path=db_path)
    else:
        results = medicine_service.get_all_medicines(db_path=db_path)
    return 200, results


def handle_get_medicine_by_id(medicine_id_str: str, query_params: dict, db_path: Path | str | None = None) -> tuple[int, dict]:
    """GET /api/medicines/<id>"""
    try:
        medicine_id = int(medicine_id_str)
        if medicine_id <= 0:
            raise ValueError("ID must be a positive integer")
    except ValueError:
        return 400, {
            "error": "Bad Request",
            "message": f"Invalid medicine ID '{medicine_id_str}'. ID must be a positive integer.",
        }

    medicine = medicine_service.get_medicine(medicine_id, db_path=db_path)
    if not medicine:
        return 404, {
            "error": "Not Found",
            "message": f"Medicine with ID {medicine_id} does not exist.",
        }

    return 200, medicine


def handle_get_pharmacies(query_params: dict, db_path: Path | str | None = None) -> tuple[int, Any]:
    """GET /api/pharmacies"""
    pharmacies = pharmacy_service.get_all_pharmacies(db_path=db_path)
    return 200, pharmacies


def handle_get_inventory(query_params: dict, db_path: Path | str | None = None) -> tuple[int, Any]:
    """GET /api/inventory (supports ?pharmacy_id=... and ?low_stock=true)"""
    pharmacy_id_param = query_params.get("pharmacy_id", [None])[0]
    pharmacy_id = None
    if pharmacy_id_param is not None:
        try:
            pharmacy_id = int(pharmacy_id_param)
            if pharmacy_id <= 0:
                raise ValueError()
        except ValueError:
            return 400, {
                "error": "Bad Request",
                "message": f"Invalid pharmacy_id '{pharmacy_id_param}'. Must be a positive integer.",
            }

    low_stock_param = query_params.get("low_stock", ["false"])[0].lower()
    if low_stock_param in ("true", "1", "yes"):
        items = inventory_service.get_low_stock(pharmacy_id=pharmacy_id, db_path=db_path)
    else:
        items = inventory_service.get_all_inventory(pharmacy_id=pharmacy_id, db_path=db_path)

    return 200, items


def handle_get_orders(query_params: dict, db_path: Path | str | None = None) -> tuple[int, Any]:
    """GET /api/orders (supports ?pharmacy_id=...)"""
    pharmacy_id_param = query_params.get("pharmacy_id", [None])[0]
    pharmacy_id = None
    if pharmacy_id_param is not None:
        try:
            pharmacy_id = int(pharmacy_id_param)
            if pharmacy_id <= 0:
                raise ValueError()
        except ValueError:
            return 400, {
                "error": "Bad Request",
                "message": f"Invalid pharmacy_id '{pharmacy_id_param}'. Must be a positive integer.",
            }

    orders = order_service.get_all_orders(pharmacy_id=pharmacy_id, db_path=db_path)
    return 200, orders


def handle_get_order_by_id(order_id_str: str, query_params: dict, db_path: Path | str | None = None) -> tuple[int, dict]:
    """GET /api/orders/<id>"""
    try:
        order_id = int(order_id_str)
        if order_id <= 0:
            raise ValueError("ID must be a positive integer")
    except ValueError:
        return 400, {
            "error": "Bad Request",
            "message": f"Invalid order ID '{order_id_str}'. ID must be a positive integer.",
        }

    order = order_service.get_order(order_id, db_path=db_path)
    if not order:
        return 404, {
            "error": "Not Found",
            "message": f"Order with ID {order_id} does not exist.",
        }

    return 200, order


# Compile regex patterns for routing table
ROUTE_PATTERNS = [
    # Root / API info
    (re.compile(r"^/(?:api)?/?$"), lambda m, q, db: handle_api_index(q, db)),
    # Medicines
    (re.compile(r"^/api/medicines/?$"), lambda m, q, db: handle_get_medicines(q, db)),
    (re.compile(r"^/api/medicines/(?P<id>[^/]+)/?$"), lambda m, q, db: handle_get_medicine_by_id(m.group("id"), q, db)),
    # Pharmacies
    (re.compile(r"^/api/pharmacies/?$"), lambda m, q, db: handle_get_pharmacies(q, db)),
    # Inventory
    (re.compile(r"^/api/inventory/?$"), lambda m, q, db: handle_get_inventory(q, db)),
    # Orders
    (re.compile(r"^/api/orders/?$"), lambda m, q, db: handle_get_orders(q, db)),
    (re.compile(r"^/api/orders/(?P<id>[^/]+)/?$"), lambda m, q, db: handle_get_order_by_id(m.group("id"), q, db)),
]


def dispatch_route(raw_url: str, db_path: Path | str | None = None) -> tuple[int, Any]:
    """
    Parses request path and query string, matches against defined routes,
    and returns (http_status_code, response_data).
    Catches unexpected exceptions and returns 500 Internal Server Error.
    """
    try:
        parsed = urlparse(raw_url)
        path = parsed.path
        query_params = parse_qs(parsed.query)

        for pattern, handler in ROUTE_PATTERNS:
            match = pattern.match(path)
            if match:
                return handler(match, query_params, db_path)

        # No route matched
        return 404, {
            "error": "Not Found",
            "message": f"Endpoint '{path}' not recognized by the Pharmacy HTTP REST API.",
            "valid_endpoints": [
                "/api/medicines",
                "/api/medicines/<id>",
                "/api/pharmacies",
                "/api/inventory",
                "/api/orders",
                "/api/orders/<id>",
            ],
        }

    except Exception as err:
        return 500, {
            "error": "Internal Server Error",
            "message": str(err),
        }
