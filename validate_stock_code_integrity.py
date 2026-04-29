import os
import requests
import pandas as pd
from dotenv import load_dotenv

def fetch_all_from_supabase(url, headers, table_name, select="*", filters=""):
    """Supabase에서 페이지네이션을 처리하여 모든 데이터를 가져옵니다."""
    all_data = []
    limit = 1000
    offset = 0
    
    while True:
        target_url = f"{url}/{table_name}?select={select}&limit={limit}&offset={offset}{filters}"
        res = requests.get(target_url, headers=headers)
        if res.status_code != 200:
            print(f"오류 발생 ({table_name}): {res.status_code} {res.text}")
            break
            
        data = res.json()
        if not data:
            break
            
        all_data.extend(data)
        if len(data) < limit:
            break
        offset += limit
        
    return all_data

def validate_stock_code_integrity():
    """
    KRX 상장종목(listed_stocks)과 DART 기업코드(corp_codes) 간의 정합성을 검증합니다.
    DART의 stock_code는 법인 기준이므로 종목별로 생성되는 '우선주' 등은 제외하고 검증합니다.
    """
    load_dotenv()
    
    SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
    SUPABASE_KEY = os.environ["SUPABASE_KEY"]
    SUPABASE_HEADERS = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }

    print("1. 검증을 위한 데이터 수집 중...")
    
    # listed_stocks 데이터 가져오기 (전체 행)
    print("   - listed_stocks 테이블 조회 중...")
    listed_stocks_data = fetch_all_from_supabase(
        SUPABASE_URL, SUPABASE_HEADERS, "listed_stocks"
    )
    
    # corp_codes에서 stock_code 목록 가져오기 (null 제외)
    print("   - corp_codes 테이블 조회 중...")
    corp_codes_data = fetch_all_from_supabase(
        SUPABASE_URL, SUPABASE_HEADERS, "corp_codes", select="stock_code", filters="&stock_code=not.is.null"
    )
    corp_set = {item["stock_code"] for item in corp_codes_data if item.get("stock_code")}

    print("\n2. 정합성 검증 시작")
    
    # 필터링 로직: 
    # 1. corp_codes에 없는 코드 추출
    # 2. 그 중 "우선주"인 것은 정상적인 케이스로 간주하여 제외
    missing_entries = []
    for row in listed_stocks_data:
        code = row.get("ISU_SRT_CD")
        name = row.get("ISU_NM") or ""
        
        if code not in corp_set:
            if "우선주" in name:
                continue # 우선주는 DART 코드에 없을 수 있으므로 패스
            missing_entries.append(row)

    # 결과 출력
    print(f"   - 총 검증 대상 (listed_stocks): {len(listed_stocks_data):,}개")
    print(f"   - corp_codes 보유 코드 수: {len(corp_set):,}개")
    
    if not missing_entries:
        print("\n✅ [검증 성공] listed_stocks의 모든 주요 종목 코드가 corp_codes와 일치합니다.")
        print("   (참고: 우선주 등 법인 대표 코드가 아닌 종목은 검증 대상에서 제외됨)")
    else:
        print(f"\n❌ [검증 실패] {len(missing_entries):,}개의 종목 코드가 corp_codes에 존재하지 않습니다.")
        print("-" * 40)
        print(f"{'종목코드':<10} | {'종목명'}")
        print("-" * 40)
        for entry in missing_entries:
            print(f"{entry.get('ISU_SRT_CD', 'N/A'):<10} | {entry.get('ISU_NM', 'N/A')}")
        print("-" * 40)

if __name__ == "__main__":
    validate_stock_code_integrity()
