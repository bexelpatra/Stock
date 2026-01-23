"""
주가 데이터 제공 추상 클래스 정의.

[ 역할 ]
    OHLCV(시가/고가/저가/종가/거래량) 데이터를 제공하는 인터페이스.
    데이터 소스(파일, API, DB 등)에 독립적으로 전략/백테스트에 데이터 공급.

[ 구현체 ]
    - brokers/mock_broker.py::MockDataProvider  (DataFrame 기반, 백테스트용)
    - 향후: 실시간 API 연동 구현체

[ 호출하는 곳 ]
    - data/market_data.py::MarketDataManager가 이 인터페이스를 통해 데이터 조회
    - backtest/engine.py에서 직접 DataFrame을 전달하여 사용
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass
class OHLCV:
    """단일 봉(캔들) 데이터. get_current_ohlcv()의 반환값."""
    date: date
    open: float      # 시가
    high: float      # 고가
    low: float       # 저가
    close: float     # 종가
    volume: int      # 거래량


class DataProvider(ABC):
    """주가 데이터 제공 추상 클래스.

    모든 데이터 제공자 구현체는 이 클래스를 상속받아 아래 메서드를 구현해야 한다.
    """

    @abstractmethod
    def get_ohlcv(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """OHLCV 데이터 조회.

        Args:
            ticker: 종목 코드
            start_date: 시작일
            end_date: 종료일

        Returns:
            DataFrame with columns: [date, open, high, low, close, volume]
        """
        ...

    @abstractmethod
    def get_current_ohlcv(self, ticker: str) -> OHLCV:
        """실시간(당일) OHLCV 조회."""
        ...

    @abstractmethod
    def get_tickers(self) -> list[str]:
        """조회 가능한 종목 코드 목록."""
        ...
