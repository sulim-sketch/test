import os
from datetime import datetime, timedelta, timezone

import requests
import pandas as pd
from dotenv import load_dotenv

def get_yesterday_kst() -> str:
    """한국시간(KST) 기준 전날 날짜 반환"""
    kst = timezone(timedelta(hours=9))
    yesterday = datetime.now(kst) - timedelta(days=1)
    return yesterday.strftime("%Y%m%d")

def crawl_listed_stocks_to_supabase():
    # .env 로드
    load_dotenv()
    
    # KRX 설정
    api_key = os.environ.get("KRX_API_KEY")
    if not api_key:
        print("오류: .env 파일에 KRX_API_KEY가 설정되어 있지 않습니다.")
        return

    # Supabase 설정
    SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
    SUPABASE_KEY = os.environ["SUPABASE_KEY"]
    SUPABASE_HEADERS = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates", # 중복 시 업데이트(UPSERT)
    }

    # 기준일자: 테스트를 위해 최근 영업일인 20260424 사용
    date = "20260424" 

    # 대상 시장 리스트 (API 엔드포인트, 시장 구분명)
    markets = [
        ("stk_isu_base_info", "KOSPI"),
        ("ksq_isu_base_info", "KOSDAQ"),
        ("knx_isu_base_info", "KONEX")
    ]

    all_records = []

    for endpoint, market_name in markets:
        # 1. KRX API 요청
        url = f"https://data-dbg.krx.co.kr/svc/apis/sto/{endpoint}?basDd={date}"
        headers = {"AUTH_KEY": api_key}

        print(f"\n[{market_name}] KRX API 요청 중... (기준일자: {date})")
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if "OutBlock_1" not in data or not data["OutBlock_1"]:
                print(f"   {market_name} 데이터가 없습니다.")
                continue

            records = data["OutBlock_1"]
            print(f"   {len(records):,}개 {market_name} 종목 데이터 수신 완료")

            # 2. 데이터 가공 (is_active, market 추가)
            for record in records:
                record["is_active"] = True
                record["market"] = market_name
            
            all_records.extend(records)

        except Exception as e:
            print(f"   {market_name} 요청 중 오류 발생: {e}")

    if not all_records:
        print("업로드할 데이터가 없습니다.")
        return

    # (선택 사항) 전체 데이터 엑셀 백업 저장
    df = pd.DataFrame(all_records)
    output_file = f"listed_stocks_combined_{date}.xlsx"
    df.to_excel(output_file, index=False)
    print(f"\n2. 전체 엑셀 백업 저장 완료: {output_file}")

    # 3. Supabase 적재 (배치 100건씩)
    print(f"3. Supabase listed_stocks 테이블 적재 중... (총 {len(all_records):,}건)")
    BATCH_SIZE = 100
    total_batches = (len(all_records) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(all_records), BATCH_SIZE):
        batch = all_records[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        
        res = requests.post(
            f"{SUPABASE_URL}/listed_stocks",
            headers=SUPABASE_HEADERS,
            json=batch,
            timeout=30,
        )
        
        if res.status_code not in (200, 201):
            print(f"   [오류] batch {batch_num}/{total_batches}: {res.status_code} {res.text}")
        else:
            if batch_num % 10 == 0 or i + BATCH_SIZE >= len(all_records):
                print(f"   진행 중: batch {batch_num}/{total_batches} ({min(i + BATCH_SIZE, len(all_records))} / {len(all_records)})")

    print(f"   Supabase 적재 완료 ({len(all_records):,}건)")

if __name__ == "__main__":
    crawl_listed_stocks_to_supabase()
