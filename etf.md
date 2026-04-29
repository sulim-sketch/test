# etf.py

KRX(한국거래소) Open API를 통해 ETF 일별 매매 데이터를 수집하고 엑셀 파일로 저장하는 스크립트입니다.

## 실행 방법

```bash
python etf.py
```

출력 파일: `krx_etf_YYYYMMDD.xlsx`

---

## 로직 설명

### 1. 기준일자 계산 (한국시간 기준 전날)

KRX API는 조회할 날짜(`basDd`)를 쿼리 파라미터로 요청합니다.
서버가 어느 시간대에서 실행되더라도 항상 **한국시간(KST, UTC+9) 기준 어제**를 기준일자로 사용합니다.
주말·공휴일 등 영업일 여부는 고려하지 않으며, 단순히 오늘 날짜에서 1일을 뺀 값을 사용합니다.

```python
kst = timezone(timedelta(hours=9))
date = (datetime.now(kst) - timedelta(days=1)).strftime("%Y%m%d")
```

- `datetime.now(kst)` — 현재 시각을 KST로 변환
- `- timedelta(days=1)` — 하루 전날로 이동 (영업일 여부 무관)
- `.strftime("%Y%m%d")` — `20260423` 형태의 문자열로 포맷

> 전날을 사용하는 이유: KRX는 당일 장 종료 후 데이터를 집계하므로, 당일 날짜로 조회하면 데이터가 없거나 불완전할 수 있습니다.

> **공휴일·주말 동작**: 기준일자가 공휴일이나 주말이더라도 ETF 종목 목록(`ISU_CD`, `ISU_NM` 등)은 정상적으로 반환됩니다. 단, 거래가 없으므로 종가(`TDD_CLSPRC`), 거래량(`ACC_TRDVOL`) 등 시세 관련 필드는 값이 비어있거나 0으로 내려올 수 있습니다.

### 2. API 인증

API 키는 `.env` 파일에서 불러오며, HTTP 요청 헤더의 `AUTH_KEY` 필드에 담아 전송합니다.

```
# .env
KRX_API_KEY=your_api_key_here
```

```python
headers = {"AUTH_KEY": api_key}
response = requests.get(url, headers=headers)
```

### 3. 응답 파싱

응답 JSON의 최상위 키 `OutBlock_1`이 ETF 레코드 리스트입니다.
각 레코드의 모든 값은 **문자열(string)** 타입입니다.

```python
records = data["OutBlock_1"]  # list of dict
df = pd.DataFrame(records, columns=COLUMNS)
```

### 4. 출력 파일

파일명에 기준일자를 포함시켜 실행할 때마다 덮어쓰지 않고 날짜별로 누적 저장됩니다.

```
krx_etf_20260423.xlsx
krx_etf_20260424.xlsx
...
```

---

## API 응답 컬럼 설명

API endpoint: `GET https://data-dbg.krx.co.kr/svc/apis/etp/etf_bydd_trd?basDd={YYYYMMDD}`

응답 JSON 키: `OutBlock_1` (리스트, 각 원소는 아래 필드를 가진 문자열 값)

| 컬럼명 | 설명 |
|---|---|
| `BAS_DD` | 기준일자 (YYYYMMDD) |
| `ISU_CD` | 종목코드 |
| `ISU_NM` | 종목명 |
| `TDD_CLSPRC` | 종가 |
| `CMPPREVDD_PRC` | 전일 대비 가격 변동 |
| `FLUC_RT` | 등락률 (%) |
| `NAV` | 순자산가치 (NAV) |
| `TDD_OPNPRC` | 시가 |
| `TDD_HGPRC` | 고가 |
| `TDD_LWPRC` | 저가 |
| `ACC_TRDVOL` | 거래량 |
| `ACC_TRDVAL` | 거래대금 |
| `MKTCAP` | 시가총액 |
| `INVSTASST_NETASST_TOTAMT` | 순자산총액 |
| `LIST_SHRS` | 상장좌수 |
| `IDX_IND_NM` | 기초지수 지수명 |
| `OBJ_STKPRC_IDX` | 기초지수 종가 |
| `CMPPREVDD_IDX` | 기초지수 전일 대비 |
| `FLUC_RT_IDX` | 기초지수 등락률 (%) |
