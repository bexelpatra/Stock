"""
시장 데이터 관리 모듈.

[ 역할 ]
    DataProvider를 감싸서 캐싱 + 편의 메서드 제공.
    동일 데이터 반복 조회 시 캐시에서 즉시 반환.

[ 의존성 ]
    - core/data_provider.py::DataProvider (데이터 소스 추상화)

[ 호출하는 곳 ]
    - 실전 매매 시 스케줄러에서 사용 (향후)
    - 백테스트에서는 engine.py가 직접 DataFrame을 다루므로 미사용
"""

from datetime import date
from typing import Optional

import pandas as pd

from trading_system.core.data_provider import DataProvider


class MarketDataManager:
    """DataProvider 위에 캐싱 레이어를 추가한 매니저.

    사용 예:
        provider = MockDataProvider()
        manager = MarketDataManager(provider)
        df = manager.get_market_data("005930", start, end)
    """

    def __init__(self, data_provider: DataProvider):
        self.provider = data_provider
        self._cache: dict[str, pd.DataFrame] = {}  # "ticker_start_end" → DataFrame

    def get_market_data(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """시장 데이터 조회 (캐싱 지원).

        Returns:
            DataFrame with columns: [date, open, high, low, close, volume]
        """
        cache_key = f"{ticker}_{start_date}_{end_date}"

        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        df = self.provider.get_ohlcv(ticker, start_date, end_date)
        if use_cache:
            self._cache[cache_key] = df
        return df

    def get_latest_data(
        self,
        ticker: str,
        end_date: date,
        lookback_days: int = 30,
    ) -> pd.DataFrame:
        """최근 N일간 데이터 조회."""
        start = pd.Timestamp(end_date) - pd.Timedelta(days=lookback_days * 2)
        df = self.get_market_data(ticker, start.date(), end_date)
        return df.tail(lookback_days)

    def get_n_days_ago_close(
        self,
        ticker: str,
        current_date: date,
        n: int = 1,
    ) -> Optional[float]:
        """N일 전 종가 조회."""
        df = self.get_latest_data(ticker, current_date, lookback_days=n + 5)
        if len(df) < n + 1:
            return None
        return float(df.iloc[-(n + 1)]["close"])

    def clear_cache(self) -> None:
        """캐시 초기화."""
        self._cache.clear()
