"""
Seeds essential medicines across the entire alphabet (B through Z)
into the database and stocks them across pharmacies.
"""

from datetime import date, timedelta
from pathlib import Path
from backend.app import config
from backend.app.database.connection import get_connection

POPULAR_MEDICINES = [
    # (product_id, brand_name, manufacturer, price_inr, dosage_form, pack_size, pack_unit, ingredient, strength, category, batch_no, expiry_offset_days)
    (20001, "Becosules Z Capsules", "Pfizer Ltd", 52.00, "Capsule", 20.0, "capsules", "Vitamin B-Complex with Zinc", "50mg", "Vitamins & Supplements", "BZ-6110", 400),
    (20002, "Calpol 500 Tablet", "GlaxoSmithKline", 61.20, "Tablet", 15.0, "tablets", "Paracetamol", "500mg", "Analgesic & Antipyretic", "CP-8331", 22),
    (20003, "Combiflam Tablet", "Sanofi India Ltd", 48.50, "Tablet", 20.0, "tablets", "Ibuprofen + Paracetamol", "400mg/325mg", "Analgesic & Antipyretic", "CB-1044", 450),
    (20004, "Cipcal 500 Tablet", "Cipla Ltd", 83.50, "Tablet", 15.0, "tablets", "Calcium with Vitamin D3", "500mg", "Vitamins & Supplements", "CP-9102", 28),
    (20005, "Dolo 650mg Tablet", "Micro Labs Ltd", 32.50, "Tablet", 15.0, "tablets", "Paracetamol", "650mg", "Analgesic & Antipyretic", "DL-9082", 365),
    (20006, "Deriphyllin Retard 150", "Zydus Cadila", 38.00, "Tablet", 30.0, "tablets", "Theophylline + Etophylline", "150mg", "Respiratory", "DR-4401", 500),
    (20007, "Digene Gel Mint", "Abbott Healthcare", 145.00, "Syrup", 200.0, "ml", "Magnesium Hydroxide + Simethicone", "Standard", "Antacid & GI", "DG-3312", 300),
    (20008, "Ecosprin 75 Tablet", "USV Ltd", 9.80, "Tablet", 14.0, "tablets", "Aspirin", "75mg", "Cardiovascular", "EC-7721", 550),
    (20009, "Electral Powder", "FDC Ltd", 22.00, "Powder", 21.8, "g", "Oral Rehydration Salts (ORS)", "Standard", "Electrolytes", "EL-1205", 600),
    (20010, "Gelusil MPS Liquid", "Pfizer Ltd", 115.00, "Syrup", 200.0, "ml", "Aluminium Hydroxide + Simethicone", "Standard", "Antacid & GI", "GL-4402", 400),
    (20011, "Glycomet 500mg Tablet", "USV Ltd", 45.00, "Tablet", 20.0, "tablets", "Metformin", "500mg", "Diabetes Care", "GL-8820", 365),
    (20012, "Metolar 50 Tablet", "Cipla Ltd", 154.00, "Tablet", 15.0, "tablets", "Metoprolol Succinate", "50mg", "Cardiovascular", "MT-5501", 420),
    (20013, "Montair-LC Tablet", "Cipla Ltd", 168.00, "Tablet", 10.0, "tablets", "Levocetirizine + Montelukast", "5mg/10mg", "Respiratory", "ML-2034", 250),
    (20014, "Oflox 200mg Eye Drops", "Cipla Ltd", 65.00, "Drops", 10.0, "ml", "Ofloxacin", "0.3%", "Ophthalmic", "OF-1004", -16),  # Expired
    (20015, "Pan-D Capsule", "Alkem Laboratories", 199.50, "Capsule", 15.0, "capsules", "Pantoprazole + Domperidone", "40mg/30mg", "Antacid & GI", "PD-3109", 220),
    (20016, "Pantocid 40 Tablet", "Sun Pharma", 172.00, "Tablet", 15.0, "tablets", "Pantoprazole", "40mg", "Antacid & GI", "PC-8801", 480),
    (20017, "Paracip 500 Tablet", "Cipla Ltd", 20.50, "Tablet", 10.0, "tablets", "Paracetamol", "500mg", "Analgesic & Antipyretic", "PC-1001", 380),
    (20018, "Septran Pediatric Susp", "GSK Pharma", 48.00, "Syrup", 50.0, "ml", "Trimethoprim + Sulfamethoxazole", "Standard", "Antibiotic", "SP-2918", -45),  # Expired
    (20019, "Telma 40mg Tablet", "Glenmark", 142.80, "Tablet", 30.0, "tablets", "Telmisartan", "40mg", "Cardiovascular", "TL-4401", 500),
    (20020, "Thyronorm 50mcg Tablet", "Abbott Healthcare", 182.00, "Tablet", 100.0, "tablets", "Thyroxine Sodium", "50mcg", "Endocrine", "TH-9011", 220),
    (20021, "Volini Gel 30g", "Sun Pharma", 125.00, "Gel", 30.0, "g", "Diclofenac Diethylamine", "1.16%", "Pain Relief Topical", "VL-3301", 450),
    (20022, "Zifi 200 Tablet", "FDC Ltd", 112.00, "Tablet", 10.0, "tablets", "Cefixime", "200mg", "Antibiotic", "ZF-2001", 340),
    (20023, "Zincovit Tablet", "Apex Laboratories", 110.00, "Tablet", 15.0, "tablets", "Multivitamins with Zinc", "Standard", "Vitamins & Supplements", "ZN-9002", 400),
]


