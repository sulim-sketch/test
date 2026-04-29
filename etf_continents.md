# etf_continents.py

funetf.co.kr에서 ETF 구성 종목(포트폴리오) 테이블을 Selenium으로 크롤링하고 엑셀로 저장하는 스크립트입니다.

## 실행 방법

```bash
python etf_continents.py
```

출력 파일: `etf_portfolio_{ticker}.xlsx`

> 현재는 테스트 목적으로 `get_etf_tickers()`가 반환하는 리스트의 **첫 번째 ticker**만 처리합니다.

---

## 사전 요구사항

- `krx_etf_{YYYYMMDD}.xlsx` 파일이 존재해야 합니다 (`etf.py` 실행 결과물).
- Chrome 브라우저 및 ChromeDriver가 설치되어 있어야 합니다.

---

## 로직 설명

### 1. ticker 목록 가져오기 (`get_etf_tickers`)

`etf.py`가 생성한 `krx_etf_{date}.xlsx`의 `ISU_CD` 컬럼에서 종목코드 목록을 읽어옵니다.
`date`는 한국시간(KST) 기준 어제 날짜(YYYYMMDD)를 사용합니다.

```python
tickers = get_etf_tickers()
ticker = tickers[0]  # 현재는 첫 번째만 사용
```

---

### 2. 검색 페이지 → 상세 페이지 이동

`https://funetf.co.kr/search?schVal={ticker}`에 접근한 뒤,
`<div class="prd-name">` 안의 `<a>` 태그 href를 추출해 상세 페이지로 이동합니다.

```
https://funetf.co.kr/search?schVal=451060
    → div.prd-name > a[href]
    → https://www.funetf.co.kr/product/etf/view/KR7451060008
```

---

### 3. treemap 섹션 스크롤 → 동적 데이터 로드

상세 페이지의 `<section class="treemap">`은 화면에 진입해야 JS가 테이블 데이터를 채워주는 구조입니다.
Selenium으로 해당 섹션으로 스크롤한 뒤 4초 대기합니다.

```python
driver.execute_script("arguments[0].scrollIntoView(true);", section)
time.sleep(4)
```

---

### 4. 날짜 피커 처리

페이지에는 `<input class="input-picker">` 요소가 여러 개 존재합니다.
treemap 섹션과 연결된 피커는 **섹션 Y좌표 바로 위에 위치한 피커**입니다(`find_picker_for_section`).

#### 사이트의 기준일 결정 방식

funetf 상세 페이지는 다음 기준으로 구성 종목 및 비중을 표시합니다.

| 상황 | 표시 기준 |
|---|---|
| 오늘 장이 아직 끝나지 않은 경우 | 어제 장 마감 기준 |
| 오늘 장이 끝난 경우 | 오늘 장 마감 기준 |

즉, 사이트 피커의 기본값은 "가장 최근에 마감된 장"의 날짜를 반영합니다.

#### 공휴일 처리가 필요한 이유

funetf는 **비영업일(공휴일·주말)을 기준일로 조회하면 구성 종목 데이터를 반환하지 않습니다.**
사이트 피커 기본값이 공휴일을 가리킬 수 있으므로, 크롤링 전 반드시 영업일 여부를 확인해야 합니다.

#### 날짜 처리 방식

1. 사이트가 피커에 기본으로 세팅한 날짜를 읽습니다 (`YY.MM.DD` 형식).
2. `holidayskr.is_holiday`로 해당 날짜가 공휴일인지 확인합니다.
3. 공휴일이면 하루씩 날짜를 줄여가며 공휴일이 아닌 날짜를 찾아 피커에 재설정합니다.
4. 공휴일이 아니면 피커를 변경하지 않고 바로 크롤링을 진행합니다.

> `holidayskr.is_holiday`는 토요일·일요일에 대해 `False`를 반환합니다. 주말 처리는 사이트 기본 피커값에 의존합니다.

피커 값 변경은 JavaScript로 직접 주입하며, `change` / `input` 이벤트를 함께 발생시켜 테이블이 갱신되도록 합니다.

```javascript
arguments[0].value = "26.04.25";  // YY.MM.DD 형식
arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
arguments[0].dispatchEvent(new Event('input',  { bubbles: true }));
```

---

### 5. 테이블 수집

treemap 섹션 안에는 `<table>`이 두 개 있습니다.

| 테이블 | 역할 |
|---|---|
| `<thead>` 포함 테이블 | 컬럼 헤더 |
| `<tbody>` 포함 테이블 | 실제 데이터 행 |

두 테이블을 각각 찾아 컬럼명과 데이터를 조합해 DataFrame을 구성합니다.
완전히 빈 행(`td` 텍스트가 모두 비어있는 경우)은 제외합니다.

---

## 출력 컬럼

| 컬럼명 | 설명 |
|---|---|
| `종목명` | 구성 종목명 및 종목코드 |
| `비율(%)` | 포트폴리오 내 비중 |
| `수량` | 보유 수량 |
| `평가금액(원)` | 평가금액 |
| `기준가(원)` | 기준가격 |
| `전일대비(원)` | 전일 대비 가격 변동 |
| `1일 수익률(%)` | 1일 수익률 |
