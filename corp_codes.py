import os
import io
import zipfile
import xml.etree.ElementTree as ET

import requests
from dotenv import load_dotenv

load_dotenv()

# .env의 DART_API_KEY로 DART Open API 인증
api_key = os.environ["DART_API_KEY"]

# Supabase 설정
# SUPABASE_URL은 보통 'https://<project>.supabase.co/rest/v1' 형태를 권장합니다.
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates", # 중복 시 업데이트(UPSERT)
}

# DART 기업 고유번호 전체 목록 API
API_URL = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={api_key}"

# 1. API 요청 → ZIP 바이너리 수신
print("1. DART API 요청 중...")
response = requests.get(API_URL, timeout=60)
response.raise_for_status()
print(f"   응답 크기: {len(response.content):,} bytes")

# 2. ZIP 압축 해제 → CORPCODE.xml 추출
print("2. ZIP 파일 압축 해제 중...")
with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
    xml_data = zf.read("CORPCODE.xml")

# 3. XML 파싱
print("3. XML 파싱 중...")
root = ET.fromstring(xml_data)

records = []
for item in root.findall("list"):
    records.append({
        "corp_code":     item.findtext("corp_code", "").strip(),
        "corp_name":     item.findtext("corp_name", "").strip(),
        "corp_eng_name": item.findtext("corp_eng_name", "").strip() or None,
        "stock_code":    item.findtext("stock_code", "").strip() or None,
        "modify_date":   item.findtext("modify_date", "").strip(),
    })

print(f"   총 {len(records):,}개 기업 데이터 파싱 완료")

# 4. Supabase 적재 (배치 100건씩)
print("4. Supabase corp_codes 테이블 적재 중...")
BATCH_SIZE = 100
total_batches = (len(records) + BATCH_SIZE - 1) // BATCH_SIZE

for i in range(0, len(records), BATCH_SIZE):
    batch = records[i:i + BATCH_SIZE]
    batch_num = i // BATCH_SIZE + 1
    
    # POST 요청으로 데이터 전송 (Prefer 헤더로 UPSERT 동작)
    res = requests.post(
        f"{SUPABASE_URL}/corp_codes",
        headers=SUPABASE_HEADERS,
        json=batch,
        timeout=30,
    )
    
    if res.status_code not in (200, 201):
        print(f"   [오류] batch {batch_num}/{total_batches}: {res.status_code} {res.text}")
    else:
        # 진행 상황 출력 (10배수 배치마다 혹은 마지막 배치)
        if batch_num % 10 == 0 or i + BATCH_SIZE >= len(records):
            print(f"   진행 중: batch {batch_num}/{total_batches} ({min(i + BATCH_SIZE, len(records))} / {len(records)})")

print(f"   Supabase 적재 완료 ({len(records):,}건)")
