import os
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
from dotenv import load_dotenv
from holidayskr import is_holiday
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

load_dotenv()


def get_yesterday_kst() -> str:
    """한국시간(KST, UTC+9) 기준 전날을 YYYYMMDD 형식으로 반환합니다."""
    kst = timezone(timedelta(hours=9))
    return (datetime.now(kst) - timedelta(days=1)).strftime("%Y%m%d")


def get_etf_tickers() -> list[str]:
    """
    etf.py가 생성한 krx_etf_{date}.xlsx 파일에서 ETF 종목코드(ISU_CD) 목록을 반환합니다.
    date는 한국시간 기준 어제 날짜(YYYYMMDD)를 사용합니다.
    """
    date = get_yesterday_kst()
    filepath = f"etf_{date}.xlsx"
    df = pd.read_excel(filepath, sheet_name="Sheet1", usecols=["ISU_CD"], dtype=str)
    return df["ISU_CD"].dropna().tolist()


def make_driver() -> webdriver.Chrome:
    """headless Chrome 드라이버를 생성합니다."""
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=opts)


def find_picker_for_section(driver: webdriver.Chrome, section) -> webdriver.remote.webelement.WebElement | None:
    """
    페이지 내 모든 input.input-picker 중, section의 Y좌표보다 위에 있는 것 중
    가장 가까운(Y 거리가 최소인) 피커를 반환합니다.
    funetf 상세 페이지에는 피커가 여러 개 존재하므로 위치 기반으로 구분합니다.
    """
    section_y = section.location["y"]
    pickers = driver.find_elements(By.CSS_SELECTOR, "input.input-picker")

    # section보다 위에 있는 피커만 추려서 거리(section_y - picker_y)가 가장 작은 것 선택
    candidates = [
        (p, section_y - p.location["y"])
        for p in pickers
        if p.location["y"] < section_y
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda x: x[1])[0]


def parse_picker_date(picker) -> datetime:
    """
    피커의 현재 value(YY.MM.DD 형식)를 datetime으로 파싱합니다.
    예: "26.04.24" → datetime(2026, 4, 24)
    """
    raw = picker.get_attribute("value")  # 예: "26.04.24"
    return datetime.strptime(raw, "%y.%m.%d")


def find_non_holiday(dt: datetime) -> datetime:
    """
    주어진 날짜가 공휴일이면 하루씩 줄여가며 공휴일이 아닌 날짜를 반환합니다.
    holidayskr.is_holiday는 'YYYY-MM-DD' 문자열을 인자로 받습니다.
    주말(토/일)은 is_holiday가 False를 반환하므로 공휴일 판단에만 사용됩니다.
    """
    while is_holiday(dt.strftime("%Y-%m-%d")):
        dt -= timedelta(days=1)
    return dt


def set_date_picker(driver: webdriver.Chrome, picker, dt: datetime):
    """
    input-picker 요소의 값을 YY.MM.DD 형식으로 직접 주입하고
    change/input 이벤트를 발생시켜 테이블이 갱신되도록 합니다.

    funetf의 날짜 피커는 일반 input이므로 JavaScript로 값을 설정한 뒤
    이벤트를 강제로 발생시켜야 페이지가 반응합니다.
    """
    date_str = dt.strftime("%y.%m.%d")  # funetf 날짜 형식: YY.MM.DD (예: 26.04.25)
    driver.execute_script(
        """
        arguments[0].value = arguments[1];
        arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
        arguments[0].dispatchEvent(new Event('input',  { bubbles: true }));
        """,
        picker,
        date_str,
    )


