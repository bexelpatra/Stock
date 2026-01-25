# ClickHouse + Yahoo Finance 통합 진행 상황

**시작일**: 2026-01-23
**현재 단계**: Phase 6 - 자동 업데이트 (선택사항)

---

## 진행 상태 범례
- `[ ]` 미완료
- `[~]` 진행중
- `[x]` 완료
- `[!]` 오류/보류

---

## Phase 0: 준비 및 설정 확인

### 환경 확인
- [x] 0.1 - ClickHouse Docker 컨테이너 실행 확인
- [x] 0.2 - Python 가상환경 확인 (선택사항)
- [x] 0.3 - 현재 requirements.txt 백업

**실행 명령**:
```bash
# 0.1
docker ps | grep clickhouse
curl http://localhost:8123/ping

# 0.2 (선택)
python3 --version
which python3

# 0.3
cp requirements.txt requirements.txt.backup
```

**다음 단계로 진행 조건**: ClickHouse가 정상 실행 중

---

## Phase 1: 기초 작업 (의존성 및 디렉토리)

### 1.1 의존성 설치
- [x] 1.1.1 - requirements.txt에 새 패키지 추가
- [x] 1.1.2 - pip install 실행
- [x] 1.1.3 - 패키지 임포트 테스트

**수정 파일**: `requirements.txt`
**추가 내용**:
```
yfinance>=0.2.36
clickhouse-connect>=0.7.0
python-dateutil>=2.8.2
```

**실행 명령**:
```bash
pip install -r requirements.txt
python3 -c "import yfinance; import clickhouse_connect; print('OK')"
```

**예상 이슈**:
- 네트워크 연결 필요
- clickhouse-connect 설치 시간 소요 (약 1-2분)

### 1.2 디렉토리 구조 생성
- [x] 1.2.1 - `trading_system/ingestion/` 생성
- [x] 1.2.2 - `scripts/` 생성
- [x] 1.2.3 - `__init__.py` 생성

**실행 명령**:
```bash
mkdir -p trading_system/ingestion
mkdir -p scripts
touch trading_system/ingestion/__init__.py
```

**다음 단계로 진행 조건**: 모든 패키지 설치 완료, 디렉토리 생성 완료

---

## Phase 2: ClickHouse 스키마 구현

### 2.1 clickhouse_schema.py 작성
- [x] 2.1.1 - 파일 생성 및 기본 구조
- [x] 2.1.2 - get_client() 함수 구현
- [x] 2.1.3 - initialize_schema() 함수 구현 (테이블 생성 SQL)
- [x] 2.1.4 - 유틸리티 함수 구현 (verify_connection, get_tickers 등)
- [x] 2.1.5 - 테스트 완료

**파일**: `trading_system/ingestion/clickhouse_schema.py`

**핵심 기능**:
1. ClickHouse 연결 생성
2. stock_ohlcv 테이블 생성
3. ingestion_log 테이블 생성
4. 연결 검증

**테스트 명령**:
```bash
python3 -c "
from trading_system.ingestion.clickhouse_schema import get_client, initialize_schema
client = get_client('localhost', 9000, 'default')
initialize_schema(client)
print('Schema initialized successfully')
"
```

**예상 이슈**:
- ClickHouse 연결 포트 확인 (9000 vs 8123)
- 권한 문제 (default 유저)

**다음 단계로 진행 조건**: 테이블이 ClickHouse에 정상 생성됨

---

## Phase 3: Yahoo Finance 데이터 수집 구현

### 3.1 yahoo_finance.py 작성
- [x] 3.1.1 - fetch_ticker_data() 구현
- [x] 3.1.2 - validate_data() 구현
- [x] 3.1.3 - Rate limiting 로직 추가
- [x] 3.1.4 - 에러 핸들링 및 재시도 로직

**파일**: `trading_system/ingestion/yahoo_finance.py`

