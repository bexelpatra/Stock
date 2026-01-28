# 크론잡 설정 가이드

## 1. 스크립트 확인

스크립트가 정상적으로 생성되었는지 확인:
```bash
ls -lh scripts/update_stock_data.sh
```

## 2. 수동 테스트

크론잡 등록 전에 먼저 수동으로 실행해서 테스트:
```bash
cd /home/jai/class/Stock
./scripts/update_stock_data.sh
```

실행 결과는 `logs/update_YYYYMMDD_HHMMSS.log` 파일에 저장됩니다.

## 3. 크론잡 등록

### 3.1 크론탭 편집
```bash
crontab -e
```

### 3.2 다음 라인 추가

**옵션 1: 평일 오후 7시에 실행 (추천)**
```cron
0 19 * * 1-5 /home/jai/class/Stock/scripts/update_stock_data.sh
```

**옵션 2: 매일 오후 7시에 실행**
```cron
0 19 * * * /home/jai/class/Stock/scripts/update_stock_data.sh
```

**옵션 3: 평일 오전 9시에 실행 (장 시작 전)**
```cron
0 9 * * 1-5 /home/jai/class/Stock/scripts/update_stock_data.sh
```

**옵션 4: 평일 오후 4시에 실행 (미국 장 마감 후, 한국 시간 기준)**
```cron
0 16 * * 1-5 /home/jai/class/Stock/scripts/update_stock_data.sh
```

### 3.3 크론 시간 설명
```
*    *    *    *    *
│    │    │    │    │
│    │    │    │    └─ 요일 (0-6, 0=일요일)
│    │    │    └────── 월 (1-12)
│    │    └─────────── 일 (1-31)
│    └──────────────── 시 (0-23)
└───────────────────── 분 (0-59)
```

- `1-5`: 월요일~금요일
- `*`: 매번 (모든 값)

## 4. 크론잡 확인

### 등록된 크론잡 목록 확인
```bash
crontab -l
```

### 크론 로그 확인 (시스템 로그)
```bash
# 최근 크론 실행 로그
grep CRON /var/log/syslog | tail -20

# 또는
journalctl -u cron | tail -20
```

### 스크립트 실행 로그 확인
```bash
# 최신 로그 파일 확인
ls -lt logs/update_*.log | head -5

# 최신 로그 내용 보기
tail -f logs/update_$(ls -t logs/update_*.log | head -1 | xargs basename)

# 또는 모든 로그 확인
cat logs/update_*.log
```

## 5. 로그 관리

### 오래된 로그 삭제 (30일 이상)
```bash
find /home/jai/class/Stock/logs -name "update_*.log" -mtime +30 -delete
```

### 로그 자동 정리 크론잡 추가
매월 1일 새벽 2시에 30일 이상 된 로그 삭제:
```cron
0 2 1 * * find /home/jai/class/Stock/logs -name "update_*.log" -mtime +30 -delete
```

## 6. 문제 해결

### ClickHouse가 자동 시작되지 않는 경우

시스템 부팅 시 ClickHouse 자동 시작 설정:
```bash
# Docker compose 서비스로 등록 (systemd)
sudo systemctl enable docker

# 또는 크론으로 부팅 시 시작
crontab -e
@reboot cd /home/jai/class/Stock && docker compose up -d
```

### 크론잡이 실행되지 않는 경우

1. **크론 서비스 상태 확인**:
   ```bash
   sudo systemctl status cron
   ```

2. **스크립트 권한 확인**:
   ```bash
   ls -l /home/jai/class/Stock/scripts/update_stock_data.sh
   # -rwxr-xr-x (실행 권한 있어야 함)
   ```

3. **절대 경로 사용 확인**: 크론에서는 상대 경로가 작동하지 않음

4. **환경 변수 문제**: 스크립트에 모든 경로를 절대 경로로 지정했으므로 문제없음

### 스크립트 테스트

수동으로 실행해서 정상 작동하는지 확인:
```bash
cd /home/jai/class/Stock
./scripts/update_stock_data.sh
```

## 7. 알림 설정 (선택사항)

### 이메일 알림

크론에서 이메일 알림을 받으려면 crontab 상단에 추가:
```cron
MAILTO=your-email@example.com

0 19 * * 1-5 /home/jai/class/Stock/scripts/update_stock_data.sh
```

### Slack 웹훅 (고급)

스크립트 끝에 Slack 알림 추가:
```bash
# 성공 시
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Stock data update completed"}' \
  YOUR_SLACK_WEBHOOK_URL

# 실패 시
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Stock data update failed"}' \
  YOUR_SLACK_WEBHOOK_URL
```

## 8. 추천 설정

**평일 오후 7시 자동 업데이트 + 로그 정리**:
```bash
crontab -e
```

다음 내용 추가:
```cron
# Stock data update (Mon-Fri at 7:00 PM)
0 19 * * 1-5 /home/jai/class/Stock/scripts/update_stock_data.sh

# Clean old logs (1st day of month at 2:00 AM)
0 2 1 * * find /home/jai/class/Stock/logs -name "update_*.log" -mtime +30 -delete
```

## 9. 크론잡 제거

크론잡을 제거하려면:
```bash
crontab -e
# 해당 라인 삭제 후 저장
```

또는 전체 크론탭 삭제:
```bash
crontab -r
```