def seed_alphabet_medicines(db_path: Path | str | None = None) -> None:
    target_path = Path(db_path) if db_path else config.DB_PATH
    conn = get_connection(target_path)
    today = date.today()

    try:
        cursor = conn.cursor()

        # Fetch pharmacies
        cursor.execute("SELECT id FROM pharmacies;")
        pharmacies = [r["id"] for r in cursor.fetchall()]
        if not pharmacies:
            pharmacies = [1, 2]

        print(f"Seeding {len(POPULAR_MEDICINES)} popular B-Z medicines across all pharmacies...")

        for item in POPULAR_MEDICINES:
            pid, brand, mfr, price, form, psize, punit, ingr, strength, cat, batch, offset_days = item
            exp_date = (today + timedelta(days=offset_days)).isoformat()

            # Insert or replace medicine
            cursor.execute(
                """
                INSERT INTO medicines (
                    product_id, brand_name, manufacturer, price_inr, dosage_form,
                    pack_size, pack_unit, primary_ingredient, primary_strength,
                    therapeutic_class, batch_no, expiry_date, is_discontinued
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(product_id) DO UPDATE SET
                    brand_name = excluded.brand_name,
                    price_inr = excluded.price_inr,
                    batch_no = excluded.batch_no,
                    expiry_date = excluded.expiry_date;
                """,
                (pid, brand, mfr, price, form, psize, punit, ingr, strength, cat, batch, exp_date),
            )
            med_id = cursor.lastrowid
            if not med_id or med_id == 0:
                cursor.execute("SELECT id FROM medicines WHERE product_id = ?;", (pid,))
                med_id = cursor.fetchone()["id"]

            # Stock at ALL pharmacies with safe realistic inventory
            for p_id in pharmacies:
                # Give Pharmacy 1 and 2 varied stocks
                if "Expired" in brand or offset_days < 0:
                    stock = 12
                    min_stock = 10
                elif "Dolo" in brand or "Calpol" in brand or "Becosules" in brand:
                    stock = 140
                    min_stock = 30
                elif "Thyronorm" in brand:
                    stock = 8  # Low stock
                    min_stock = 20
                else:
                    stock = 50 + (med_id * 7) % 60
                    min_stock = 15

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
                    (p_id, med_id, stock, min_stock, batch, exp_date),
                )

        conn.commit()
        print("Successfully seeded popular medicines across all letters B-Z into all pharmacies!")
    finally:
        conn.close()


if __name__ == "__main__":
    seed_alphabet_medicines()
