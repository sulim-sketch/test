import os
import requests
import openpyxl
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BSNS_YEARS     = ["2023", "2024"]
API_BATCH_SIZE = 10   # DART API 한 번에 조회할 기업 수
DB_BATCH_SIZE  = 100  # Supabase upsert 배치 크기

ANNUAL_REPRT_CODE = "11011"

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

def fetch_multi_annual_items(api_key, corp_codes, bsns_year):
    """여러 기업의 연간 fnlttMultiAcnt 호출 (1회).
    반환: {corp_code: [items]}, {corp_code: rcept_no}
    """
    url = "https://opendart.fss.or.kr/api/fnlttMultiAcnt.json"
    resp = requests.get(url, params={
        "crtfc_key":  api_key,
        "corp_code":  ",".join(corp_codes),
        "bsns_year":  bsns_year,
        "reprt_code": ANNUAL_REPRT_CODE,
    })
    resp.encoding = "utf-8"
    data = resp.json()

    items_map   = {cc: [] for cc in corp_codes}
    rcept_map   = {}

    if data.get("status") == "000":
        for item in data.get("list", []):
            cc = item.get("corp_code")
            if cc not in items_map:
                continue
            items_map[cc].append(item)
            if cc not in rcept_map:
                rcept_map[cc] = item.get("rcept_no")

    return items_map, rcept_map


# ── 파싱 헬퍼 ────────────────────────────────────────────────

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


# ── 행 생성 ──────────────────────────────────────────────────

def build_annual_row(corp_code, stock_code, bsns_year, items, rcept_no):
    fs_div = detect_fs_div(items)
    row = {
        "corp_code":       corp_code,
        "stock_code":      stock_code,
        "is_consolidated": fs_div == "CFS",
        "rcept_no":        rcept_no,
        "bsns_year":       bsns_year,
        "quarter":         0,
    }
    for col, keyword, exact, _ in ACCOUNTS:
        item = find_item(items, keyword, exact, fs_div)
        val = to_int(item.get("thstrm_amount")) if item else None
        row[col] = str(val) if val is not None else ""
    return row


# ── Supabase 적재 ─────────────────────────────────────────────

def upsert_to_supabase(rows):
    """rows를 DB_BATCH_SIZE씩 나눠 upsert."""
    headers = supabase_headers(prefer_upsert=True)
    errors = []

    for i in range(0, len(rows), DB_BATCH_SIZE):
        batch = rows[i:i + DB_BATCH_SIZE]
        resp = requests.post(
            f"{SUPABASE_URL}/annual_results",
            headers=headers,
            json=batch,
        )
        if resp.status_code not in (200, 201):
            errors.append(f"{resp.status_code} {resp.text[:200]}")

    return errors


# ── 실패 엑셀 저장 ────────────────────────────────────────────

def save_failures_to_excel(failures):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "failures"
    ws.append(["bsns_year", "stock_code", "corp_code", "reason"])
    for f in failures:
        ws.append([f.get("bsns_year", ""), f["stock_code"], f.get("corp_code", ""), f["reason"]])

    filename = f"annual_failures_2022_2024_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    wb.save(filename)
    return filename


# ── 연도별 처리 ───────────────────────────────────────────────

def process_year(dart_api_key, all_stock_codes, bsns_year, failures):
    total_stocks = len(all_stock_codes)
    total_batches = (total_stocks + API_BATCH_SIZE - 1) // API_BATCH_SIZE
    print(f"\n{'='*60}")
    print(f"  {bsns_year}년 처리 시작 — 총 {total_stocks}개 종목, {total_batches}개 배치")
    print(f"{'='*60}")

    total_inserted = 0
    pending_rows = []

    for batch_num, i in enumerate(range(0, total_stocks, API_BATCH_SIZE), start=1):
        stock_batch = all_stock_codes[i:i + API_BATCH_SIZE]
        print(f"[{bsns_year} | 배치 {batch_num}/{total_batches}] {stock_batch[0]} ~ {stock_batch[-1]}")

        # 1. corp_code 조회
        corp_map = {}
        for stock_code in stock_batch:
            try:
                corp_code = find_corp_code(stock_code)
            except Exception as e:
                failures.append({"bsns_year": bsns_year, "stock_code": stock_code, "reason": f"corp_code 조회 오류: {e}"})
                continue
            if not corp_code:
                failures.append({"bsns_year": bsns_year, "stock_code": stock_code, "reason": "corp_codes 매칭 없음"})
                continue
            corp_map[stock_code] = corp_code

        if not corp_map:
            continue

        # 2. DART 연간 멀티 조회
        try:
            items_map, rcept_map = fetch_multi_annual_items(
                dart_api_key, list(corp_map.values()), bsns_year
            )
        except Exception as e:
            for stock_code, corp_code in corp_map.items():
                failures.append({"bsns_year": bsns_year, "stock_code": stock_code, "corp_code": corp_code, "reason": f"DART API 오류: {e}"})
            continue

        # 3. 기업별 행 생성
        for stock_code, corp_code in corp_map.items():
            try:
                items = items_map[corp_code]
                if not items:
                    failures.append({"bsns_year": bsns_year, "stock_code": stock_code, "corp_code": corp_code, "reason": "연간 데이터 없음"})
                    continue
                row = build_annual_row(corp_code, stock_code, bsns_year, items, rcept_map.get(corp_code))
                pending_rows.append(row)
            except Exception as e:
                failures.append({"bsns_year": bsns_year, "stock_code": stock_code, "corp_code": corp_code, "reason": f"데이터 파싱 오류: {e}"})

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

    print(f"\n{bsns_year}년 완료: {total_inserted}행 적재")
    return total_inserted


# ── 메인 ─────────────────────────────────────────────────────

def main():
    dart_api_key = os.environ.get("DART_API_KEY")
    failures = []

    print("1. listed_stocks 전체 종목 조회 중...")
    all_stock_codes = load_all_stock_codes()
    print(f"   총 {len(all_stock_codes)}개 종목 로드 완료")

    grand_total = 0
    for bsns_year in BSNS_YEARS:
        grand_total += process_year(dart_api_key, all_stock_codes, bsns_year, failures)

    print(f"\n{'='*60}")
    print(f"전체 완료: 총 {grand_total}행 적재 / 실패 {len(failures)}건")
    print(f"{'='*60}")

    if failures:
        filename = save_failures_to_excel(failures)
        print(f"실패 내역 저장: {filename}")
        for f in failures:
            print(f"  [실패] {f.get('bsns_year','-')} {f['stock_code']} ({f.get('corp_code', '-')}): {f['reason']}")


if __name__ == "__main__":
    main()
