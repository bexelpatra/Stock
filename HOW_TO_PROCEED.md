# 단계별 실행 가이드

이 문서는 ClickHouse + Yahoo Finance 통합 작업을 여러 세션에 걸쳐 진행하는 방법을 설명합니다.

---

## 파일 구조

```
/home/jai/class/Stock/
├── PROGRESS.md              ← 진행 상황 추적 (체크리스트)
├── HOW_TO_PROCEED.md        ← 이 파일 (실행 가이드)
└── .claude/plans/
    └── sunny-crafting-hoare.md  ← 전체 구현 계획
```

---

## 세션 시작 시 워크플로우

### 1단계: 현재 상태 파악
```bash
cd /home/jai/class/Stock
cat PROGRESS.md | grep -A 20 "현재 단계"
```

### 2단계: 이전 작업 검토
`PROGRESS.md`에서 다음을 확인:
- 마지막으로 완료된 Phase
- 오류 로그 (있다면)
- 다음 작업 항목

### 3단계: Claude에게 작업 요청

**템플릿**:
```
PROGRESS.md를 확인해줘.
현재 Phase X.Y 작업을 시작하려고 해.
고려사항과 예상 이슈를 검토하고, 실행해도 되는지 확인해줘.
문제없으면 작업을 진행해줘.
```

**예시**:
```
PROGRESS.md를 확인해줘.
Phase 1.1 (의존성 설치) 작업을 시작하려고 해.
requirements.txt 수정 전에 검토해줘.
```

### 4단계: 작업 실행
Claude가 다음을 수행:
1. 해당 Phase의 계획 검토
2. 예상 이슈 확인
3. 파일 수정 또는 명령 실행
4. 테스트 명령 실행
5. `PROGRESS.md` 업데이트

### 5단계: 검증
Claude가 제시한 테스트 명령을 실행하여 정상 동작 확인

### 6단계: 다음 단계 준비
- 작업이 성공하면 다음 Phase로 진행
- 오류 발생 시 오류 로그 기록 및 해결 방안 논의

---

## Phase별 실행 전략

### Phase 0-1: 환경 준비 (빠름, 한 세션)
- 의존성 설치
- 디렉토리 생성
- 기본 설정

→ **예상 시간**: 10분

### Phase 2: 스키마 구현 (중요, 한 세션)
- ClickHouse 테이블 생성
- 연결 테스트

→ **예상 시간**: 20분

### Phase 3: 데이터 수집 (복잡, 1-2 세션)
- Yahoo Finance 연동
- 데이터 삽입 스크립트

→ **예상 시간**: 30-40분

### Phase 4: DataProvider (중간, 한 세션)
- ClickHouseDataProvider 구현
- 검증 스크립트

→ **예상 시간**: 20분

### Phase 5: 백테스트 통합 (중요, 한 세션)
- 설정 파일 수정
- run_backtest.py 연동

→ **예상 시간**: 20분

### Phase 6: 자동화 (간단, 한 세션)
- 업데이트 스크립트
- 크론잡 설정

→ **예상 시간**: 15분

---

## 오류 처리 프로토콜

### 오류 발생 시
1. 오류 메시지 전체 복사
2. `PROGRESS.md`의 "오류 로그"에 기록:
   ```
   2026-01-23 | Phase 3.1 | ModuleNotFoundError: yfinance | pip install yfinance
   ```
3. Claude에게 오류 해결 요청:
   ```
   Phase 3.1에서 오류 발생했어.
   오류 내용: [오류 메시지 붙여넣기]
   해결 방법 알려줘.
   ```

### 해결 후
- 해당 항목을 `[x]`로 변경
- 오류 로그에 해결 방법 기록

---

## 각 Phase 시작 템플릿

### Phase 0: 환경 확인
```
Phase 0을 시작하자.
PROGRESS.md의 Phase 0 체크리스트를 보고
ClickHouse 상태와 환경을 확인해줘.
```

### Phase 1: 기초 작업
```
Phase 1을 시작하자.
requirements.txt 수정하고 의존성 설치해줘.
디렉토리도 생성해줘.
```

### Phase 2: 스키마 구현
```
Phase 2를 시작하자.
clickhouse_schema.py를 작성해줘.
테이블 생성 SQL 포함해서.
```

### Phase 3: 데이터 수집
```
Phase 3.1을 시작하자.
yahoo_finance.py를 먼저 작성해줘.
그 다음 ingest_data.py 스크립트 만들어줘.
```

### Phase 4: DataProvider
```
Phase 4를 시작하자.
clickhouse_provider.py를 작성해줘.
DataProvider 인터페이스를 구현하는거야.
```

### Phase 5: 백테스트 통합
```
Phase 5를 시작하자.
config.yaml, config.py, run_backtest.py를
순서대로 수정해줘.
```

### Phase 6: 자동화
```
Phase 6을 시작하자.
update_data.py 작성하고 크론잡 설정 방법 알려줘.
```

---

## 중단 및 재개

### 세션 중단 시
Claude에게 요청:
```
여기까지 진행 상황을 PROGRESS.md에 기록해줘.
다음 세션에 이어서 할 작업도 메모해줘.
```

### 세션 재개 시
Claude에게 요청:
```
PROGRESS.md를 읽고 현재 상태를 요약해줘.
다음에 할 작업이 뭔지 알려줘.
```

---

## 백업 전략

중요한 파일 수정 전 백업:
```bash
cp config.yaml config.yaml.backup
cp run_backtest.py run_backtest.py.backup
cp trading_system/utils/config.py trading_system/utils/config.py.backup
```

---

## 완료 확인

모든 Phase 완료 후:
```
Phase 7 최종 검증을 해줘.
백테스트 실행하고 결과 보여줘.
```

---

## 팁

1. **한 번에 하나씩**: 각 Phase를 완전히 완료하고 다음으로
2. **테스트 필수**: 각 단계마다 테스트 명령 실행
3. **오류 기록**: 오류 발생 시 반드시 기록
4. **백업**: 중요 파일 수정 전 백업
5. **검증**: Phase 완료 후 다음 단계 진행 조건 확인

---

**작성일**: 2026-01-23
**목적**: 중단 없는 점진적 개발
