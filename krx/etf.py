import os
from datetime import datetime, timedelta, timezone

import requests
import pandas as pd
from dotenv import load_dotenv

# API 응답의 OutBlock_1 각 레코드에서 추출할 컬럼 순서 정의
# 모든 값은 문자열(string) 타입으로 내려옵니다
COLUMNS = [
    "BAS_DD",                   # 기준일자
    "ISU_CD",                   # 종목코드
    "ISU_NM",                   # 종목명
    "TDD_CLSPRC",               # 종가
    "CMPPREVDD_PRC",            # 전일 대비 가격 변동
    "FLUC_RT",                  # 등락률 (%)
    "NAV",                      # 순자산가치 (NAV)
    "TDD_OPNPRC",               # 시가
    "TDD_HGPRC",                # 고가
    "TDD_LWPRC",                # 저가
    "ACC_TRDVOL",               # 거래량
    "ACC_TRDVAL",               # 거래대금
    "MKTCAP",                   # 시가총액
    "INVSTASST_NETASST_TOTAMT", # 순자산총액
    "LIST_SHRS",                # 상장좌수
    "IDX_IND_NM",               # 기초지수 지수명
    "OBJ_STKPRC_IDX",           # 기초지수 종가
    "CMPPREVDD_IDX",            # 기초지수 전일 대비
    "FLUC_RT_IDX",              # 기초지수 등락률 (%)
]


def get_yesterday_kst() -> str:
    """
    서버 시간대와 무관하게 항상 한국시간(KST, UTC+9) 기준 전날을 반환합니다.
    KRX는 당일 장 종료 후 데이터를 집계하므로 당일 조회 시 데이터가 없을 수 있어
    전날을 기준일자로 사용합니다.
    """
    kst = timezone(timedelta(hours=9))  # KST = UTC+9
    yesterday = datetime.now(kst) - timedelta(days=1)
    return yesterday.strftime("%Y%m%d")  # 예: "20260423"


def crawl_etf_to_excel():
    # .env 파일에서 환경 변수 로드 (KRX_API_KEY)
    load_dotenv()
    api_key = os.environ["KRX_API_KEY"]

    # 기준일자: 한국시간 어제
    date = get_yesterday_kst()

    # KRX ETF 일별 매매 API 엔드포인트
    # basDd: 조회 기준일자 (YYYYMMDD)
    url = f"https://data-dbg.krx.co.kr/svc/apis/etp/etf_bydd_trd?basDd={date}"

    # KRX API는 쿼리 파라미터가 아닌 헤더의 AUTH_KEY로 인증합니다
    headers = {"AUTH_KEY": api_key}

    print(f"1. KRX API 요청 중... (기준일자: {date})")
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    # 응답 JSON 최상위 키 OutBlock_1에 ETF 레코드 리스트가 담겨 있습니다
    data = response.json()
    records = data["OutBlock_1"]
    print(f"   {len(records):,}개 ETF 데이터 수신")

    # 레코드 리스트를 DataFrame으로 변환, 컬럼 순서를 COLUMNS에 맞춥니다
    df = pd.DataFrame(records, columns=COLUMNS)

    # 파일명에 기준일자를 포함해 날짜별로 누적 저장합니다
    output_file = f"etf_{date}.xlsx"
    df.to_excel(output_file, index=False)
    print(f"2. 완료! '{output_file}' 저장됨 ({len(df):,}개 행)")


if __name__ == "__main__":
    crawl_etf_to_excel()
