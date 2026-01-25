#!/usr/bin/env python3
"""
ClickHouse에 저장된 주가 데이터 품질 검증 스크립트
"""
import argparse
import sys
from pathlib import Path
from datetime import date, timedelta

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from trading_system.ingestion.clickhouse_schema import get_client
import pandas as pd


class DataVerifier:
    """데이터 품질 검증 클래스"""

    def __init__(self, client):
        self.client = client

    def get_ticker_statistics(self, ticker: str = None) -> pd.DataFrame:
        """티커별 통계 조회"""
        if ticker:
            query = """
                SELECT
                    ticker,
                    COUNT(*) as record_count,
                    MIN(date) as min_date,
                    MAX(date) as max_date,
                    AVG(close) as avg_close,
                    MIN(close) as min_close,
                    MAX(close) as max_close,
                    AVG(volume) as avg_volume
                FROM stock_ohlcv
                WHERE ticker = %(ticker)s
                GROUP BY ticker
            """
            result = self.client.query(query, parameters={"ticker": ticker})
        else:
            query = """
                SELECT
                    ticker,
                    COUNT(*) as record_count,
                    MIN(date) as min_date,
                    MAX(date) as max_date,
                    AVG(close) as avg_close,
                    MIN(close) as min_close,
                    MAX(close) as max_close,
                    AVG(volume) as avg_volume
                FROM stock_ohlcv
                GROUP BY ticker
                ORDER BY ticker
            """
            result = self.client.query(query)

        df = pd.DataFrame(
            result.result_rows,
            columns=['ticker', 'record_count', 'min_date', 'max_date',
                     'avg_close', 'min_close', 'max_close', 'avg_volume']
        )
        return df

    def check_duplicates(self, ticker: str = None) -> pd.DataFrame:
        """중복 데이터 확인"""
        if ticker:
            query = """
                SELECT ticker, date, COUNT(*) as count
                FROM stock_ohlcv
                WHERE ticker = %(ticker)s
                GROUP BY ticker, date
                HAVING count > 1
                ORDER BY date
            """
            result = self.client.query(query, parameters={"ticker": ticker})
        else:
            query = """
                SELECT ticker, date, COUNT(*) as count
                FROM stock_ohlcv
                GROUP BY ticker, date
                HAVING count > 1
                ORDER BY ticker, date
            """
            result = self.client.query(query)

        df = pd.DataFrame(
            result.result_rows,
            columns=['ticker', 'date', 'count']
        )
        return df

    def check_invalid_prices(self, ticker: str = None) -> dict:
        """잘못된 가격 데이터 확인 (음수, 0, high < low 등)"""
        base_where = f"ticker = '{ticker}'" if ticker else "1=1"

        # 음수/0 가격
        query_negative = f"""
            SELECT COUNT(*) FROM stock_ohlcv
            WHERE {base_where} AND (open <= 0 OR high <= 0 OR low <= 0 OR close <= 0)
        """

        # high < low
        query_high_low = f"""
            SELECT COUNT(*) FROM stock_ohlcv
            WHERE {base_where} AND high < low
        """

        # close < low or close > high
        query_close_range = f"""
            SELECT COUNT(*) FROM stock_ohlcv
            WHERE {base_where} AND (close < low OR close > high)
        """

        # open < low or open > high
        query_open_range = f"""
            SELECT COUNT(*) FROM stock_ohlcv
            WHERE {base_where} AND (open < low OR open > high)
        """

        # 음수 volume
        query_negative_volume = f"""
            SELECT COUNT(*) FROM stock_ohlcv
            WHERE {base_where} AND volume < 0
        """

        return {
            'negative_or_zero_prices': self.client.command(query_negative),
            'high_less_than_low': self.client.command(query_high_low),
            'close_out_of_range': self.client.command(query_close_range),
            'open_out_of_range': self.client.command(query_open_range),
            'negative_volume': self.client.command(query_negative_volume),
        }

    def check_null_values(self, ticker: str = None) -> dict:
        """NULL 값 확인"""
        base_where = f"ticker = '{ticker}'" if ticker else "1=1"

        columns = ['open', 'high', 'low', 'close', 'adjusted_close', 'volume']
        null_counts = {}

        for col in columns:
            query = f"""
                SELECT COUNT(*) FROM stock_ohlcv
                WHERE {base_where} AND {col} IS NULL
            """
            null_counts[col] = self.client.command(query)

        return null_counts

    def find_date_gaps(self, ticker: str) -> list:
        """날짜 간격(gap) 찾기 (5일 이상 차이나는 경우)"""
        query = """
            SELECT
                date as current_date,
                lagInFrame(date) OVER (ORDER BY date) as prev_date,
                dateDiff('day', lagInFrame(date) OVER (ORDER BY date), date) as gap_days
            FROM stock_ohlcv
            WHERE ticker = %(ticker)s
            ORDER BY date
        """
        result = self.client.query(query, parameters={"ticker": ticker})

        gaps = []
        for row in result.result_rows:
            current_date, prev_date, gap_days = row
            if prev_date and gap_days > 5:  # 주말 제외 5일 이상 gap
                gaps.append({
                    'prev_date': prev_date,
                    'current_date': current_date,
                    'gap_days': gap_days
                })

        return gaps

    def get_ingestion_log(self) -> pd.DataFrame:
        """ingestion_log 테이블 조회"""
        query = """
            SELECT
                ticker,
                last_date,
                last_ingestion,
                record_count,
                status
            FROM ingestion_log
            ORDER BY last_ingestion DESC
        """
        result = self.client.query(query)

        df = pd.DataFrame(
            result.result_rows,
            columns=['ticker', 'last_date', 'last_ingestion', 'record_count', 'status']
        )
        return df


