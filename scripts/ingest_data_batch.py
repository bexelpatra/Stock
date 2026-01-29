#!/usr/bin/env python3
"""
Yahoo Finance 데이터를 ClickHouse로 배치 수집하는 스크립트
(대량 데이터를 월별로 나눠서 삽입)
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
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def insert_ohlcv_data_batch(client, ticker: str, df, batch_size: int = 100) -> int:
    """
    OHLCV 데이터를 ClickHouse에 배치 삽입

    Args:
        client: ClickHouse 클라이언트
        ticker: 티커 심볼
        df: OHLCV DataFrame
        batch_size: 배치 크기 (일 단위)

    Returns:
        삽입된 레코드 수
    """
    if df is None or df.empty:
        logger.warning(f"No data to insert for {ticker}")
        return 0

    # DataFrame을 ClickHouse 형식으로 변환
    df = df.copy()
    df['ticker'] = ticker

    # 컬럼 순서 맞추기
    df = df.rename(columns={'adj_close': 'adjusted_close'})

    # ClickHouse에 삽입할 컬럼 선택
    columns = ['ticker', 'date', 'open', 'high', 'low', 'close', 'adjusted_close', 'volume']

    # 배치로 나눠서 삽입
    total_rows = len(df)
    inserted = 0

    for i in range(0, total_rows, batch_size):
        batch_df = df.iloc[i:i+batch_size]
        data = batch_df[columns].values.tolist()

        try:
            client.insert('stock_ohlcv', data, column_names=columns)
            inserted += len(data)
            logger.info(f"Inserted batch {i//batch_size + 1}: {len(data)} rows (total: {inserted}/{total_rows})")
        except Exception as e:
            logger.error(f"Error inserting batch {i//batch_size + 1} for {ticker}: {e}")
            raise

    logger.info(f"Successfully inserted {inserted} total rows for {ticker}")
    return inserted


def update_ingestion_log(client, ticker: str, start_date: date, end_date: date,
                         record_count: int, status: str = 'success'):
    """
    ingestion_log 테이블 업데이트
    """
    data = [[
        ticker,
        start_date,
        end_date,
        record_count,
        status,
        datetime.now()
    ]]

    try:
        client.insert('ingestion_log', data,
                     column_names=['ticker', 'start_date', 'end_date',
                                 'records_inserted', 'status', 'updated_at'])
        logger.info(f"Updated ingestion_log for {ticker}")
    except Exception as e:
        logger.error(f"Error updating ingestion_log for {ticker}: {e}")


def ingest_ticker_batch(client, ticker: str, start_date: date, end_date: date,
                       batch_size: int = 100) -> bool:
    """
    단일 티커의 데이터를 배치 수집하고 ClickHouse에 저장
    """
    logger.info(f"Starting ingestion for {ticker} ({start_date} to {end_date})")

    try:
        # 1. Yahoo Finance에서 데이터 수집
        df = fetch_ticker_data(ticker, start_date, end_date)

        if df is None or df.empty:
            logger.warning(f"No data fetched for {ticker}")
            update_ingestion_log(client, ticker, start_date, end_date, 0, 'failed')
            return False

        # 2. ClickHouse에 데이터 배치 삽입
        record_count = insert_ohlcv_data_batch(client, ticker, df, batch_size)

        # 3. ingestion_log 업데이트
        update_ingestion_log(client, ticker, start_date, end_date, record_count, 'success')

        logger.info(f"Successfully ingested {record_count} rows for {ticker}")
        return True

    except Exception as e:
        logger.error(f"Error ingesting {ticker}: {e}", exc_info=True)
        update_ingestion_log(client, ticker, start_date, end_date, 0, 'failed')
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Ingest stock data from Yahoo Finance to ClickHouse (with batching)'
    )

    parser.add_argument('--tickers', type=str, required=True,
                       help='Comma-separated ticker symbols')
    parser.add_argument('--start-date', type=str, default=None,
                       help='Start date in YYYY-MM-DD format (default: 1970-01-01)')
    parser.add_argument('--end-date', type=str, default=None,
                       help='End date in YYYY-MM-DD format (default: today)')
    parser.add_argument('--batch-size', type=int, default=100,
                       help='Batch size for insertion (default: 100 days)')

    # ClickHouse 연결 정보
    parser.add_argument('--host', type=str, default='localhost')
    parser.add_argument('--port', type=int, default=8123)
    parser.add_argument('--database', type=str, default='default')
    parser.add_argument('--user', type=str, default='default')
    parser.add_argument('--password', type=str, default='password')

    args = parser.parse_args()

    # 날짜 파싱
    if args.end_date:
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
    else:
        end_date = date.today()

    if args.start_date:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
    else:
        start_date = date(1970, 1, 1)

    # 티커 리스트 파싱
    tickers = [t.strip() for t in args.tickers.split(',')]

    logger.info(f"Ingestion parameters:")
    logger.info(f"  Tickers: {tickers}")
    logger.info(f"  Date range: {start_date} to {end_date}")
    logger.info(f"  Batch size: {args.batch_size} days")
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

        # 각 티커별 데이터 수집
        success_count = 0
        for ticker in tickers:
            if ingest_ticker_batch(client, ticker, start_date, end_date, args.batch_size):
                success_count += 1

        logger.info("=" * 60)
        logger.info(f"Ingestion completed:")
        logger.info(f"  Success: {success_count}/{len(tickers)}")
        logger.info(f"  Failed: {len(tickers) - success_count}/{len(tickers)}")

        return 0 if success_count == len(tickers) else 1

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
