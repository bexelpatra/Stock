#!/usr/bin/env python3
"""
Yahoo Finance 데이터를 ClickHouse로 수집하는 스크립트
"""
import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
import logging

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from trading_system.ingestion.clickhouse_schema import get_client, initialize_schema
from trading_system.ingestion.yahoo_finance import fetch_ticker_data

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def insert_ohlcv_data(client, ticker: str, df) -> int:
    """
    OHLCV 데이터를 ClickHouse에 삽입

    Args:
        client: ClickHouse 클라이언트
        ticker: 티커 심볼
        df: OHLCV DataFrame

    Returns:
        삽입된 레코드 수
    """
    if df is None or df.empty:
        logger.warning(f"No data to insert for {ticker}")
        return 0

    # DataFrame을 ClickHouse 형식으로 변환
    # ticker 컬럼 추가
    df = df.copy()
    df['ticker'] = ticker

    # 컬럼 순서 맞추기 (adjusted_close로 이름 변경)
    df = df.rename(columns={'adj_close': 'adjusted_close'})

    # ClickHouse에 삽입할 컬럼 선택
    columns = ['ticker', 'date', 'open', 'high', 'low', 'close', 'adjusted_close', 'volume']
    data = df[columns].values.tolist()

    try:
        # 배치 삽입
        client.insert('stock_ohlcv', data, column_names=columns)
        logger.info(f"Inserted {len(data)} rows for {ticker}")
        return len(data)
    except Exception as e:
        logger.error(f"Error inserting data for {ticker}: {e}")
        raise


def update_ingestion_log(client, ticker: str, last_date: date, record_count: int, status: str = 'success'):
    """
    ingestion_log 테이블 업데이트

    Args:
        client: ClickHouse 클라이언트
        ticker: 티커 심볼
        last_date: 마지막 데이터 날짜
        record_count: 삽입된 레코드 수
        status: 상태 ('success' 또는 'failed')
    """
    data = [[
        ticker,
        last_date,
        datetime.now(),
        record_count,
        status
    ]]

    try:
        client.insert('ingestion_log', data, column_names=['ticker', 'last_date', 'last_ingestion', 'record_count', 'status'])
        logger.info(f"Updated ingestion_log for {ticker}")
    except Exception as e:
        logger.error(f"Error updating ingestion_log for {ticker}: {e}")
        # 로그 업데이트 실패는 치명적이지 않으므로 예외를 발생시키지 않음


def ingest_ticker(client, ticker: str, start_date: date, end_date: date) -> bool:
    """
    단일 티커의 데이터를 수집하고 ClickHouse에 저장

    Args:
        client: ClickHouse 클라이언트
        ticker: 티커 심볼
        start_date: 시작 날짜
        end_date: 종료 날짜

    Returns:
        성공 시 True, 실패 시 False
    """
    logger.info(f"Starting ingestion for {ticker} ({start_date} to {end_date})")

    try:
        # 1. Yahoo Finance에서 데이터 수집
        df = fetch_ticker_data(ticker, start_date, end_date)

        if df is None or df.empty:
            logger.warning(f"No data fetched for {ticker}")
            update_ingestion_log(client, ticker, end_date, 0, 'failed')
            return False

        # 2. ClickHouse에 데이터 삽입
        record_count = insert_ohlcv_data(client, ticker, df)

        # 3. ingestion_log 업데이트
        last_date = df['date'].max()
        if isinstance(last_date, str):
            last_date = datetime.strptime(last_date, '%Y-%m-%d').date()

        update_ingestion_log(client, ticker, last_date, record_count, 'success')

        logger.info(f"Successfully ingested {record_count} rows for {ticker}")
        return True

    except Exception as e:
        logger.error(f"Error ingesting {ticker}: {e}", exc_info=True)
        update_ingestion_log(client, ticker, end_date, 0, 'failed')
        return False


def main():
    parser = argparse.ArgumentParser(description='Ingest stock data from Yahoo Finance to ClickHouse')

    # 티커 관련 인자
    parser.add_argument(
        '--tickers',
        type=str,
        required=True,
        help='Comma-separated ticker symbols (e.g., "^GSPC,005930.KS,AAPL")'
    )

    # 날짜 관련 인자
    parser.add_argument(
        '--start-date',
        type=str,
        default=None,
        help='Start date in YYYY-MM-DD format (default: 365 days ago)'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        default=None,
        help='End date in YYYY-MM-DD format (default: today)'
    )

    # ClickHouse 연결 정보
    parser.add_argument('--host', type=str, default='localhost', help='ClickHouse host')
    parser.add_argument('--port', type=int, default=8123, help='ClickHouse HTTP port')
    parser.add_argument('--database', type=str, default='default', help='ClickHouse database')
    parser.add_argument('--user', type=str, default='default', help='ClickHouse user')
    parser.add_argument('--password', type=str, default='password', help='ClickHouse password')

    # 기타
    parser.add_argument('--init-schema', action='store_true', help='Initialize schema before ingestion')

    args = parser.parse_args()

    # 날짜 파싱
    if args.end_date:
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
    else:
        end_date = date.today()

    if args.start_date:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
    else:
        start_date = end_date - timedelta(days=365)

    # 티커 리스트 파싱
    tickers = [t.strip() for t in args.tickers.split(',')]

    logger.info(f"Ingestion parameters:")
    logger.info(f"  Tickers: {tickers}")
    logger.info(f"  Date range: {start_date} to {end_date}")
    logger.info(f"  ClickHouse: {args.host}:{args.port}/{args.database}")

    try:
        # ClickHouse 연결
        client = get_client(
            host=args.host,
            port=args.port,
            database=args.database,
            user=args.user,
            password=args.password
        )
        logger.info("Connected to ClickHouse")

        # 스키마 초기화 (선택사항)
        if args.init_schema:
            initialize_schema(client)
            logger.info("Schema initialized")

        # 각 티커별 데이터 수집
        success_count = 0
        fail_count = 0

        for ticker in tickers:
            if ingest_ticker(client, ticker, start_date, end_date):
                success_count += 1
            else:
                fail_count += 1

        # 결과 요약
        logger.info("=" * 60)
        logger.info(f"Ingestion completed:")
        logger.info(f"  Success: {success_count}/{len(tickers)}")
        logger.info(f"  Failed: {fail_count}/{len(tickers)}")

        # 종료 코드
        sys.exit(0 if fail_count == 0 else 1)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
