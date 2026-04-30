import os
import requests
import openpyxl
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BSNS_YEAR      = "2024"
API_BATCH_SIZE = 10   # DART API 한 번에 조회할 기업 수
DB_BATCH_SIZE  = 100  # Supabase upsert 배치 크기

PERIOD_CODES = {
    "1Q":     "11013",
    "2Q":     "11012",
    "3Q":     "11014",
    "Annual": "11011",
}

QUARTER_INT    = {"1Q": 1, "2Q": 2, "3Q": 3, "4Q": 4}
QUARTER_SOURCE = {"1Q": "1Q", "2Q": "2Q", "3Q": "3Q", "4Q": "Annual"}

ACCOUNTS = [
    ("revenue",          "매출액",     True,  "IS"),
    ("operating_income", "영업이익",   False, "IS"),
    ("net_income",       "당기순이익", False, "IS"),
    ("asset",            "자산총계",   True,  "BS"),
    ("liability",        "부채총계",   True,  "BS"),
    ("equity",           "자본총계",   True,  "BS"),
]

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")


# ── Supabase 헬퍼 ─────────────────────────────────────────────

def supabase_headers(prefer_upsert=False):
    key = os.environ["SUPABASE_KEY"]
    h = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if prefer_upsert:
        h["Prefer"] = "resolution=merge-duplicates"
    return h


# ── Supabase 데이터 로딩 ──────────────────────────────────────

def load_all_stock_codes():
    """listed_stocks 전체에서 ISU_SRT_CD 목록 반환 (페이지네이션)."""
    all_codes = []
    page_size = 1000
    offset = 0

    while True:
        resp = requests.get(
            f"{SUPABASE_URL}/listed_stocks",
            headers=supabase_headers(),
            params={"select": "ISU_SRT_CD,ISU_NM", "limit": page_size, "offset": offset},
        )
        resp.raise_for_status()
        data = resp.json()
        all_codes.extend(
            row["ISU_SRT_CD"] for row in data if "우선주" not in row.get("ISU_NM", "")
        )
        if len(data) < page_size:
            break
        offset += page_size

    return all_codes


def find_corp_code(stock_code):
    """corp_codes 테이블에서 stock_code 매칭 corp_code 반환."""
    resp = requests.get(
        f"{SUPABASE_URL}/corp_codes",
        headers=supabase_headers(),
        params={"select": "corp_code", "stock_code": f"eq.{stock_code}"},
    )
    resp.raise_for_status()
    data = resp.json()
    return data[0]["corp_code"] if data else None


# ── DART API ─────────────────────────────────────────────────

def fetch_multi_period_items(api_key, corp_codes, bsns_year):
    """여러 기업의 분기별 fnlttMultiAcnt 호출 (총 4회).
    반환: {corp_code: {period: [items]}}, {corp_code: {period: rcept_no}}
    """
    url = "https://opendart.fss.or.kr/api/fnlttMultiAcnt.json"
    corp_codes_str = ",".join(corp_codes)

    period_items = {cc: {p: [] for p in PERIOD_CODES} for cc in corp_codes}
    rcept_nos    = {cc: {} for cc in corp_codes}

    for period, code in PERIOD_CODES.items():
        resp = requests.get(url, params={
            "crtfc_key": api_key,
            "corp_code": corp_codes_str,
            "bsns_year": bsns_year,
            "reprt_code": code,
        })
        resp.encoding = "utf-8"
        data = resp.json()

        if data.get("status") == "000":
            for item in data.get("list", []):
                cc = item.get("corp_code")
                if cc not in period_items:
                    continue
                period_items[cc][period].append(item)
                if period not in rcept_nos[cc]:
                    rcept_nos[cc][period] = item.get("rcept_no")

    return period_items, rcept_nos


# ── 파싱 헬퍼 ────────────────────────────────────────────────

def detect_fs_div(period_items):
    for items in period_items.values():
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


# ── 분기별 계산 ──────────────────────────────────────────────

def build_quarterly(period_items):
    fs_div = detect_fs_div(period_items)
    account_values = {}

    for col, keyword, exact, acc_type in ACCOUNTS:
        quarterly = {}

        for q in ("1Q", "2Q", "3Q"):
            item = find_item(period_items.get(q, []), keyword, exact, fs_div)
            if item:
                quarterly[q] = to_int(item.get("thstrm_amount"))

        annual_item = find_item(period_items.get("Annual", []), keyword, exact, fs_div)
        if annual_item:
            if acc_type == "IS":
                q3_item = find_item(period_items.get("3Q", []), keyword, exact, fs_div)
                if q3_item:
                    q3_cumul = to_int(
                        q3_item.get("thstrm_add_amount") or q3_item.get("thstrm_amount")
                    )
                    annual_total = to_int(annual_item.get("thstrm_amount"))
                    if annual_total is not None and q3_cumul is not None:
                        quarterly["4Q"] = annual_total - q3_cumul
            else:
                quarterly["4Q"] = to_int(annual_item.get("thstrm_amount"))

        account_values[col] = quarterly

    return account_values, fs_div


