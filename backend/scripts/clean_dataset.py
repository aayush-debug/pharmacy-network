"""
Medicine Dataset Cleaning & SQLite Import Pipeline.
Cleans raw medicine records from 'revooda/indian-pharma-data' and exports
approximately 10,000 active medicines to backend/data/processed/medicines.csv.
Imports cleaned medicines into the SQLite database.

Cleaning Rules:
1. Filters out discontinued products (keeps only is_discontinued == 0).
2. Drops rows with missing or empty brand_name.
3. Deduplicates unique product_id.
4. Normalizes text formatting (strips whitespace, capitalizes dosage forms).
5. Sanitizes price, pack size, and unit values.
6. Caps development import to ~10,000 active, genuine medicines.
"""

import csv
import math
from pathlib import Path
import sqlite3
from typing import Any

from datasets import load_dataset
from backend.app import config
from backend.app.database.connection import get_connection
from backend.app.database.init_db import init_database

DEFAULT_CLEAN_OUTPUT = config.DATA_PROCESSED_DIR / "medicines.csv"
TARGET_ACTIVE_COUNT = 10000


def clean_and_export_dataset(
    target_count: int = TARGET_ACTIVE_COUNT,
    output_csv: Path | str | None = None,
    dataset_name: str = "revooda/indian-pharma-data",
) -> Path:
    """
    Loads raw Hugging Face dataset, applies cleaning filters, and saves ~10,000
    active medicines into backend/data/processed/medicines.csv.
    """
    print(f"[Cleaning Pipeline] Loading dataset '{dataset_name}'...")
    dataset = load_dataset(dataset_name)
    split = dataset["train"] if "train" in dataset else dataset

    out_path = Path(output_csv) if output_csv else DEFAULT_CLEAN_OUTPUT
    out_path.parent.mkdir(parents=True, exist_ok=True)

    seen_product_ids: set[int] = set()
    cleaned_rows: list[dict[str, Any]] = []

    print(f"[Cleaning Pipeline] Processing records (Target: {target_count:,} active medicines)...")

    for idx, item in enumerate(split):
        # 1. Filter discontinued medicines
        discontinued_raw = item.get("is_discontinued")
        if discontinued_raw in (1, True, "1", "true", "True"):
            continue

        # 2. Check and clean product_id
        raw_pid = item.get("product_id")
        if raw_pid is None:
            continue
        try:
            pid = int(raw_pid)
            if pid <= 0:
                continue
        except (ValueError, TypeError):
            continue

        # 3. Deduplicate product IDs
        if pid in seen_product_ids:
            continue

        # 4. Check brand name
        raw_brand = item.get("brand_name")
        if not raw_brand or not str(raw_brand).strip():
            continue
        brand_name = str(raw_brand).strip()

        # 5. Manufacturer
        raw_mfr = item.get("manufacturer")
        manufacturer = str(raw_mfr).strip() if raw_mfr and str(raw_mfr).strip() else "Unknown Manufacturer"

        # 6. Price in INR
        raw_price = item.get("price_inr")
        try:
            price = float(raw_price) if raw_price is not None else 0.0
            if math.isnan(price) or price < 0:
                price = 0.0
            price = round(price, 2)
        except (ValueError, TypeError):
            price = 0.0

        # 7. Dosage form
        raw_form = item.get("dosage_form")
        dosage_form = str(raw_form).strip().title() if raw_form and str(raw_form).strip() else "Tablet"

        # 8. Pack size and unit
        raw_size = item.get("pack_size")
        try:
            pack_size = float(raw_size) if raw_size is not None else 1.0
            if math.isnan(pack_size) or pack_size <= 0:
                pack_size = 1.0
        except (ValueError, TypeError):
            pack_size = 1.0

        raw_unit = item.get("pack_unit")
        pack_unit = str(raw_unit).strip().lower() if raw_unit and str(raw_unit).strip() else "units"

        # 9. Ingredients and class
        raw_ingr = item.get("primary_ingredient")
        primary_ingredient = str(raw_ingr).strip() if raw_ingr and str(raw_ingr).strip() else "N/A"

        raw_str = item.get("primary_strength")
        primary_strength = str(raw_str).strip() if raw_str and str(raw_str).strip() else "N/A"

        raw_class = item.get("therapeutic_class")
        therapeutic_class = str(raw_class).strip() if raw_class and str(raw_class).strip() else "General Therapeutic"

        seen_product_ids.add(pid)
        cleaned_rows.append({
            "product_id": pid,
            "brand_name": brand_name,
            "manufacturer": manufacturer,
            "price_inr": price,
            "dosage_form": dosage_form,
            "pack_size": pack_size,
            "pack_unit": pack_unit,
            "primary_ingredient": primary_ingredient,
            "primary_strength": primary_strength,
            "therapeutic_class": therapeutic_class,
            "is_discontinued": 0,
        })

        if len(cleaned_rows) >= target_count:
            break

    print(f"[Cleaning Pipeline] Collected {len(cleaned_rows):,} clean medicines. Writing to CSV...")

    fieldnames = [
        "product_id",
        "brand_name",
        "manufacturer",
        "price_inr",
        "dosage_form",
        "pack_size",
        "pack_unit",
        "primary_ingredient",
        "primary_strength",
        "therapeutic_class",
        "is_discontinued",
    ]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cleaned_rows)

    print(f"[Cleaning Pipeline] Cleaned CSV generated: {out_path} ({len(cleaned_rows):,} rows)")
    return out_path


