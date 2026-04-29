import os
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

def get_kst_now():
    """항상 한국 시간(UTC+9) 기준 현재 시간을 반환합니다."""
    return datetime.now(timezone(timedelta(hours=9)))

def fetch_all_active_tickers_from_db(url, headers):
    """현재 DB에 저장된 활성화된(is_active=True) 종목들의 ISU_SRT_CD 목록을 가져옵니다."""
    active_tickers = []
    limit = 1000
    offset = 0
    
    while True:
        target_url = f"{url}/listed_stocks?select=ISU_SRT_CD&is_active=eq.true&limit={limit}&offset={offset}"
        res = requests.get(target_url, headers=headers)
        if res.status_code != 200:
            print(f"[{datetime.now()}] [Error] Failed to fetch active tickers from DB: {res.status_code} {res.text}")
            break
            
        data = res.json()
        if not data:
            break
            
        active_tickers.extend([item["ISU_SRT_CD"] for item in data])
        if len(data) < limit:
            break
        offset += limit
        
    return set(active_tickers)

def run_cron_listed_stocks():
    """
    KRX API로부터 최근 영업일의 상장 종목 정보를 가져와 Supabase에 UPSERT하고,
    상장폐지된 종목(API에 없는 종목)은 is_active를 False로 변경합니다.
    """
    load_dotenv()
    
    # 설정값 로드
    KRX_API_KEY = os.environ.get("KRX_API_KEY")
    SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
    SUPABASE_KEY = os.environ["SUPABASE_KEY"]
    
    SUPABASE_HEADERS = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates", # 중복 시 업데이트(UPSERT)
    }

    # 1. 데이터가 있는 최근 영업일 찾기
    # 한국 시간 기준 어제부터 역추적 (최대 10일까지)
    kst_now = get_kst_now()
    found_date = None
    all_api_records = []
    api_tickers = set()
    
    markets = [
        ("stk_isu_base_info", "KOSPI"),
        ("ksq_isu_base_info", "KOSDAQ"),
        ("knx_isu_base_info", "KONEX")
    ]

    print(f"[{datetime.now()}] Searching for the latest trading date...")
    for i in range(1, 11):
        test_date = (kst_now - timedelta(days=i)).strftime("%Y%m%d")
        
        # 첫 번째 시장(KOSPI) 데이터를 기준으로 영업일 여부 판단
        endpoint, market_name = markets[0]
        url = f"https://data-dbg.krx.co.kr/svc/apis/sto/{endpoint}?basDd={test_date}"
        headers = {"AUTH_KEY": KRX_API_KEY}
        
        try:
            res = requests.get(url, headers=headers, timeout=30)
            res.raise_for_status()
            data = res.json()
            
            if "OutBlock_1" in data and data["OutBlock_1"]:
                found_date = test_date
                print(f"[{datetime.now()}] Found trading data for date: {found_date}")
                break
            else:
                print(f"[{datetime.now()}] No data for {test_date}, checking previous day...")
        except Exception as e:
            print(f"[{datetime.now()}] [Error] API check failed for {test_date}: {e}")
            continue

    if not found_date:
        print(f"[{datetime.now()}] Could not find any trading data in the last 10 days. Task aborted.")
        return

    # 2. 찾은 날짜(found_date)로 모든 시장 데이터 수집
    current_time = datetime.now(timezone.utc).isoformat()
    for endpoint, market_name in markets:
        url = f"https://data-dbg.krx.co.kr/svc/apis/sto/{endpoint}?basDd={found_date}"
        headers = {"AUTH_KEY": KRX_API_KEY}

        print(f"[{datetime.now()}] Fetching {market_name} data for {found_date}...")
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            records = data.get("OutBlock_1", [])
            for record in records:
                ticker = record.get("ISU_SRT_CD")
                if ticker:
                    record["is_active"] = True
                    record["market"] = market_name
                    record["updated_at"] = current_time
                    all_api_records.append(record)
                    api_tickers.add(ticker)
            print(f"[{datetime.now()}] Received {len(records):,} records from {market_name}.")
        except Exception as e:
            print(f"[{datetime.now()}] [Error] API request failed for {market_name}: {e}")

    # 3. Supabase UPSERT (데이터 적재 및 갱신)
    print(f"[{datetime.now()}] Starting UPSERT for {len(all_api_records):,} records...")
    upsert_url = f"{SUPABASE_URL}/listed_stocks?on_conflict=ISU_SRT_CD"
    
    BATCH_SIZE = 100
    for i in range(0, len(all_api_records), BATCH_SIZE):
        batch = all_api_records[i:i + BATCH_SIZE]
        res = requests.post(upsert_url, headers=SUPABASE_HEADERS, json=batch, timeout=30)
        
        if res.status_code not in (200, 201):
            print(f"[{datetime.now()}] [Error] UPSERT Batch {i//BATCH_SIZE + 1} failed: {res.status_code} {res.text}")
        else:
            if (i + BATCH_SIZE) % 1000 == 0 or i + BATCH_SIZE >= len(all_api_records):
                print(f"[{datetime.now()}] UPSERT Progress: {min(i + BATCH_SIZE, len(all_api_records)):,} / {len(all_api_records):,}")

    # 4. 상장폐지 처리 (Delisting)
    print(f"[{datetime.now()}] Checking for delisted stocks...")
    db_active_tickers = fetch_all_active_tickers_from_db(SUPABASE_URL, SUPABASE_HEADERS)
    delisted_tickers = db_active_tickers - api_tickers
    
    if delisted_tickers:
        print(f"[{datetime.now()}] Found {len(delisted_tickers):,} delisted stocks. Updating status...")
        delisted_list = list(delisted_tickers)
        for i in range(0, len(delisted_list), BATCH_SIZE):
            batch_tickers = delisted_list[i:i + BATCH_SIZE]
            ticker_filter = ",".join([f'"{t}"' for t in batch_tickers])
            
            patch_url = f"{SUPABASE_URL}/listed_stocks?ISU_SRT_CD=in.({ticker_filter})"
            patch_headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
            }
            res = requests.patch(
                patch_url, 
                headers=patch_headers, 
                json={"is_active": False, "updated_at": current_time},
                timeout=30
            )
            
            if res.status_code not in (200, 204):
                print(f"[{datetime.now()}] [Error] Failed to update delisted status: {res.status_code} {res.text}")
            else:
                print(f"[{datetime.now()}] Updated delisted status for {len(batch_tickers)} stocks.")
    else:
        print(f"[{datetime.now()}] No delisted stocks found.")

    print(f"[{datetime.now()}] Cron task for listed_stocks completed successfully.")

if __name__ == "__main__":
    run_cron_listed_stocks()
