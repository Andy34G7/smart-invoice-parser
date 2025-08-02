import sqlite3

def setup_database(db_name="invoices.db"):
    """Creates the database and the invoices table."""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT UNIQUE,
        vendor_name TEXT,
        invoice_date TEXT,
        total_amount REAL,
        processing_tier TEXT,
        status TEXT,
        extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()
    print("Database setup complete.")

def save_to_db(data, db_name="invoices.db"):
    """Saves or updates a record of extracted data to the SQLite database."""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO invoices (file_path, vendor_name, invoice_date, total_amount, processing_tier, status)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        data.get("file_path"),
        data.get("vendor_name"),
        data.get("invoice_date"),
        data.get("total_amount"),
        data.get("processing_tier"),
        data.get("status", "SUCCESS")
    ))
    conn.commit()
    conn.close()
    print(f"'{data.get('file_path')}' saved to db using {data.get('processing_tier')}.")

def get_result_by_filename(filename, db_name="invoices.db"):
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM invoices WHERE file_path LIKE ?", ('%' + filename + '%',))
    result = cursor.fetchone()
    conn.close()
    return dict(result) if result else None