import os
import requests
from dotenv import load_dotenv

load_dotenv()

DART_API_KEY = os.environ["DART_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

BSNS_YEAR        = "2025"
ANNUAL_REPRT_CODE = "11011"

ACCOUNTS = [
    ("revenue",          "매출액",     True),
    ("operating_income", "영업이익",   False),
    ("net_income",       "당기순이익", False),
    ("asset",            "자산총계",   True),
    ("liability",        "부채총계",   True),
    ("equity",           "자본총계",   True),
]

SIPMAN   = 100_000
CHUNMAN  = 10_000_000
EOK      = 100_000_000
BAEK_EOK = 10_000_000_000
JO       = 1_000_000_000_000


def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }


def find_corp_code(stock_code):
    resp = requests.get(
        f"{SUPABASE_URL}/corp_codes",
        headers=supabase_headers(),
        params={"select": "corp_code", "stock_code": f"eq.{stock_code}"},
    )
    resp.raise_for_status()
    data = resp.json()
    return data[0]["corp_code"] if data else None


def fetch_stock_name(stock_code):
    resp = requests.get(
        f"{SUPABASE_URL}/listed_stocks",
        headers=supabase_headers(),
        params={"select": "ISU_ABBRV", "ISU_SRT_CD": f"eq.{stock_code}", "limit": 1},
    )
    resp.raise_for_status()
    data = resp.json()
    return data[0]["ISU_ABBRV"] if data else stock_code


def fetch_annual_items(corp_code):
    resp = requests.get(
        "https://opendart.fss.or.kr/api/fnlttSinglAcnt.json",
        params={
            "crtfc_key":  DART_API_KEY,
            "corp_code":  corp_code,
            "bsns_year":  BSNS_YEAR,
            "reprt_code": ANNUAL_REPRT_CODE,
        },
    )
    resp.encoding = "utf-8"
    data = resp.json()

    if data.get("status") != "000":
        raise ValueError(f"DART API 오류: {data.get('message', data.get('status'))}")

    return data.get("list", [])


def detect_fs_div(items):
    for item in items:
        if item.get("fs_div") == "CFS":
            return "CFS"
    return "OFS"


def find_item(items, keyword, exact, fs_div):
    for item in items:
        if item.get("fs_div") != fs_div:
            continue
        nm = item.get("account_nm", "")
        if (exact and nm == keyword) or (not exact and keyword in nm):
            return item
    return None


def to_int(val):
    if not val:
        return None
    cleaned = val.replace(",", "").strip()
    return int(cleaned) if cleaned and cleaned != "-" else None


def format_value(n):
    if n is None:
        return "-"
    negative = n < 0
    abs_n = abs(n)

    unit = SIPMAN if abs_n < EOK else CHUNMAN
    rounded = round(abs_n / unit) * unit
    if rounded == 0:
        return "0"

    if rounded >= JO:
        jo = rounded // JO
        eok_rem = (rounded % JO) // EOK
        formatted = f"{jo}조 {eok_rem}억" if eok_rem else f"{jo}조"
    elif rounded >= BAEK_EOK:
        formatted = f"{round(rounded / EOK)}억"
    elif rounded >= EOK:
        eok = rounded // EOK
        man = (rounded % EOK) // 10_000
        formatted = f"{eok}억 {man:,}만" if man else f"{eok}억"
    else:
        formatted = f"{rounded // 10_000:,}만"

    return f"({formatted})" if negative else formatted


def print_results(stock_name, stock_code, items):
    fs_div = detect_fs_div(items)
    fs_label = "연결" if fs_div == "CFS" else "별도"

    col_width = 16
    label_width = 12
    separator = "-" * (label_width + col_width)

    print(f"\n{'='*(label_width + col_width)}")
    print(f"  {stock_name} ({stock_code})  |  {BSNS_YEAR}년 연간 실적  |  {fs_label}")
    print(f"{'='*(label_width + col_width)}")

    for col, label, exact in ACCOUNTS:
        item = find_item(items, label, exact, fs_div)
        val = format_value(to_int(item.get("thstrm_amount")) if item else None)
        print(f"  {label:<{label_width}}{val:>{col_width}}")

    print(separator)


def main():
    stock_code = input("종목코드를 입력하세요: ").strip()
    if not stock_code:
        print("종목코드를 입력해주세요.")
        return

    try:
        corp_code = find_corp_code(stock_code)
        if not corp_code:
            print(f"종목코드 {stock_code}에 해당하는 corp_code를 찾을 수 없습니다.")
            return

        stock_name = fetch_stock_name(stock_code)
        print(f"조회 중... ({stock_name}, corp_code={corp_code})")

        items = fetch_annual_items(corp_code)
        print_results(stock_name, stock_code, items)

    except Exception as e:
        print(f"오류: {e}")


if __name__ == "__main__":
    main()
