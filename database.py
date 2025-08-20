import sqlite3
from typing import Dict, Any

def setup_database(db_name: str = "invoices.db"):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE,
            vendor_name TEXT,
            invoice_number TEXT,
            invoice_date TEXT,
            total_amount REAL,
            vendor_gstin TEXT,
            customer_gstin TEXT,
            processing_tier TEXT,
            status TEXT,
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            filename TEXT
        )
        """
    )
    cursor.execute("PRAGMA table_info(invoices)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    wanted = {
        "filename": "ALTER TABLE invoices ADD COLUMN filename TEXT",
        "invoice_number": "ALTER TABLE invoices ADD COLUMN invoice_number TEXT",
        "vendor_gstin": "ALTER TABLE invoices ADD COLUMN vendor_gstin TEXT",
        "customer_gstin": "ALTER TABLE invoices ADD COLUMN customer_gstin TEXT"
    }
    for col, stmt in wanted.items():
        if col not in existing_cols:
            try:
                cursor.execute(stmt)
                print(f"Added missing column: {col}")
            except Exception as e:
                print(f"Could not add column {col}: {e}")
    conn.commit()
    conn.close()
    print("Database setup / migration complete.")

def save_to_db(data: Dict[str, Any], db_name: str = "invoices.db"):
    if not data.get("file_path"):
        print("Cannot save record without file_path")
        return
    filename = data.get("file_path").split('/')[-1]
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO invoices (file_path, vendor_name, invoice_number, invoice_date, total_amount, vendor_gstin, customer_gstin, processing_tier, status, filename)
        VALUES (:file_path, :vendor_name, :invoice_number, :invoice_date, :total_amount, :vendor_gstin, :customer_gstin, :processing_tier, :status, :filename)
        ON CONFLICT(file_path) DO UPDATE SET
            vendor_name=excluded.vendor_name,
            invoice_number=excluded.invoice_number,
            invoice_date=excluded.invoice_date,
            total_amount=excluded.total_amount,
            vendor_gstin=excluded.vendor_gstin,
            customer_gstin=excluded.customer_gstin,
            processing_tier=excluded.processing_tier,
            status=excluded.status,
            filename=excluded.filename
        """,
        {
            "file_path": data.get("file_path"),
            "vendor_name": data.get("vendor_name"),
            "invoice_number": data.get("invoice_number"),
            "invoice_date": data.get("invoice_date"),
            "total_amount": data.get("total_amount"),
            "vendor_gstin": data.get("vendor_gstin"),
            "customer_gstin": data.get("customer_gstin"),
            "processing_tier": data.get("processing_tier"),
            "status": data.get("status", "SUCCESS"),
            "filename": filename
        }
    )
    conn.commit()
    conn.close()
    print(f"Saved to DB ({data.get('processing_tier')}): {filename}")

def get_result_by_filename(filename: str, db_name: str = "invoices.db"):
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM invoices WHERE filename = ?", (filename,))
    result = cursor.fetchone()
    conn.close()
    return dict(result) if result else None