**테스트 명령**:
```bash
python3 -c "
from trading_system.ingestion.yahoo_finance import fetch_ticker_data
from datetime import date

df = fetch_ticker_data('005930.KS', date(2024, 1, 1), date(2024, 1, 31))
print(f'Fetched {len(df)} rows')
print(df.head())
"
```

**예상 이슈**:
- Yahoo Finance API 제한
- 잘못된 티커 형식
- 네트워크 타임아웃

### 3.2 ingest_data.py 스크립트 작성
- [x] 3.2.1 - CLI 인자 파싱 (argparse)
- [x] 3.2.2 - Yahoo Finance에서 데이터 수집
- [x] 3.2.3 - ClickHouse에 배치 삽입
- [x] 3.2.4 - ingestion_log 업데이트
- [x] 3.2.5 - 로깅 추가

**파일**: `scripts/ingest_data.py`

**테스트 명령**:
```bash
# 단일 티커 테스트
python scripts/ingest_data.py --tickers 005930.KS

# ClickHouse에서 확인
docker exec -it clickhouse-server clickhouse-client --query \
  "SELECT ticker, COUNT(*) FROM stock_ohlcv GROUP BY ticker"
```

**예상 이슈**:
- 대량 데이터 삽입 시 메모리 사용량
- 중복 데이터 처리

**다음 단계로 진행 조건**: 최소 1개 티커의 데이터가 ClickHouse에 정상 저장됨

---

## Phase 4: ClickHouseDataProvider 구현

### 4.1 clickhouse_provider.py 작성
- [x] 4.1.1 - ClickHouseDataProvider 클래스 뼈대
- [x] 4.1.2 - get_ohlcv() 메서드 구현
- [x] 4.1.3 - get_current_ohlcv() 메서드 구현
- [x] 4.1.4 - get_tickers() 메서드 구현
- [x] 4.1.5 - use_adjusted_close 옵션 처리

**파일**: `trading_system/data/clickhouse_provider.py`

**테스트 명령**:
```bash
python3 -c "
from trading_system.data.clickhouse_provider import ClickHouseDataProvider
from datetime import date

provider = ClickHouseDataProvider('localhost', 9000, 'default')
df = provider.get_ohlcv('005930.KS', date(2024, 1, 1), date(2024, 1, 31))
print(f'Retrieved {len(df)} rows')
print(df.columns.tolist())
"
```

**예상 이슈**:
- DataFrame 컬럼 순서
- 날짜 형식 변환

### 4.2 verify_data.py 작성
- [x] 4.2.1 - 티커별 통계 출력
- [x] 4.2.2 - 날짜 범위 검증
- [x] 4.2.3 - 중복 데이터 감지
- [x] 4.2.4 - 이상치 검사

**파일**: `scripts/verify_data.py`

**다음 단계로 진행 조건**: ClickHouseDataProvider가 정상적으로 데이터 반환

---

## Phase 5: 백테스트 통합

### 5.1 config.yaml 수정
- [x] 5.1.1 - database 섹션 추가
- [x] 5.1.2 - data_ingestion 섹션 추가
- [x] 5.1.3 - tickers를 Yahoo Finance 형식으로 변경 (.KS 추가)

**파일**: `config.yaml`

### 5.2 config.py 수정
- [x] 5.2.1 - DatabaseConfig 클래스 추가
- [x] 5.2.2 - DataIngestionConfig 클래스 추가
- [x] 5.2.3 - Config 클래스에 필드 추가
- [x] 5.2.4 - _from_dict() 메서드 업데이트

**파일**: `trading_system/utils/config.py`

### 5.3 run_backtest.py 수정
- [x] 5.3.1 - ClickHouseDataProvider 임포트
- [x] 5.3.2 - CLI에 --source 인자 추가
- [x] 5.3.3 - else 블록 (라인 128-130) 교체
- [x] 5.3.4 - 에러 메시지 개선

**파일**: `run_backtest.py`

