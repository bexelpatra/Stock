"""
ClickHouse 기반 DataProvider 구현.

[ 역할 ]
    ClickHouse에 저장된 주가 데이터를 조회하여 전략/백테스트에 제공.
    DataProvider 인터페이스를 구현하여 기존 시스템과 호환.

[ 의존성 ]
    - core/data_provider.py::DataProvider (추상 클래스)
    - ingestion/clickhouse_schema.py (ClickHouse 연결 및 스키마)

[ 호출하는 곳 ]
    - run_backtest.py (--source clickhouse 옵션 사용 시)
    - 실전 매매 시 MarketDataManager를 통해 사용
"""

from datetime import date
from typing import Optional

import pandas as pd
from clickhouse_connect.driver import Client

from trading_system.core.data_provider import DataProvider, OHLCV
from trading_system.ingestion.clickhouse_schema import get_client


class ClickHouseDataProvider(DataProvider):
    """ClickHouse 기반 데이터 제공자.

    사용 예:
        provider = ClickHouseDataProvider('localhost', 8123, 'default', password='password')
        df = provider.get_ohlcv('005930.KS', date(2024, 1, 1), date(2024, 12, 31))
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8123,
        database: str = "default",
        user: str = "default",
        password: str = "password",
        use_adjusted_close: bool = True,
    ):
        """
        Args:
            host: ClickHouse 호스트
            port: HTTP 포트 (기본값: 8123)
            database: 데이터베이스 이름
            user: 사용자 이름
            password: 비밀번호
            use_adjusted_close: True이면 adjusted_close를 사용, False이면 close 사용
        """
        self.client: Client = get_client(host, port, database, user, password)
        self.use_adjusted_close = use_adjusted_close

    def get_ohlcv(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """OHLCV 데이터 조회.

        Args:
            ticker: 종목 코드 (예: '^GSPC', '005930.KS')
            start_date: 시작일
            end_date: 종료일

        Returns:
            DataFrame with columns: [date, open, high, low, close, volume]
            - close 컬럼은 use_adjusted_close 옵션에 따라 adjusted_close 또는 close
        """
        # close 컬럼 선택
        close_column = "adjusted_close" if self.use_adjusted_close else "close"

        query = f"""
            SELECT
                date,
                open,
                high,
                low,
                {close_column} as close,
                volume
            FROM stock_ohlcv
            WHERE ticker = %(ticker)s
              AND date >= %(start_date)s
              AND date <= %(end_date)s
            ORDER BY date ASC
        """

        result = self.client.query(
            query,
            parameters={
                "ticker": ticker,
                "start_date": start_date,
                "end_date": end_date,
            }
        )

        # DataFrame으로 변환
        df = pd.DataFrame(
            result.result_rows,
            columns=['date', 'open', 'high', 'low', 'close', 'volume']
        )

        # date 컬럼을 datetime으로 변환 (pandas에서 표준)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])

        return df

    def get_current_ohlcv(self, ticker: str) -> OHLCV:
        """실시간(당일) OHLCV 조회.

        ClickHouse의 경우 실시간 데이터가 아니므로,
        가장 최근 날짜의 데이터를 반환합니다.

        Args:
            ticker: 종목 코드

        Returns:
            OHLCV 객체

        Raises:
            ValueError: 데이터가 없는 경우
        """
        # close 컬럼 선택
        close_column = "adjusted_close" if self.use_adjusted_close else "close"

        query = f"""
            SELECT
                date,
                open,
                high,
                low,
                {close_column} as close,
                volume
            FROM stock_ohlcv
            WHERE ticker = %(ticker)s
            ORDER BY date DESC
            LIMIT 1
        """

        result = self.client.query(query, parameters={"ticker": ticker})

        if not result.result_rows:
            raise ValueError(f"No data found for ticker: {ticker}")

        row = result.result_rows[0]
        return OHLCV(
            date=row[0],
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=int(row[5])
        )

    def get_tickers(self) -> list[str]:
        """조회 가능한 종목 코드 목록.

        Returns:
            티커 리스트 (알파벳 순 정렬)
        """
        query = "SELECT DISTINCT ticker FROM stock_ohlcv ORDER BY ticker"
        result = self.client.query(query)
        return [row[0] for row in result.result_rows]

    def get_date_range(self, ticker: str) -> Optional[tuple[date, date]]:
        """특정 티커의 날짜 범위 조회.

        Args:
            ticker: 종목 코드

        Returns:
            (최소 날짜, 최대 날짜) 튜플, 데이터가 없으면 None
        """
        query = """
            SELECT MIN(date) as min_date, MAX(date) as max_date
            FROM stock_ohlcv
            WHERE ticker = %(ticker)s
        """
        result = self.client.query(query, parameters={"ticker": ticker})

        if result.result_rows:
            min_date, max_date = result.result_rows[0]
            if min_date and max_date:
                return (min_date, max_date)

        return None

    def get_record_count(self, ticker: Optional[str] = None) -> int:
        """레코드 수 조회.

        Args:
            ticker: 특정 티커 (None이면 전체)

        Returns:
            레코드 수
        """
        if ticker:
            query = "SELECT COUNT(*) FROM stock_ohlcv WHERE ticker = %(ticker)s"
            result = self.client.query(query, parameters={"ticker": ticker})
        else:
            query = "SELECT COUNT(*) FROM stock_ohlcv"
            result = self.client.query(query)

        return result.result_rows[0][0] if result.result_rows else 0

    def close(self):
        """ClickHouse 연결 종료."""
        if hasattr(self.client, 'close'):
            self.client.close()


if __name__ == "__main__":
    # 테스트 코드
    import sys
    from pathlib import Path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    from trading_system.data.clickhouse_provider import ClickHouseDataProvider

    provider = ClickHouseDataProvider(
        host='localhost',
        port=8123,
        database='default',
        password='password',
        use_adjusted_close=True
    )

    # 1. 티커 목록 조회
    tickers = provider.get_tickers()
    print(f"Available tickers: {tickers}")

    if tickers:
        ticker = tickers[0]
        print(f"\nTesting with ticker: {ticker}")

        # 2. 날짜 범위 조회
        date_range = provider.get_date_range(ticker)
        if date_range:
            print(f"Date range: {date_range[0]} to {date_range[1]}")

        # 3. OHLCV 데이터 조회
        df = provider.get_ohlcv(ticker, date(2024, 1, 1), date(2024, 1, 31))
        print(f"\nFetched {len(df)} rows")
        print(df.head())

        # 4. 최신 OHLCV 조회
        current = provider.get_current_ohlcv(ticker)
        print(f"\nCurrent OHLCV:")
        print(f"  Date: {current.date}")
        print(f"  Close: {current.close}")

        # 5. 레코드 수 조회
        count = provider.get_record_count(ticker)
        print(f"\nTotal records for {ticker}: {count}")
