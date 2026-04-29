# KRX & DART 데이터 통합 프로젝트

이 프로젝트는 한국거래소(KRX)의 상장 종목 정보와 금융감독원(DART)의 기업 고유번호 데이터를 수집하여 Supabase 데이터베이스에 적재하고, 두 데이터 간의 정합성을 검증하는 도구들을 포함하고 있습니다.

## 주요 스크립트 설명

### 1. `corp_codes.py`
- **목적**: DART Open API를 통해 대한민국 전체 기업의 고유번호 목록을 가져와 Supabase에 적재합니다.
- **주요 기능**:
    - DART API에서 XML 데이터를 다운로드 및 파싱
    - `stock_code`(종목코드) 및 `corp_eng_name`(영문명)이 빈 값인 경우 `null`로 처리하여 데이터 품질 유지
    - Supabase `corp_codes` 테이블에 100건씩 배치로 UPSERT(중복 시 업데이트) 수행

### 2. `listed_stocks.py`
- **목적**: KRX OpenAPI를 통해 KOSPI, KOSDAQ, KONEX 시장의 상장 종목 기본 정보를 수집합니다.
- **주요 기능**:
    - 시장별 엔드포인트(`stk_isu_base_info`, `ksq_isu_base_info`, `knx_isu_base_info`) 호출
    - 각 레코드에 `is_active` (True), `market` (KOSPI/KOSDAQ/KONEX) 컬럼 추가
    - 통합된 데이터를 Supabase `listed_stocks` 테이블에 적재
    - 실행 시 `listed_stocks_combined_{date}.xlsx` 형태의 로컬 백업 파일 생성

### 3. `validate_stock_code_integrity.py`
- **목적**: `listed_stocks` 테이블의 종목 코드가 `corp_codes` 테이블에 모두 존재하는지 확인하여 데이터 정합성을 검증합니다.
- **검증 로직**:
    - **법인 vs 종목 차이 반영**: DART의 기업 코드는 '법인' 기준이므로, 하나의 법인이 발행한 여러 종목(예: 우선주)은 `corp_codes`에 종목코드가 등록되어 있지 않은 경우가 많습니다.
    - **필터링**: 종목명(`ISU_NM`)에 **"우선주"**가 포함된 행은 검증 대상에서 제외합니다.
    - **출력**: 일치하지 않는 종목이 있을 경우, 해당 종목의 코드와 이름을 콘솔에 리스트업합니다.

### 4. `validate_corp_code_uniqueness.py`
- **목적**: `corp_codes` 테이블 내의 `corp_code`(기업고유번호)가 중복 없이 유일(Unique)하게 저장되어 있는지 검증합니다.
- **검증 로직**:
    - Supabase에서 모든 `corp_code`를 수집하여 전체 개수와 고유 개수(Set)를 비교합니다.
    - 중복이 발견될 경우, 중복된 코드의 개수와 예시 목록을 출력합니다.

## 데이터베이스 구조 (Supabase)

- **`corp_codes`**: DART 기업 고유번호 정보
    - **중요**: `cron_corp_codes.py`의 UPSERT 로직이 정상 작동하려면 `corp_code` 컬럼에 Unique 제약 조건이 설정되어 있어야 합니다. (SQL Editor에서 아래 명령 실행 필요)
      ```sql
      ALTER TABLE corp_codes ADD CONSTRAINT corp_codes_corp_code_unique UNIQUE (corp_code);
      ```
- **`listed_stocks`**: KRX 상장 종목 상세 정보
    - **중요**: UPSERT 로직 활용을 위해 `ISU_SRT_CD` 컬럼에 Unique 제약 조건 설정이 권장됩니다.
      ```sql
      ALTER TABLE listed_stocks ADD CONSTRAINT listed_stocks_isu_srt_cd_unique UNIQUE ("ISU_SRT_CD");
      ```

### 5. `cron_corp_codes.py`
- **목적**: DART 기업 고유번호를 정기적으로 업데이트(UPSERT)하기 위한 크론 잡용 스크립트입니다.
- **주요 기능**:
    - `corp_code`를 기준으로 중복을 체크하여, 이미 존재할 경우 전체 값을 최신 데이터로 덮어씌우고 `updated_at` 시간을 갱신합니다.
    - 존재하지 않을 경우 새로운 행을 추가합니다.
    - 모든 로그와 출력문은 영어로 작성되었으며, 내부 주석은 한글로 작성되어 유지보수성을 높였습니다.

### 6. `cron_listed_stocks.py`
- **목적**: KRX 상장 종목 정보를 최신 영업일 기준으로 동기화하고, 상장폐지된 종목을 관리합니다.
- **주요 기능**:
    - **최근 영업일 자동 감지**: 한국 시간 기준 어제부터 최대 10일 전까지 역추적하여 데이터가 존재하는 가장 최근 영업일을 자동으로 찾아냅니다.
    - **UPSERT 연산**: `ISU_SRT_CD`(티커)를 기준으로 중복 시 업데이트를 수행합니다. 이를 통해 시장 변경, 사명 변경, 액면분할 등으로 인한 데이터 변동을 반영합니다.
    - **상장폐지 관리**: DB 내 활성 종목(`is_active=True`) 중 API 결과에 포함되지 않은 종목을 상장폐지된 것으로 간주하여 `is_active=False`로 업데이트합니다.
    - **`updated_at` 갱신**: 모든 작업 시 해당 시점의 타임스탬프를 기록합니다.

## 실행 방법

1. **환경 변수 설정**: `.env` 파일에 다음 키들이 설정되어 있어야 합니다.
    - `DART_API_KEY`
    - `KRX_API_KEY`
    - `SUPABASE_URL`
    - `SUPABASE_KEY`

2. **의존성 설치**:
    ```bash
    pip install requests pandas openpyxl python-dotenv
    ```

3. **스크립트 실행**:
    ```bash
    python corp_codes.py
    python listed_stocks.py
    python validate_stock_code_integrity.py
    ```