def import_medicines_to_sqlite(
    csv_path: Path | str | None = None,
    db_path: Path | str | None = None,
    reset: bool = False,
) -> int:
    """
    Imports the cleaned medicines CSV into SQLite 'medicines' table.
    Ensures database schema exists and uses batch insertion for maximum speed.
    """
    source_csv = Path(csv_path) if csv_path else DEFAULT_CLEAN_OUTPUT
    if not source_csv.is_file():
        raise FileNotFoundError(f"Cleaned medicines CSV not found at {source_csv}. Run clean_and_export_dataset first.")

    target_db = Path(db_path) if db_path else config.DB_PATH
    init_database(target_db)

    conn = get_connection(target_db)
    try:
        cursor = conn.cursor()

        if reset:
            cursor.execute("DELETE FROM transactions;")
            cursor.execute("DELETE FROM orders;")
            cursor.execute("DELETE FROM inventory;")
            cursor.execute("DELETE FROM medicines;")
            try:
                cursor.execute("DELETE FROM sqlite_sequence WHERE name='medicines';")
            except sqlite3.OperationalError:
                pass
            conn.commit()
            print(f"[Database Import] Cleared previous medicine records in {target_db}.")

        records = []
        with open(source_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append((
                    int(row["product_id"]),
                    row["brand_name"],
                    row["manufacturer"],
                    float(row["price_inr"]),
                    row["dosage_form"],
                    float(row["pack_size"]),
                    row["pack_unit"],
                    row["primary_ingredient"],
                    row["primary_strength"],
                    row["therapeutic_class"],
                    0,
                ))

        sql = """
            INSERT OR REPLACE INTO medicines (
                product_id, brand_name, manufacturer, price_inr, dosage_form,
                pack_size, pack_unit, primary_ingredient, primary_strength,
                therapeutic_class, is_discontinued
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        cursor.executemany(sql, records)
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM medicines;")
        total_in_db = cursor.fetchone()[0]
        print(f"[Database Import] Successfully inserted {len(records):,} records. Total medicines in SQLite: {total_in_db:,}")
        return total_in_db

    finally:
        conn.close()


if __name__ == "__main__":
    clean_csv = clean_and_export_dataset(target_count=TARGET_ACTIVE_COUNT)
    import_medicines_to_sqlite(csv_path=clean_csv, reset=True)
