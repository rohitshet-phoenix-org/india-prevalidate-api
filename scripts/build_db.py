#!/usr/bin/env python3
"""
Build SQLite database from public-domain IFSC and PIN code datasets.

Data sources:
  - IFSC: Razorpay IFSC dataset (MIT license, public-domain data)
    https://github.com/razorpay/ifsc/releases
  - PIN codes: India Post All India Pincode Directory (data.gov.in, public domain)
    https://github.com/thatisuday/indian-pincode-database

Usage:
  python scripts/build_db.py            # Downloads data and builds data/prevalidate.db
  python scripts/build_db.py --skip-download  # Builds DB from already-downloaded CSVs
"""

import csv
import os
import sqlite3
import sys
import urllib.request

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
DB_PATH = os.path.join(DATA_DIR, "prevalidate.db")

IFSC_CSV_URL = "https://github.com/razorpay/ifsc/releases/download/v2.0.57/IFSC.csv"
IFSC_CSV_PATH = os.path.join(DATA_DIR, "IFSC.csv")

PINCODE_CSV_URL = "https://raw.githubusercontent.com/thatisuday/indian-pincode-database/master/res/all_india_pin_code.csv"
PINCODE_CSV_PATH = os.path.join(DATA_DIR, "pincode_full.csv")


def download_file(url: str, dest: str, label: str) -> None:
    if os.path.exists(dest):
        size_mb = os.path.getsize(dest) / (1024 * 1024)
        print(f"  {label}: already downloaded ({size_mb:.1f} MB), skipping")
        return
    print(f"  {label}: downloading from {url} ...")
    urllib.request.urlretrieve(url, dest)
    size_mb = os.path.getsize(dest) / (1024 * 1024)
    print(f"  {label}: done ({size_mb:.1f} MB)")