def crawl_treemap(ticker: str) -> pd.DataFrame:
    """
    funetf.co.kr에서 주어진 ticker의 구성 종목 테이블을 크롤링해 DataFrame으로 반환합니다.

    흐름:
      1. 검색 페이지(search?schVal={ticker}) → div.prd-name의 <a> href로 상세 페이지 이동
      2. section.treemap으로 스크롤 → JS 동적 데이터 로드 대기
      3. 피커의 기본 날짜 확인 → 공휴일이면 하루씩 줄여 비공휴일 날짜로 재설정
      4. thead 테이블에서 컬럼명 수집
      5. tbody 테이블에서 데이터 행 수집
    """
    driver = make_driver()
    try:
        # 1. 검색 페이지 → 상세 페이지 URL 추출
        search_url = f"https://funetf.co.kr/search?schVal={ticker}"
        print(f"  [1] 검색 페이지 접근: {search_url}")
        driver.get(search_url)
        wait = WebDriverWait(driver, 15)
        prd_div = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.prd-name")))
        detail_url = prd_div.find_element(By.TAG_NAME, "a").get_attribute("href")

        # 2. 상세 페이지 이동 → treemap 섹션 스크롤 → 동적 데이터 로드 대기
        # treemap 테이블은 화면에 진입해야 JS가 데이터를 채워주는 구조입니다.
        print(f"  [2] 상세 페이지 이동: {detail_url}")
        driver.get(detail_url)
        time.sleep(3)
        section = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "section.treemap")))
        driver.execute_script("arguments[0].scrollIntoView(true);", section)
        time.sleep(4)  # 스크롤 후 JS 렌더링 완료 대기

        # 3. 날짜 피커 처리
        # 사이트가 기본으로 채워둔 날짜를 읽은 뒤 공휴일 여부를 확인합니다.
        # 공휴일이면 하루씩 날짜를 줄여가며 공휴일이 아닌 날짜를 찾아 피커에 재설정합니다.
        # 공휴일이 아니면 피커를 건드리지 않고 바로 크롤링을 진행합니다.
        picker = find_picker_for_section(driver, section)
        if picker:
            default_date = parse_picker_date(picker)
            adjusted_date = find_non_holiday(default_date)

            if adjusted_date != default_date:
                print(f"  [3] 공휴일 감지({default_date.strftime('%y.%m.%d')}) → {adjusted_date.strftime('%y.%m.%d')}으로 재설정")
                set_date_picker(driver, picker, adjusted_date)
                time.sleep(3)  # 날짜 변경 후 테이블 갱신 대기
            else:
                print(f"  [3] 공휴일 아님 → 기본 날짜 그대로 사용 ({default_date.strftime('%y.%m.%d')})")
        else:
            print("  [3] 날짜 피커를 찾지 못했습니다. 기본값으로 진행합니다.")

        # 4. thead 테이블에서 컬럼명 수집
        # treemap 섹션 안에 table이 두 개 존재합니다:
        #   - thead만 있는 테이블: 컬럼 헤더
        #   - tbody만 있는 테이블: 실제 데이터
        tables = section.find_elements(By.TAG_NAME, "table")
        thead_table = next((t for t in tables if t.find_elements(By.TAG_NAME, "thead")), None)
        tbody_table = next((t for t in tables if t.find_elements(By.TAG_NAME, "tbody")), None)

        if not thead_table or not tbody_table:
            raise RuntimeError("treemap 내 thead/tbody 테이블을 찾지 못했습니다.")

        columns = [th.text.strip() for th in thead_table.find_elements(By.TAG_NAME, "th")]
        print(f"  [4] 컬럼: {columns}")

        # 5. tbody 데이터 수집 (빈 행 제외)
        rows = tbody_table.find_element(By.TAG_NAME, "tbody").find_elements(By.TAG_NAME, "tr")
        data = []
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            values = [c.text.strip() for c in cells]
            if any(values):  # 완전히 빈 행은 건너뜁니다
                data.append(values)

        print(f"  [5] 데이터 {len(data)}행 수집 완료")
        return pd.DataFrame(data, columns=columns if columns else None)

    finally:
        driver.quit()


def main():
    tickers = get_etf_tickers()
    print(f"총 {len(tickers)}개 ticker 크롤링 시작")

    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst).strftime("%Y%m%d")

    output_file = f"etf_continents_{today}.xlsx"

    # 이미 존재하는 파일은 삭제 후 덮어씁니다 (열려 있으면 PermissionError 발생)
    if os.path.exists(output_file):
        os.remove(output_file)

    # 모든 ticker의 구성종목을 하나의 엑셀 파일에 저장
    # 시트 이름은 ticker로 설정 (Excel 시트명 최대 31자 제한)
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        for i, ticker in enumerate(tickers, start=1):
            print(f"[{i}/{len(tickers)}] ticker: {ticker}")
            try:
                df = crawl_treemap(ticker)
                df.to_excel(writer, sheet_name=ticker, index=False)
                print(f"  → 시트 '{ticker}' 저장 완료 ({len(df)}행)")
            except Exception as e:
                print(f"  → 실패: {e}")

            # 과도한 요청으로 인한 차단 방지를 위해 1초 대기
            time.sleep(1)

    print(f"\n완료! '{output_file}'에 {len(tickers)}개 시트 저장")


if __name__ == "__main__":
    main()
