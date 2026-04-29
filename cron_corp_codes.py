import os
import io
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

def run_cron_corp_codes():
    """
    Fetches DART corp codes and UPSERTs them into Supabase.
    Note: 'corp_code' column MUST have a UNIQUE constraint in the database.
    """
    # 0. Load environment variables
    load_dotenv()
    
    DART_API_KEY = os.environ.get("DART_API_KEY")
    SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
    SUPABASE_KEY = os.environ["SUPABASE_KEY"]
    
    # Supabase UPSERT Headers
    # 1. 'Prefer: resolution=merge-duplicates' tells Supabase to update on conflict.
    # 2. To use this, the table must have a UNIQUE constraint on the identifying column.
    SUPABASE_HEADERS = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates", 
    }

    print(f"[{datetime.now()}] Requesting DART API...")
    DART_URL = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={DART_API_KEY}"
    
    try:
        # 1. Request DART API and Extract ZIP
        response = requests.get(DART_URL, timeout=60)
        response.raise_for_status()
        
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            xml_data = zf.read("CORPCODE.xml")

        # 2. Parse XML and Process Data
        print(f"[{datetime.now()}] Parsing XML data...")
        root = ET.fromstring(xml_data)
        
        # Current time for updated_at field
        current_time = datetime.now(timezone.utc).isoformat()
        
        records = []
        for item in root.findall("list"):
            corp_code = item.findtext("corp_code", "").strip()
            corp_name = item.findtext("corp_name", "").strip()
            corp_eng_name = item.findtext("corp_eng_name", "").strip() or None
            stock_code = item.findtext("stock_code", "").strip() or None
            modify_date = item.findtext("modify_date", "").strip()
            
            records.append({
                "corp_code": corp_code,
                "corp_name": corp_name,
                "corp_eng_name": corp_eng_name,
                "stock_code": stock_code,
                "modify_date": modify_date,
                "updated_at": current_time 
            })

        total_count = len(records)
        print(f"[{datetime.now()}] Parsed {total_count:,} records. Starting Supabase UPSERT...")

        # 3. Supabase UPSERT (Batch size: 100)
        # We specify 'on_conflict=corp_code' to tell Postgres which column to check for duplicates.
        upsert_url = f"{SUPABASE_URL}/corp_codes?on_conflict=corp_code"
        
        BATCH_SIZE = 100
        for i in range(0, total_count, BATCH_SIZE):
            batch = records[i:i + BATCH_SIZE]
            
            res = requests.post(
                upsert_url,
                headers=SUPABASE_HEADERS,
                json=batch,
                timeout=30,
            )
            
            if res.status_code not in (200, 201):
                # If you see 400 error here, please check if 'corp_code' has a UNIQUE constraint in Supabase.
                print(f"[{datetime.now()}] [Error] Batch {i//BATCH_SIZE + 1}: {res.status_code} {res.text}")
            else:
                if (i + BATCH_SIZE) % 10000 == 0 or i + BATCH_SIZE >= total_count:
                    print(f"[{datetime.now()}] Progress: {min(i + BATCH_SIZE, total_count):,} / {total_count:,}")

        print(f"[{datetime.now()}] All data upserted successfully.")

    except Exception as e:
        print(f"[{datetime.now()}] Critical error occurred: {e}")

if __name__ == "__main__":
    run_cron_corp_codes()
