#!/usr/bin/env python3
"""
ClickHouse의 주식 데이터를 자동으로 업데이트하는 스크립트
- ingestion_log를 조회하여 마지막 수집 날짜 확인
- 마지막 날짜 이후부터 오늘까지 증분 데이터 수집
- 중복 방지 로직 포함
"""
import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
import logging
import yaml

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from trading_system.ingestion.clickhouse_schema import (
    get_client,
    get_last_ingestion_date,
    get_date_range
)
from trading_system.ingestion.yahoo_finance import fetch_ticker_data

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """
    config.yaml 파일 로드

    Args:
        config_path: config.yaml 파일 경로

    Returns:
        설정 딕셔너리
    """
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        logger.error(f"Failed to load config file: {e}")
        raise


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


def get_update_date_range(client, ticker: str, max_lookback_days: int = 365) -> tuple:
    """
    업데이트할 날짜 범위 계산

    Args:
        client: ClickHouse 클라이언트
        ticker: 티커 심볼
        max_lookback_days: 최대 lookback 일수 (첫 수집인 경우)

    Returns:
        (start_date, end_date, is_first_ingestion) 튜플
    """
    today = date.today()

    # ingestion_log에서 마지막 수집 날짜 확인
    last_ingestion_date = get_last_ingestion_date(client, ticker)

    if last_ingestion_date:
        # 증분 업데이트: 마지막 수집일 다음날부터 오늘까지
        start_date = last_ingestion_date + timedelta(days=1)

        # 이미 최신 데이터가 있는 경우
        if start_date > today:
            logger.info(f"{ticker}: Already up-to-date (last date: {last_ingestion_date})")
            return None, None, False

        logger.info(f"{ticker}: Incremental update from {start_date} to {today}")
        return start_date, today, False
    else:
        # 첫 수집: max_lookback_days 이전부터 오늘까지
        start_date = today - timedelta(days=max_lookback_days)
        logger.info(f"{ticker}: First ingestion from {start_date} to {today}")
        return start_date, today, True


def update_ticker(client, ticker: str, max_lookback_days: int = 365) -> bool:
    """
    단일 티커의 데이터를 증분 업데이트

    Args:
        client: ClickHouse 클라이언트
        ticker: 티커 심볼
        max_lookback_days: 첫 수집 시 lookback 일수

    Returns:
        성공 시 True, 실패 또는 스킵 시 False
    """
    try:
        # 업데이트할 날짜 범위 계산
        start_date, end_date, is_first = get_update_date_range(client, ticker, max_lookback_days)

        # 업데이트할 데이터가 없으면 스킵
        if start_date is None or end_date is None:
            return True  # 이미 최신이므로 성공으로 간주

        # Yahoo Finance에서 데이터 수집
        df = fetch_ticker_data(ticker, start_date, end_date)

        if df is None or df.empty:
            logger.warning(f"{ticker}: No data fetched for {start_date} to {end_date}")
            update_ingestion_log(client, ticker, end_date, 0, 'failed')
            return False

        # ClickHouse에 데이터 삽입
        record_count = insert_ohlcv_data(client, ticker, df)

        # ingestion_log 업데이트
        last_date = df['date'].max()
        if isinstance(last_date, str):
            last_date = datetime.strptime(last_date, '%Y-%m-%d').date()

        update_ingestion_log(client, ticker, last_date, record_count, 'success')

        logger.info(f"{ticker}: Successfully updated {record_count} rows")
        return True

    except Exception as e:
        logger.error(f"{ticker}: Error during update: {e}", exc_info=True)
        try:
            update_ingestion_log(client, ticker, date.today(), 0, 'failed')
        except:
            pass
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Update stock data in ClickHouse with incremental ingestion'
    )

    # 설정 파일
    parser.add_argument(
        '--config',
        type=str,
        default='config.yaml',
        help='Path to config.yaml file (default: config.yaml)'
    )

    # ClickHouse 연결 정보 (config.yaml 오버라이드)
    parser.add_argument('--host', type=str, help='ClickHouse host (overrides config)')
    parser.add_argument('--port', type=int, help='ClickHouse HTTP port (overrides config)')
    parser.add_argument('--database', type=str, help='ClickHouse database (overrides config)')
    parser.add_argument('--user', type=str, help='ClickHouse user (overrides config)')
    parser.add_argument('--password', type=str, help='ClickHouse password (overrides config)')

    # 티커 선택 (선택사항)
    parser.add_argument(
        '--tickers',
        type=str,
        help='Comma-separated ticker symbols (overrides config.yaml ticker list)'
    )

    # 기타
    parser.add_argument(
        '--max-lookback-days',
        type=int,
        help='Max lookback days for first ingestion (overrides config)'
    )

    args = parser.parse_args()

    try:
        # 설정 파일 로드
        config = load_config(args.config)
        logger.info(f"Loaded config from {args.config}")

        # ClickHouse 연결 정보
        db_config = config.get('database', {})
        host = args.host or db_config.get('host', 'localhost')
        port = args.port or db_config.get('port', 8123)
        database = args.database or db_config.get('database', 'default')
        user = args.user or db_config.get('user', 'default')
        password = args.password or db_config.get('password', 'password')

        # 티커 목록
        if args.tickers:
            tickers = [t.strip() for t in args.tickers.split(',')]
        else:
            tickers = config.get('strategy', {}).get('tickers', [])

        if not tickers:
            logger.error("No tickers specified in config or command line")
            sys.exit(1)

        # max_lookback_days
        max_lookback_days = args.max_lookback_days or \
                           config.get('data_ingestion', {}).get('default_lookback_days', 365)

        logger.info(f"Update parameters:")
        logger.info(f"  Tickers: {tickers}")
        logger.info(f"  Max lookback days: {max_lookback_days}")
        logger.info(f"  ClickHouse: {host}:{port}/{database}")

        # ClickHouse 연결
        client = get_client(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        logger.info("Connected to ClickHouse")

        # 각 티커별 데이터 업데이트
        success_count = 0
        fail_count = 0
        skip_count = 0

        for ticker in tickers:
            result = update_ticker(client, ticker, max_lookback_days)
            if result:
                success_count += 1
            else:
                fail_count += 1

        # 결과 요약
        logger.info("=" * 60)
        logger.info(f"Update completed:")
        logger.info(f"  Success: {success_count}/{len(tickers)}")
        logger.info(f"  Failed: {fail_count}/{len(tickers)}")
        logger.info("=" * 60)

        # 종료 코드
        sys.exit(0 if fail_count == 0 else 1)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