**테스트 명령**:
```bash
# ClickHouse 데이터로 백테스트
python run_backtest.py --source clickhouse

# 샘플 데이터와 비교
python run_backtest.py --source sample
```

**예상 이슈**:
- 설정 파싱 오류
- 데이터가 없는 경우 처리

**다음 단계로 진행 조건**: 백테스트가 ClickHouse 데이터로 정상 실행됨

---

## Phase 6: 자동 업데이트

### 6.1 update_data.py 작성
- [ ] 6.1.1 - ingestion_log 조회
- [ ] 6.1.2 - 증분 데이터 수집 (last_date ~ today)
- [ ] 6.1.3 - 중복 방지 로직
- [ ] 6.1.4 - 로깅

**파일**: `scripts/update_data.py`

**테스트 명령**:
```bash
python scripts/update_data.py --config config.yaml
```

### 6.2 크론잡 설정
- [ ] 6.2.1 - 크론 명령 작성
- [ ] 6.2.2 - crontab 등록
- [ ] 6.2.3 - 로그 확인

**크론 설정**:
```bash
crontab -e
# 추가:
0 19 * * 1-5 /usr/bin/python3 /home/jai/class/Stock/scripts/update_data.py --config /home/jai/class/Stock/config.yaml >> /home/jai/class/Stock/logs/cron_update.log 2>&1
```

**다음 단계로 진행 조건**: update_data.py가 수동 실행 시 정상 동작

---

## Phase 7: 최종 검증

- [ ] 7.1 - 전체 백테스트 실행 (여러 티커)
- [ ] 7.2 - 데이터 품질 검증 (verify_data.py --all)
- [ ] 7.3 - 크론잡 1회 실행 확인
- [ ] 7.4 - 문서화 (README 또는 별도 가이드)

---

## 세션별 작업 기록

### 세션 1 (2026-01-23 오전)
- [x] 계획 수립
- [x] 사용자 요구사항 확인
- [x] 진행 상황 추적 파일 생성 (PROGRESS.md)

### 세션 2 (2026-01-23 오후)
- [x] Phase 0 완료 (환경 확인)
  - ClickHouse Docker 시작
  - Python 버전 확인 (3.11.7)
  - requirements.txt 백업
- [x] Phase 1 완료 (기초 작업)
  - requirements.txt에 yfinance, clickhouse-connect, python-dateutil 추가
  - 패키지 설치 및 임포트 테스트
  - 디렉토리 구조 생성 (trading_system/ingestion/, scripts/)
- [~] Phase 2 진행중 (ClickHouse 스키마)
  - clickhouse_schema.py 파일 생성 완료
  - 모든 함수 구현 완료 (get_client, initialize_schema, verify_connection 등)
  - 테스트 중 ClickHouse 인증 오류 발생 (권한 문제)
  - docker-compose.yml 수정 (비밀번호 설정)
- [!] 다음 세션: ch_data, ch_logs 삭제 후 Phase 2 테스트 완료 및 Phase 3 진행

### 세션 3 (2026-01-25 오전)

#### Phase 2 완료 (ClickHouse 스키마)
- [x] docker compose 재시작 (깨끗한 상태에서 시작)
  - 기존 ch_data, ch_logs 디렉토리 없음 확인
  - docker-compose.yml 비밀번호 설정 적용
  - `docker compose up -d` 성공
- [x] ClickHouse 연결 테스트 성공
  - `curl http://localhost:8123/ping` → Ok
  - clickhouse_schema.py 테스트 완료
  - stock_ohlcv, ingestion_log 테이블 생성 확인
  - ClickHouse 클라이언트로 SHOW TABLES 확인

#### Phase 3 완료 (Yahoo Finance 데이터 수집)
- [x] yahoo_finance.py 작성
  - `fetch_ticker_data()` - Yahoo Finance API 호출
  - `validate_data()` - 데이터 검증 (NULL, 음수, OHLC 관계)
  - 재시도 로직 (max_retries=3, retry_delay=5초)
  - 에러 핸들링 및 로깅
