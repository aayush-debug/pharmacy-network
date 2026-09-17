"""
Report Generation Module.
Generates CSV reports from the service layer data into backend/reports/:
1. inventory_report.csv
2. order_report.csv
3. low_stock_report.csv

These reports are served and transferred over File Transfer Protocol (FTP).
"""

import csv
from pathlib import Path
from backend.app import config
from backend.app.services import inventory_service, order_service


def _ensure_dir(target_dir: Path | str | None = None) -> Path:
    """Ensures the destination reports directory exists and returns Path object."""
    destination = Path(target_dir) if target_dir else config.REPORTS_DIR
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def generate_inventory_report(
    output_dir: Path | str | None = None, db_path: Path | str | None = None
) -> Path:
    """
    Generates 'inventory_report.csv' containing full network inventory status.
    """
    dest_dir = _ensure_dir(output_dir)
    file_path = dest_dir / "inventory_report.csv"

    items = inventory_service.get_all_inventory(db_path=db_path)

    fieldnames = [
        "inventory_id",
        "pharmacy_id",
        "pharmacy_name",
        "location",
        "medicine_id",
        "brand_name",
        "price_inr",
        "stock_quantity",
        "minimum_stock",
        "is_low_stock",
        "last_updated",
    ]

    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            writer.writerow({
                "inventory_id": item.get("id"),
                "pharmacy_id": item.get("pharmacy_id"),
                "pharmacy_name": item.get("pharmacy_name"),
                "location": item.get("location"),
                "medicine_id": item.get("medicine_id"),
                "brand_name": item.get("brand_name"),
                "price_inr": item.get("price_inr"),
                "stock_quantity": item.get("stock_quantity"),
                "minimum_stock": item.get("minimum_stock"),
                "is_low_stock": "YES" if item.get("is_low_stock") else "NO",
                "last_updated": item.get("last_updated"),
            })

    print(f"[Reports] Generated inventory report: {file_path} ({len(items)} records)")
    return file_path


def generate_order_report(
    output_dir: Path | str | None = None, db_path: Path | str | None = None
) -> Path:
    """
    Generates 'order_report.csv' containing transaction and fulfillment history.
    """
    dest_dir = _ensure_dir(output_dir)
    file_path = dest_dir / "order_report.csv"

    orders = order_service.get_all_orders(db_path=db_path)

    fieldnames = [
        "order_id",
        "pharmacy_id",
        "pharmacy_name",
        "medicine_id",
        "brand_name",
        "unit_price",
        "quantity",
        "total_amount",
        "status",
        "created_at",
    ]

    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for o in orders:
            writer.writerow({
                "order_id": o.get("order_id"),
                "pharmacy_id": o.get("pharmacy_id"),
                "pharmacy_name": o.get("pharmacy_name"),
                "medicine_id": o.get("medicine_id"),
                "brand_name": o.get("brand_name"),
                "unit_price": o.get("unit_price"),
                "quantity": o.get("quantity"),
                "total_amount": o.get("total_amount"),
                "status": o.get("status"),
                "created_at": o.get("created_at"),
            })

    print(f"[Reports] Generated order report: {file_path} ({len(orders)} records)")
    return file_path


def generate_low_stock_report(
    output_dir: Path | str | None = None, db_path: Path | str | None = None
) -> Path:
    """
    Generates 'low_stock_report.csv' containing medicines needing reorder.
    """
    dest_dir = _ensure_dir(output_dir)
    file_path = dest_dir / "low_stock_report.csv"

    low_items = inventory_service.get_low_stock(db_path=db_path)

    fieldnames = [
        "pharmacy_id",
        "pharmacy_name",
        "location",
        "medicine_id",
        "brand_name",
        "price_inr",
        "stock_quantity",
        "minimum_stock",
        "last_updated",
    ]

    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in low_items:
            writer.writerow({
                "pharmacy_id": item.get("pharmacy_id"),
                "pharmacy_name": item.get("pharmacy_name"),
                "location": item.get("location"),
                "medicine_id": item.get("medicine_id"),
                "brand_name": item.get("brand_name"),
                "price_inr": item.get("price_inr"),
                "stock_quantity": item.get("stock_quantity"),
                "minimum_stock": item.get("minimum_stock"),
                "last_updated": item.get("last_updated"),
            })

    print(f"[Reports] Generated low-stock alert report: {file_path} ({len(low_items)} records)")
    return file_path


def generate_all_reports(
    output_dir: Path | str | None = None, db_path: Path | str | None = None
) -> dict[str, Path]:
    """Convenience helper to generate all 3 reports in one call."""
    return {
        "inventory": generate_inventory_report(output_dir, db_path),
        "orders": generate_order_report(output_dir, db_path),
        "low_stock": generate_low_stock_report(output_dir, db_path),
    }


if __name__ == "__main__":
    print("=== Generating Pharmacy CSV Reports for FTP ===")
    generate_all_reports()
    print("Done. Reports are ready in backend/reports/")
