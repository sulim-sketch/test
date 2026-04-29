import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

DART_API_KEY = os.environ["DART_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

BSNS_YEAR = "2023"
TEST_STOCK_COUNT = 5  # 테스트할 종목 수

PERIOD_CODES = {
    "1Q":     "11013",
    "2Q":     "11012",
    "3Q":     "11014",
    "Annual": "11011",
}


def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }


def load_sample_corp_codes(n):
    """listed_stocks에서 n개 종목의 corp_code를 반환."""
    resp = requests.get(
        f"{SUPABASE_URL}/listed_stocks",
        headers=supabase_headers(),
        params={"select": "ISU_SRT_CD,ISU_NM", "limit": n, "ISU_NM": "not.ilike.*우선주*"},
    )
    resp.raise_for_status()
    stock_codes = [row["ISU_SRT_CD"] for row in resp.json()]

    corp_codes = []
    for stock_code in stock_codes:
        resp = requests.get(
            f"{SUPABASE_URL}/corp_codes",
            headers=supabase_headers(),
            params={"select": "corp_code,stock_code", "stock_code": f"eq.{stock_code}"},
        )
        resp.raise_for_status()
        data = resp.json()
        if data:
            corp_codes.append({"stock_code": stock_code, "corp_code": data[0]["corp_code"]})

    return corp_codes


def fetch_multi_acnt(corp_codes_str, bsns_year, reprt_code, period_label):
    """fnlttMultiAcnt API 호출."""
    url = "https://opendart.fss.or.kr/api/fnlttMultiAcnt.json"
    resp = requests.get(url, params={
        "crtfc_key": DART_API_KEY,
        "corp_code": corp_codes_str,
        "bsns_year": bsns_year,
        "reprt_code": reprt_code,
    })
    resp.encoding = "utf-8"
    data = resp.json()

    status = data.get("status")
    message = data.get("message", "")
    items = data.get("list", [])

    print(f"\n[{period_label}] status={status}, message={message}, 항목 수={len(items)}")
    return items


def main():
    print(f"=== fnlttMultiAcnt API 테스트 (bsns_year={BSNS_YEAR}) ===\n")

    print(f"1. Supabase에서 샘플 {TEST_STOCK_COUNT}개 corp_code 조회 중...")
    samples = load_sample_corp_codes(TEST_STOCK_COUNT)
    if not samples:
        print("corp_code 조회 실패")
        return

    for s in samples:
        print(f"   {s['stock_code']} → {s['corp_code']}")

    corp_codes_str = ",".join(s["corp_code"] for s in samples)
    print(f"\n2. corp_code 파라미터: {corp_codes_str}")

    print("\n3. 분기별 API 호출 중...")
    all_results = {}
    for period_label, reprt_code in PERIOD_CODES.items():
        items = fetch_multi_acnt(corp_codes_str, BSNS_YEAR, reprt_code, period_label)
        all_results[period_label] = items

        if items:
            # 첫 번째 항목 샘플 출력
            sample = items[0]
            print(f"  샘플 항목: corp_code={sample.get('corp_code')}, "
                  f"fs_div={sample.get('fs_div')}, "
                  f"account_nm={sample.get('account_nm')}, "
                  f"thstrm_amount={sample.get('thstrm_amount')}")

    print("\n4. corp_code별 수신 항목 수 요약:")
    for period_label, items in all_results.items():
        corp_counts = {}
        for item in items:
            cc = item.get("corp_code", "?")
            corp_counts[cc] = corp_counts.get(cc, 0) + 1
        print(f"  [{period_label}] " + ", ".join(f"{cc}:{cnt}개" for cc, cnt in corp_counts.items()))

    print("\n5. 원본 응답 일부 (1Q 첫 10개):")
    for item in all_results.get("1Q", [])[:10]:
        print(f"   {json.dumps(item, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