- [x] ingest_data.py 스크립트 작성
  - CLI 인자 파싱 (--tickers, --start-date, --end-date)
  - `insert_ohlcv_data()` - ClickHouse 배치 삽입
  - `update_ingestion_log()` - ingestion_log 업데이트
  - `ingest_ticker()` - 전체 수집 파이프라인
- [x] ^GSPC 티커로 테스트 성공
  - 2024년 1월 데이터 수집 (21 rows)
  - ClickHouse에 정상 저장 확인
  - ingestion_log 업데이트 확인
  - 데이터 검증: 중복 없음, 유효성 통과

#### Phase 4 완료 (ClickHouseDataProvider 구현)
- [x] clickhouse_provider.py 작성
  - `DataProvider` 인터페이스 구현
  - `get_ohlcv()` - 기간별 OHLCV 데이터 조회
  - `get_current_ohlcv()` - 최신 OHLCV 조회
  - `get_tickers()` - 티커 목록 조회
  - `get_date_range()` - 티커별 날짜 범위 조회
  - `get_record_count()` - 레코드 수 조회
  - `use_adjusted_close` 옵션 (True: adjusted_close, False: close)
- [x] test_clickhouse_provider.py 작성 및 테스트
  - 모든 메서드 정상 작동 확인
  - ^GSPC 데이터 21 rows 조회 성공
  - DataFrame 형식 올바름 (date, open, high, low, close, volume)
- [x] verify_data.py 작성
  - 티커별 통계 (record_count, date_range, avg/min/max prices)
  - 중복 데이터 감지
  - 데이터 유효성 검사 (음수, OHLC 관계, volume)
  - NULL 값 확인
  - 날짜 간격 확인
  - ingestion_log 조회
  - ^GSPC 데이터 검증 완료: ✓ No duplicates, ✓ All valid

#### Phase 5 완료 (백테스트 통합)
- [x] config.yaml 수정
  - `database` 섹션 추가 (host, port, database, user, password, use_adjusted_close)
  - `data_ingestion` 섹션 추가 (default_lookback_days, max_retries, retry_delay)
  - tickers를 Yahoo Finance 형식으로 변경 (^GSPC, 005930.KS 등)
  - 테스트용 날짜 범위 설정 (2024-01-01 ~ 2024-01-31)
- [x] config.py 수정
  - `DatabaseConfig` 클래스 추가
  - `DataIngestionConfig` 클래스 추가
  - `Config` 클래스에 database, data_ingestion 필드 추가
  - `_from_dict()` 메서드 업데이트
- [x] run_backtest.py 수정
  - `ClickHouseDataProvider` 임포트
  - `--source` 옵션 추가 (choices: sample, clickhouse)
  - ClickHouse 데이터 로드 로직 구현
  - 사용 가능한 티커 확인 및 에러 처리
  - 기존 --sample 옵션 하위 호환성 유지
- [x] 백테스트 실행 테스트
  - `python run_backtest.py --source clickhouse` → 성공
    - ^GSPC 21일 데이터 로드
    - 백테스트 정상 실행
  - `python run_backtest.py --source sample` → 성공
  - `python run_backtest.py --sample` → 성공 (기존 방식)

#### 현재 ClickHouse 데이터 상태
```
티커: ^GSPC
레코드 수: 21 rows
날짜 범위: 2024-01-02 ~ 2024-01-31
상태: success
마지막 수집: 2026-01-25 06:06:08
검증 결과: ✓ No duplicates, ✓ All valid, ✓ No NULLs
```

---

## 오류 로그

### 2026-01-23 | Phase 2.1 | ClickHouse 인증 실패 [해결됨]
**오류 내용**:
- DatabaseError: Authentication failed: password is incorrect
- 기존 ch_data, ch_logs 디렉토리가 systemd-network 소유로 생성되어 권한 문제 발생
- docker-compose.yml에 비밀번호 설정했으나 기존 데이터 때문에 적용 안됨