def build_db_rows(corp_code, stock_code, bsns_year, period_items, rcept_nos):
    account_values, fs_div = build_quarterly(period_items)
    is_consolidated = fs_div == "CFS"

    rows = []
    for q_label, q_int in QUARTER_INT.items():
        row = {
            "corp_code":       corp_code,
            "stock_code":      stock_code,
            "is_consolidated": is_consolidated,
            "rcept_no":        rcept_nos.get(QUARTER_SOURCE[q_label]),
            "bsns_year":       bsns_year,
            "quarter":         q_int,
        }
        for col, _, _, _ in ACCOUNTS:
            val = account_values.get(col, {}).get(q_label)
            row[col] = str(val) if val is not None else ""
        rows.append(row)

    return rows


# ── Supabase 적재 ─────────────────────────────────────────────

def upsert_to_supabase(rows):
    """rows를 DB_BATCH_SIZE씩 나눠 upsert."""
    headers = supabase_headers(prefer_upsert=True)
    errors = []

    for i in range(0, len(rows), DB_BATCH_SIZE):
        batch = rows[i:i + DB_BATCH_SIZE]
        resp = requests.post(
            f"{SUPABASE_URL}/quarterly_results",
            headers=headers,
            json=batch,
        )
        if resp.status_code not in (200, 201):
            errors.append(f"{resp.status_code} {resp.text[:200]}")

    return errors


# ── 실패 엑셀 저장 ────────────────────────────────────────────

def save_failures_to_excel(failures, bsns_year):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "failures"
    ws.append(["stock_code", "corp_code", "reason"])
    for f in failures:
        ws.append([f["stock_code"], f.get("corp_code", ""), f["reason"]])

    filename = f"quarterly_failures_{bsns_year}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    wb.save(filename)
    return filename


# ── 메인 ─────────────────────────────────────────────────────

def main():
    dart_api_key = os.environ.get("DART_API_KEY")
    failures = []

    print("1. listed_stocks 전체 종목 조회 중...")
    all_stock_codes = load_all_stock_codes()
    total_stocks = len(all_stock_codes)
    total_batches = (total_stocks + API_BATCH_SIZE - 1) // API_BATCH_SIZE
    print(f"   총 {total_stocks}개 종목 → {total_batches}개 API 배치 (배치당 {API_BATCH_SIZE}개)\n")

    total_inserted = 0
    pending_rows = []

    for batch_num, i in enumerate(range(0, total_stocks, API_BATCH_SIZE), start=1):
        stock_batch = all_stock_codes[i:i + API_BATCH_SIZE]
        print(f"[API 배치 {batch_num}/{total_batches}] {stock_batch[0]} ~ {stock_batch[-1]}")

        # 1. corp_code 조회
        corp_map = {}  # stock_code -> corp_code
        for stock_code in stock_batch:
            try:
                corp_code = find_corp_code(stock_code)
            except Exception as e:
                failures.append({"stock_code": stock_code, "reason": f"corp_code 조회 오류: {e}"})
                continue
            if not corp_code:
                failures.append({"stock_code": stock_code, "reason": "corp_codes 매칭 없음"})
                continue
            corp_map[stock_code] = corp_code

        if not corp_map:
            continue

        # 2. DART 멀티 조회 (4회 호출로 배치 내 전 기업 처리)
        try:
            all_period_items, all_rcept_nos = fetch_multi_period_items(
                dart_api_key, list(corp_map.values()), BSNS_YEAR
            )
        except Exception as e:
            for stock_code, corp_code in corp_map.items():
                failures.append({"stock_code": stock_code, "corp_code": corp_code, "reason": f"DART API 오류: {e}"})
            continue

        # 3. 기업별 행 생성
        for stock_code, corp_code in corp_map.items():
            try:
                rows = build_db_rows(
                    corp_code, stock_code, BSNS_YEAR,
                    all_period_items[corp_code],
                    all_rcept_nos[corp_code],
                )
                pending_rows.extend(rows)
            except Exception as e:
                failures.append({"stock_code": stock_code, "corp_code": corp_code, "reason": f"데이터 파싱 오류: {e}"})

        # 4. DB_BATCH_SIZE 이상 쌓이면 upsert
        if len(pending_rows) >= DB_BATCH_SIZE:
            errors = upsert_to_supabase(pending_rows)
            if errors:
                for err in errors:
                    print(f"  [Supabase 오류] {err}")
            else:
                total_inserted += len(pending_rows)
                print(f"  → {len(pending_rows)}행 적재 완료 (누적 {total_inserted}행)")
            pending_rows = []

    # 5. 남은 행 flush
    if pending_rows:
        errors = upsert_to_supabase(pending_rows)
        if errors:
            for err in errors:
                print(f"  [Supabase 오류] {err}")
        else:
            total_inserted += len(pending_rows)
            print(f"  → {len(pending_rows)}행 적재 완료 (누적 {total_inserted}행)")

    print(f"\n완료: 총 {total_inserted}행 적재 / 실패 {len(failures)}건")

    if failures:
        filename = save_failures_to_excel(failures, BSNS_YEAR)
        print(f"실패 내역 저장: {filename}")
        for f in failures:
            print(f"  [실패] {f['stock_code']} ({f.get('corp_code', '-')}): {f['reason']}")


if __name__ == "__main__":
    main()