def print_section(title: str):
    """섹션 제목 출력"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description='Verify data quality in ClickHouse')

    parser.add_argument(
        '--ticker',
        type=str,
        default=None,
        help='Specific ticker to verify (default: all tickers)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Run all verification checks'
    )

    # ClickHouse 연결 정보
    parser.add_argument('--host', type=str, default='localhost', help='ClickHouse host')
    parser.add_argument('--port', type=int, default=8123, help='ClickHouse HTTP port')
    parser.add_argument('--database', type=str, default='default', help='ClickHouse database')
    parser.add_argument('--password', type=str, default='password', help='ClickHouse password')

    args = parser.parse_args()

    # ClickHouse 연결
    client = get_client(
        host=args.host,
        port=args.port,
        database=args.database,
        password=args.password
    )

    verifier = DataVerifier(client)

    print_section("ClickHouse 데이터 품질 검증")

    # 1. 티커별 통계
    print_section("1. 티커별 통계")
    stats_df = verifier.get_ticker_statistics(args.ticker)
    if not stats_df.empty:
        print(stats_df.to_string(index=False))
    else:
        print("No data found")

    # 2. 중복 데이터 확인
    print_section("2. 중복 데이터 확인")
    duplicates_df = verifier.check_duplicates(args.ticker)
    if not duplicates_df.empty:
        print(f"⚠️  Found {len(duplicates_df)} duplicate records:")
        print(duplicates_df.to_string(index=False))
    else:
        print("✓ No duplicates found")

    # 3. 잘못된 가격 확인
    print_section("3. 데이터 유효성 검사")
    invalid_prices = verifier.check_invalid_prices(args.ticker)
    has_issues = False
    for check, count in invalid_prices.items():
        status = "⚠️ " if count > 0 else "✓"
        print(f"{status} {check}: {count}")
        if count > 0:
            has_issues = True

    if not has_issues:
        print("\n✓ All price data is valid")

    # 4. NULL 값 확인
    print_section("4. NULL 값 확인")
    null_counts = verifier.check_null_values(args.ticker)
    has_nulls = False
    for col, count in null_counts.items():
        if count > 0:
            print(f"⚠️  {col}: {count} NULL values")
            has_nulls = True

    if not has_nulls:
        print("✓ No NULL values found")

    # 5. 날짜 간격 확인 (특정 티커만)
    if args.ticker:
        print_section(f"5. 날짜 간격 확인 ({args.ticker})")
        gaps = verifier.find_date_gaps(args.ticker)
        if gaps:
            print(f"⚠️  Found {len(gaps)} date gaps (>5 days):")
            for gap in gaps[:10]:  # 최대 10개만 출력
                print(f"  {gap['prev_date']} → {gap['current_date']} ({gap['gap_days']} days)")
            if len(gaps) > 10:
                print(f"  ... and {len(gaps) - 10} more gaps")
        else:
            print("✓ No significant date gaps found")

    # 6. ingestion_log 확인
    if args.all:
        print_section("6. Ingestion Log")
        log_df = verifier.get_ingestion_log()
        if not log_df.empty:
            print(log_df.to_string(index=False))
        else:
            print("No ingestion log found")

    # 요약
    print_section("검증 완료")
    total_records = verifier.client.command("SELECT COUNT(*) FROM stock_ohlcv")
    total_tickers = verifier.client.command("SELECT COUNT(DISTINCT ticker) FROM stock_ohlcv")
    print(f"Total records: {total_records}")
    print(f"Total tickers: {total_tickers}")
    print()


if __name__ == "__main__":
    main()