**해결 방법**:
1. 2026-01-25 세션에서 확인: ch_data, ch_logs 디렉토리가 존재하지 않음 (깨끗한 상태)
2. docker-compose.yml 비밀번호 설정 그대로 사용
3. `docker compose up -d` 성공
4. ClickHouse 연결 및 스키마 테스트 통과

**결과**: ✅ 문제 해결 완료

---

## 참고 사항

### ClickHouse 유용한 쿼리
```sql
-- 전체 테이블 확인
SHOW TABLES;

-- 데이터 개수
SELECT COUNT(*) FROM stock_ohlcv;

-- 티커별 통계
SELECT ticker, COUNT(*) as cnt, MIN(date), MAX(date)
FROM stock_ohlcv
GROUP BY ticker;

-- 최근 데이터
SELECT * FROM stock_ohlcv ORDER BY date DESC LIMIT 10;

-- 중복 확인
SELECT ticker, date, COUNT(*) as cnt
FROM stock_ohlcv
GROUP BY ticker, date
HAVING cnt > 1;
```

### 문제 해결 체크리스트
1. ClickHouse 실행 중인가? → `docker ps`
2. 네트워크 연결되었나? → `curl http://localhost:8123/ping`
3. 패키지 설치되었나? → `pip list | grep clickhouse`
4. 테이블 존재하나? → `SHOW TABLES`
5. 데이터 있나? → `SELECT COUNT(*) FROM stock_ohlcv`

---

## 다음 세션 시작 시 체크리스트

1. [ ] PROGRESS.md 읽고 "현재 시스템 상태 요약" 섹션 확인
2. [ ] ClickHouse 컨테이너 실행 상태 확인
   ```bash
   docker ps | grep clickhouse
   curl http://localhost:8123/ping
   ```
3. [ ] 현재 저장된 데이터 확인
   ```bash
   python scripts/verify_data.py --all
   ```
4. [ ] "다음 세션 시작 시 가이드"에서 작업 선택
5. [ ] HOW_TO_PROCEED.md의 워크플로우 참고

---

**마지막 업데이트**: 2026-01-25 06:25 (세션 3 종료)

---

## 현재 시스템 상태 요약

### 완료된 기능
✅ **ClickHouse 통합 완료** (Phase 2-5)
- ClickHouse Docker 컨테이너 실행 중
- stock_ohlcv, ingestion_log 테이블 생성
- Yahoo Finance 데이터 수집 파이프라인 구축
- ClickHouseDataProvider 구현
- 백테스트 시스템과 통합

### 사용 가능한 명령어

#### 1. 데이터 수집
```bash
# 단일 티커 수집
python scripts/ingest_data.py --tickers "^GSPC" \
  --start-date "2024-01-01" --end-date "2024-01-31"

# 여러 티커 동시 수집
python scripts/ingest_data.py --tickers "^GSPC,005930.KS,000660.KS" \
  --start-date "2023-01-01" --end-date "2024-12-31"

# 최근 1년 데이터 (기본값)
python scripts/ingest_data.py --tickers "^GSPC"
```

#### 2. 데이터 검증
```bash
# 특정 티커 검증
python scripts/verify_data.py --ticker "^GSPC"

# 전체 데이터 검증
python scripts/verify_data.py --all
```

#### 3. 백테스트 실행
```bash
# ClickHouse 데이터 사용
python run_backtest.py --source clickhouse

# 샘플 데이터 사용
python run_backtest.py --source sample
python run_backtest.py --sample  # 기존 방식도 가능
```

