# dart_corpcode.py

DART(전자공시시스템) Open API를 통해 공시대상 기업의 고유번호 전체 목록을 수집하고 엑셀 파일로 저장하는 스크립트입니다.

## 실행 방법

```bash
python dart_corpcode.py
```

출력 파일: `dart_corpcode_{YYYYMMDD}.xlsx` (한국시간 기준 오늘 날짜)

> 동일한 파일이 이미 존재하면 삭제 후 덮어씁니다. 파일이 Excel에서 열려 있는 상태라면 PermissionError가 발생하므로 먼저 닫아야 합니다.

---

## 로직 설명

### 1. API 요청 → ZIP 수신

DART API는 인증키(`crtfc_key`)를 쿼리 파라미터로 받아 ZIP 파일을 반환합니다.
API 키는 `.env` 파일의 `DART_API_KEY`에서 불러옵니다.

```
GET https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={DART_API_KEY}
```

응답은 바이너리(ZIP) 형식이므로 `response.content`로 수신합니다.

### 2. ZIP 압축 해제 → XML 추출

ZIP 안에는 `CORPCODE.xml` 파일 하나만 포함되어 있습니다.
`zipfile.ZipFile`로 메모리에서 직접 압축을 해제합니다 (디스크 저장 없음).

### 3. XML 파싱

XML 구조:
```xml
<result>
  <list>
    <corp_code>00434003</corp_code>
    <corp_name>정식명칭</corp_name>
    <corp_eng_name>English Name</corp_eng_name>
    <stock_code>000000</stock_code>
    <modify_date>20170630</modify_date>
  </list>
  ...
</result>
```

- root 태그는 `<result>`이며, 바로 아래에 `<list>` 요소들이 나열됩니다.
- 모든 필드는 문자열(string) 타입입니다.

### 4. 엑셀 저장

`openpyxl`로 직접 엑셀을 구성합니다.

- 헤더 행: 진한 파란색 배경, 흰색 굵은 글씨
- 첫 행 고정 (`freeze_panes`)
- 종목명·영문명 컬럼은 왼쪽 정렬, 나머지는 가운데 정렬

---

## 출력 컬럼 설명

| 컬럼명 (한국어) | 원본 필드명 | 설명 |
|---|---|---|
| 고유번호 | `corp_code` | 공시대상 기업 고유번호 (8자리) |
| 정식명칭 | `corp_name` | 기업 정식 한국어 명칭 |
| 영문 정식명칭 | `corp_eng_name` | 기업 정식 영문 명칭 |
| 종목코드 | `stock_code` | 상장사의 주식 종목코드 (6자리, 비상장사는 공백) |
| 최종변경일자 | `modify_date` | 기업 정보 최종 변경일 (YYYYMMDD) |
