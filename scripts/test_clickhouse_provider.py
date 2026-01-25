#!/usr/bin/env python3
"""
ClickHouseDataProvider 테스트 스크립트
"""
import sys
from datetime import date
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from trading_system.data.clickhouse_provider import ClickHouseDataProvider


def main():
    print("=" * 60)
    print("ClickHouseDataProvider 테스트")
    print("=" * 60)

    # ClickHouseDataProvider 생성
    provider = ClickHouseDataProvider(
        host='localhost',
        port=8123,
        database='default',
        password='password',
        use_adjusted_close=True
    )

    # 1. 티커 목록 조회
    print("\n[1] 티커 목록 조회")
    tickers = provider.get_tickers()
    print(f"Available tickers: {tickers}")

    if not tickers:
        print("No tickers found in ClickHouse")
        return

    ticker = tickers[0]
    print(f"\n테스트 대상 티커: {ticker}")

    # 2. 날짜 범위 조회
    print("\n[2] 날짜 범위 조회")
    date_range = provider.get_date_range(ticker)
    if date_range:
        print(f"Date range: {date_range[0]} to {date_range[1]}")
    else:
        print("No date range found")

    # 3. OHLCV 데이터 조회
    print("\n[3] OHLCV 데이터 조회 (2024-01-01 ~ 2024-01-31)")
    df = provider.get_ohlcv(ticker, date(2024, 1, 1), date(2024, 1, 31))
    print(f"Fetched {len(df)} rows")
    print(f"\nFirst 5 rows:")
    print(df.head())
    print(f"\nData types:")
    print(df.dtypes)

    # 4. 최신 OHLCV 조회
    print("\n[4] 최신 OHLCV 조회")
    current = provider.get_current_ohlcv(ticker)
    print(f"Date: {current.date}")
    print(f"Open: {current.open}")
    print(f"High: {current.high}")
    print(f"Low: {current.low}")
    print(f"Close: {current.close}")
    print(f"Volume: {current.volume}")

    # 5. 레코드 수 조회
    print("\n[5] 레코드 수 조회")
    count = provider.get_record_count(ticker)
    print(f"Total records for {ticker}: {count}")

    total_count = provider.get_record_count()
    print(f"Total records (all tickers): {total_count}")

    print("\n" + "=" * 60)
    print("✓ 모든 테스트 완료")
    print("=" * 60)


if __name__ == "__main__":
    main()
