"""
Notification Service Layer (Helpers & Payloads).
Prepares structured notification payloads and alert messages for future UDP and SMTP integrations.
Contains NO socket or SMTP code — strictly pure data preparation.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from backend.app.services.inventory_service import get_low_stock


def build_order_notification_payload(order: dict) -> dict:
    """
    Constructs a structured notification payload for a newly placed or updated order.
    Returns a dictionary ready for JSON serialization or SMTP email template formatting.
    """
    return {
        "event_type": "ORDER_CONFIRMATION",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "order_id": order.get("order_id"),
        "pharmacy_name": order.get("pharmacy_name"),
        "medicine_name": order.get("brand_name"),
        "quantity": order.get("quantity"),
        "total_amount": order.get("total_amount"),
        "status": order.get("status"),
        "remaining_stock": order.get("remaining_stock"),
    }


def build_low_stock_notification_payload(item: dict) -> dict:
    """
    Constructs a structured notification payload for an item reaching or dropping below minimum stock.
    Returns a dictionary ready for UDP alert broadcasting or SMTP administrator alerts.
    """
    return {
        "event_type": "LOW_STOCK_ALERT",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pharmacy_id": item.get("pharmacy_id"),
        "pharmacy_name": item.get("pharmacy_name"),
        "pharmacy_location": item.get("location"),
        "medicine_id": item.get("medicine_id"),
        "medicine_name": item.get("brand_name"),
        "current_stock": item.get("stock_quantity"),
        "minimum_stock": item.get("minimum_stock"),
    }


def format_alert_message(payload: dict) -> str:
    """
    Formats a human-readable text message from a notification payload.
    Suitable for email bodies, console logs, or GUI status notifications.
    """
    event = payload.get("event_type")
    if event == "LOW_STOCK_ALERT":
        return (
            f"[ALERT] Low Stock at {payload.get('pharmacy_name')}!\n"
            f"Medicine: {payload.get('medicine_name')}\n"
            f"Current Stock: {payload.get('current_stock')} "
            f"(Reorder Threshold: {payload.get('minimum_stock')})"
        )
    elif event == "ORDER_CONFIRMATION":
        return (
            f"[ORDER CONFIRMED] Order #{payload.get('order_id')}\n"
            f"Pharmacy: {payload.get('pharmacy_name')}\n"
            f"Medicine: {payload.get('medicine_name')} x {payload.get('quantity')}\n"
            f"Total: INR {payload.get('total_amount')}\n"
            f"Status: {payload.get('status')}"
        )
    return f"[EVENT] {event}: {json.dumps(payload)}"


def get_pending_low_stock_alerts(
    pharmacy_id: int | None = None, db_path: Path | str | None = None
) -> list[dict]:
    """
    Scans the inventory for all active low-stock items and returns
    structured notification payloads ready for dispatch.
    """
    low_stock_items = get_low_stock(pharmacy_id, db_path=db_path)
    return [build_low_stock_notification_payload(item) for item in low_stock_items]


def notify_order_created(order_dict: dict, recipient: str | None = None):
    """
    Service event handler: Dispatches order confirmation notification via SMTP.
    Safely catches any delivery error to prevent breaking database transactions.
    """
    from backend.app.smtp.mailer import send_order_confirmation

    try:
        return send_order_confirmation(order_dict, recipient=recipient)
    except Exception as err:
        print(f"[Notification Service Warning]: Failed to dispatch order email: {err}")
        return None


def notify_low_stock(item_dict: dict, recipient: str | None = None):
    """
    Service event handler: Dispatches low-stock alert notification via SMTP.
    Safely catches any delivery error.
    """
    from backend.app.smtp.mailer import send_low_stock_alert

    try:
        return send_low_stock_alert(item_dict, recipient=recipient)
    except Exception as err:
        print(f"[Notification Service Warning]: Failed to dispatch low-stock email: {err}")
        return None