#### 4. ClickHouse 직접 조회
```bash
# 티커 목록
docker exec clickhouse-server clickhouse-client --password password \
  --query "SELECT DISTINCT ticker FROM stock_ohlcv"

# 티커별 통계
docker exec clickhouse-server clickhouse-client --password password \
  --query "SELECT ticker, COUNT(*), MIN(date), MAX(date) FROM stock_ohlcv GROUP BY ticker"

# 데이터 조회
docker exec clickhouse-server clickhouse-client --password password \
  --query "SELECT * FROM stock_ohlcv WHERE ticker='^GSPC' ORDER BY date LIMIT 10"
```

### 현재 저장된 데이터
- 티커: `^GSPC` (S&P 500 Index)
- 기간: 2024-01-02 ~ 2024-01-31
- 레코드 수: 21 rows
- 상태: 검증 완료 ✓

### 주요 파일 위치

**데이터 수집**
- `trading_system/ingestion/clickhouse_schema.py` - DB 스키마 및 연결
- `trading_system/ingestion/yahoo_finance.py` - Yahoo Finance API 호출
- `scripts/ingest_data.py` - 데이터 수집 실행 스크립트

**데이터 제공**
- `trading_system/data/clickhouse_provider.py` - ClickHouseDataProvider 구현
- `scripts/test_clickhouse_provider.py` - Provider 테스트 스크립트
- `scripts/verify_data.py` - 데이터 품질 검증 스크립트

**백테스트 통합**
- `config.yaml` - 설정 파일 (database, data_ingestion 섹션 추가됨)
- `trading_system/utils/config.py` - DatabaseConfig, DataIngestionConfig 클래스
- `run_backtest.py` - --source clickhouse 옵션 추가됨

**Docker**
- `docker-compose.yml` - ClickHouse 컨테이너 설정
- `ch_data/` - ClickHouse 데이터 볼륨
- `ch_logs/` - ClickHouse 로그 볼륨

---

## 다음 세션 시작 시 가이드

### 옵션 1: 더 많은 데이터 수집
추가 티커나 더 긴 기간의 데이터를 수집하여 백테스트 정확도 향상:
```bash
# 한국 주식 수집
python scripts/ingest_data.py --tickers "005930.KS,000660.KS" \
  --start-date "2023-01-01" --end-date "2024-12-31"

# 미국 주식 수집
python scripts/ingest_data.py --tickers "AAPL,MSFT,GOOGL" \
  --start-date "2023-01-01" --end-date "2024-12-31"
```

### 옵션 2: Phase 6 진행 (자동 업데이트)
증분 데이터 수집 및 크론잡 설정:
- `update_data.py` 작성 (마지막 수집 날짜 이후 데이터만 수집)
- 크론잡 설정 (매일 자동 업데이트)

### 옵션 3: Phase 7 진행 (최종 검증)
전체 시스템 검증 및 문서화:
- 여러 티커로 백테스트 실행
- 데이터 품질 전체 검증
- 사용 가이드 문서화

### 옵션 4: 전략 개선
현재 백테스트 시스템을 활용하여 전략 최적화:
- config.yaml에서 전략 파라미터 조정
- 다양한 티커 조합 테스트
- 성과 분석 및 개선

---

## 문제 해결

### ClickHouse 재시작
```bash
docker compose down
docker compose up -d
```

### 데이터 초기화 (주의: 모든 데이터 삭제)
```bash
docker compose down
sudo rm -rf ch_data ch_logs
docker compose up -d
```

### 테이블 재생성
```python
python3 -c "
from trading_system.ingestion.clickhouse_schema import get_client, initialize_schema
client = get_client('localhost', 8123, 'default', password='password')
initialize_schema(client)
"
```

---

**다음 작업 (선택사항)**:
1. [ ] Phase 6 - update_data.py 작성 (증분 데이터 수집)
2. [ ] Phase 6 - 크론잡 설정
3. [ ] Phase 7 - 최종 검증 및 문서화
4. [ ] 추가 데이터 수집 (더 많은 티커, 더 긴 기간)
5. [ ] 전략 파라미터 최적화