def build_ifsc_table(conn: sqlite3.Connection) -> int:
    """Load IFSC.csv into the ifsc table. Returns row count."""
    print("\n[IFSC] Loading CSV ...")
    conn.execute("DROP TABLE IF EXISTS ifsc")
    conn.execute("""
        CREATE TABLE ifsc (
            code       TEXT PRIMARY KEY,
            bank       TEXT NOT NULL,
            branch     TEXT,
            centre     TEXT,
            district   TEXT,
            state      TEXT,
            address    TEXT,
            contact    TEXT,
            city       TEXT,
            micr       TEXT,
            imps       INTEGER DEFAULT 0,
            rtgs       INTEGER DEFAULT 0,
            neft       INTEGER DEFAULT 0,
            upi        INTEGER DEFAULT 0,
            swift      TEXT
        )
    """)

    count = 0
    batch = []
    with open(IFSC_CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ifsc = row.get("IFSC", "").strip()
            if not ifsc:
                continue
            batch.append((
                ifsc,
                row.get("BANK", "").strip(),
                row.get("BRANCH", "").strip(),
                row.get("CENTRE", "").strip(),
                row.get("DISTRICT", "").strip(),
                row.get("STATE", "").strip(),
                row.get("ADDRESS", "").strip(),
                row.get("CONTACT", "").strip(),
                row.get("CITY", "").strip(),
                row.get("MICR", "").strip(),
                1 if row.get("IMPS", "").strip().lower() == "true" else 0,
                1 if row.get("RTGS", "").strip().lower() == "true" else 0,
                1 if row.get("NEFT", "").strip().lower() == "true" else 0,
                1 if row.get("UPI", "").strip().lower() == "true" else 0,
                row.get("SWIFT", "").strip(),
            ))
            count += 1
            if len(batch) >= 5000:
                conn.executemany(
                    "INSERT OR REPLACE INTO ifsc VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    batch,
                )
                batch.clear()

    if batch:
        conn.executemany(
            "INSERT OR REPLACE INTO ifsc VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            batch,
        )
    conn.commit()

    conn.execute("CREATE INDEX IF NOT EXISTS idx_ifsc_bank ON ifsc(bank)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ifsc_state ON ifsc(state)")
    conn.commit()

    print(f"[IFSC] Loaded {count:,} records")
    return count


def build_pincode_table(conn: sqlite3.Connection) -> int:
    """Load pincode CSV into the pincode table. Returns row count.

    The India Post dataset has multiple post offices per pincode.
    We store all post offices and create the lookup by pincode.
    """
    print("\n[PIN code] Loading CSV ...")
    conn.execute("DROP TABLE IF EXISTS pincode")
    conn.execute("""
        CREATE TABLE pincode (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            pincode     TEXT NOT NULL,
            office_name TEXT,
            office_type TEXT,
            delivery    TEXT,
            division    TEXT,
            region      TEXT,
            circle      TEXT,
            taluk       TEXT,
            district    TEXT,
            state       TEXT
        )
    """)

    count = 0
    batch = []
    with open(PINCODE_CSV_PATH, "r", encoding="latin-1") as f:
        reader = csv.reader(f)
        # Clean headers: strip whitespace and surrounding quotes
        raw_headers = next(reader)
        headers = [h.strip().strip("'\"").strip() for h in raw_headers]
        for raw_row in reader:
            row = dict(zip(headers, [v.strip() for v in raw_row]))
            pincode = row.get("pincode", "").strip()
            if not pincode:
                continue
            batch.append((
                pincode,
                row.get("officeName", "").strip(),
                row.get("officeType", "").strip(),
                row.get("deliveryStatus", "").strip(),
                row.get("divisionName", "").strip(),
                row.get("regionName", "").strip(),
                row.get("circleName", "").strip(),
                row.get("taluk", "").strip(),
                row.get("districtName", "").strip(),
                row.get("stateName", "").strip().title(),
            ))
            count += 1
            if len(batch) >= 5000:
                conn.executemany(
                    "INSERT INTO pincode (pincode,office_name,office_type,delivery,division,region,circle,taluk,district,state) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    batch,
                )
                batch.clear()

    if batch:
        conn.executemany(
            "INSERT INTO pincode (pincode,office_name,office_type,delivery,division,region,circle,taluk,district,state) VALUES (?,?,?,?,?,?,?,?,?,?)",
            batch,
        )
    conn.commit()

    conn.execute("CREATE INDEX IF NOT EXISTS idx_pincode_code ON pincode(pincode)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pincode_state ON pincode(state)")
    conn.commit()

    # Also create a deduplicated view: one row per pincode (first post office)
    conn.execute("DROP VIEW IF EXISTS pincode_unique")
    conn.execute("""
        CREATE VIEW pincode_unique AS
        SELECT pincode,
               office_name,
               office_type,
               delivery,
               division,
               region,
               circle,
               taluk,
               district,
               state
        FROM pincode
        GROUP BY pincode
    """)
    conn.commit()

    print(f"[PIN code] Loaded {count:,} records")
    return count


def main():
    skip_download = "--skip-download" in sys.argv

    os.makedirs(DATA_DIR, exist_ok=True)

    if not skip_download:
        print("Step 1: Downloading datasets ...")
        download_file(IFSC_CSV_URL, IFSC_CSV_PATH, "IFSC")
        download_file(PINCODE_CSV_URL, PINCODE_CSV_PATH, "PIN codes")
    else:
        print("Step 1: Skipping download (--skip-download)")
        for path, label in [(IFSC_CSV_PATH, "IFSC"), (PINCODE_CSV_PATH, "PIN codes")]:
            if not os.path.exists(path):
                print(f"  ERROR: {label} CSV not found at {path}")
                sys.exit(1)

    # Remove old DB if exists
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"\nRemoved old database: {DB_PATH}")

    print(f"\nStep 2: Building SQLite database at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    ifsc_count = build_ifsc_table(conn)
    pincode_count = build_pincode_table(conn)

    # Store metadata
    conn.execute("DROP TABLE IF EXISTS metadata")
    conn.execute("""
        CREATE TABLE metadata (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    from datetime import datetime, timezone
    conn.executemany("INSERT INTO metadata VALUES (?,?)", [
        ("ifsc_source", "Razorpay IFSC v2.0.57 (MIT license, public-domain data)"),
        ("ifsc_url", IFSC_CSV_URL),
        ("ifsc_count", str(ifsc_count)),
        ("pincode_source", "India Post All India Pincode Directory (data.gov.in, public domain)"),
        ("pincode_url", PINCODE_CSV_URL),
        ("pincode_count", str(pincode_count)),
        ("built_at", datetime.now(timezone.utc).isoformat()),
    ])
    conn.commit()

    # Final stats
    db_size = os.path.getsize(DB_PATH) / (1024 * 1024)
    print(f"\n{'='*50}")
    print(f"Database built successfully!")
    print(f"  IFSC records:    {ifsc_count:>10,}")
    print(f"  PIN code records:{pincode_count:>10,}")
    print(f"  Database size:   {db_size:>10.1f} MB")
    print(f"  Location:        {DB_PATH}")
    print(f"{'='*50}")

    conn.close()


if __name__ == "__main__":
    main()
