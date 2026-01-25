"""
Yahoo Finance 데이터 수집 모듈
"""
import yfinance as yf
import pandas as pd
from datetime import date, datetime, timedelta
import time
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fetch_ticker_data(
    ticker: str,
    start_date: date,
    end_date: date,
    max_retries: int = 3,
    retry_delay: int = 5
) -> Optional[pd.DataFrame]:
    """
    Yahoo Finance에서 티커 데이터를 수집합니다.

    Args:
        ticker: 티커 심볼 (예: '^GSPC', '005930.KS')
        start_date: 시작 날짜
        end_date: 종료 날짜
        max_retries: 최대 재시도 횟수
        retry_delay: 재시도 간 대기 시간 (초)

    Returns:
        DataFrame with columns: [Open, High, Low, Close, Adj Close, Volume]
        또는 실패 시 None
    """
    for attempt in range(max_retries):
        try:
            logger.info(f"Fetching {ticker} from {start_date} to {end_date} (attempt {attempt + 1}/{max_retries})")

            # yfinance로 데이터 다운로드
            ticker_obj = yf.Ticker(ticker)
            df = ticker_obj.history(
                start=start_date,
                end=end_date + timedelta(days=1),  # end_date 포함
                auto_adjust=False,  # Adj Close를 별도로 가져옴
                actions=False  # Dividends, Stock Splits 제외
            )

            if df.empty:
                logger.warning(f"No data found for {ticker}")
                return None

            # 인덱스(날짜)를 컬럼으로 변환
            df = df.reset_index()

            # 컬럼명 표준화
            df = df.rename(columns={
                'Date': 'date',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Adj Close': 'adj_close',
                'Volume': 'volume'
            })

            # 필요한 컬럼만 선택
            df = df[['date', 'open', 'high', 'low', 'close', 'adj_close', 'volume']]

            # date 컬럼을 datetime.date로 변환 (timezone 제거)
            if pd.api.types.is_datetime64_any_dtype(df['date']):
                df['date'] = df['date'].dt.date

            # 데이터 검증
            if validate_data(df, ticker):
                logger.info(f"Successfully fetched {len(df)} rows for {ticker}")
                return df
            else:
                logger.warning(f"Data validation failed for {ticker}")
                return None

        except Exception as e:
            logger.error(f"Error fetching {ticker} (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error(f"Max retries reached for {ticker}")
                return None

    return None


def validate_data(df: pd.DataFrame, ticker: str) -> bool:
    """
    수집한 데이터를 검증합니다.

    Args:
        df: 검증할 DataFrame
        ticker: 티커 심볼

    Returns:
        검증 통과 여부
    """
    if df is None or df.empty:
        logger.warning(f"Empty DataFrame for {ticker}")
        return False

    # 필수 컬럼 확인
    required_columns = ['date', 'open', 'high', 'low', 'close', 'adj_close', 'volume']
    missing_columns = set(required_columns) - set(df.columns)
    if missing_columns:
        logger.error(f"Missing columns for {ticker}: {missing_columns}")
        return False

    # NULL 값 확인
    null_counts = df[required_columns].isnull().sum()
    if null_counts.any():
        logger.warning(f"NULL values found in {ticker}: {null_counts[null_counts > 0].to_dict()}")
        # NULL이 있어도 일단 통과 (ClickHouse에서 처리)

    # 가격 검증 (음수 또는 0 확인)
    price_columns = ['open', 'high', 'low', 'close', 'adj_close']
    for col in price_columns:
        if (df[col] <= 0).any():
            invalid_count = (df[col] <= 0).sum()
            logger.warning(f"Invalid {col} values (<=0) for {ticker}: {invalid_count} rows")

    # OHLC 관계 검증 (high >= low)
    if (df['high'] < df['low']).any():
        invalid_count = (df['high'] < df['low']).sum()
        logger.warning(f"Invalid OHLC relationship (high < low) for {ticker}: {invalid_count} rows")

    # Volume 검증 (음수 확인)
    if (df['volume'] < 0).any():
        invalid_count = (df['volume'] < 0).sum()
        logger.warning(f"Invalid volume values (<0) for {ticker}: {invalid_count} rows")

    return True


def fetch_recent_data(ticker: str, days: int = 30) -> Optional[pd.DataFrame]:
    """
    최근 N일간의 데이터를 수집합니다.

    Args:
        ticker: 티커 심볼
        days: 수집할 일수

    Returns:
        DataFrame 또는 None
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    return fetch_ticker_data(ticker, start_date, end_date)


if __name__ == "__main__":
    # 테스트 코드
    test_ticker = "^GSPC"
    test_start = date(2024, 1, 1)
    test_end = date(2024, 1, 31)

    df = fetch_ticker_data(test_ticker, test_start, test_end)
    if df is not None:
        print(f"\nFetched {len(df)} rows for {test_ticker}")
        print(f"\nFirst 5 rows:")
        print(df.head())
        print(f"\nData types:")
        print(df.dtypes)
        print(f"\nDate range: {df['date'].min()} to {df['date'].max()}")
