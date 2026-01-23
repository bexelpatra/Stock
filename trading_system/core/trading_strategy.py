"""
매매 전략 추상 클래스 정의.

[ 역할 ]
    매매 로직의 인터페이스를 정의.
    시장 데이터와 포지션 정보를 받아 매수/매도/홀드 시그널을 생성.

[ 구현체 ]
    - strategies/split_buy_strategy.py::SplitBuyStrategy (분할매수-목표수익 전략)
    - strategies/custom_strategy.py  (사용자 커스텀 전략 - 향후)

[ 호출하는 곳 ]
    - backtest/engine.py::BacktestEngine._simulate_day()에서
      매일 generate_signal()을 호출하여 시그널을 받고 주문 실행

[ 데이터 흐름 ]
    market_data(OHLCV DataFrame) + position_info → generate_signal() → Signal 반환
    Signal.signal_type이 BUY/SELL이면 엔진이 주문 실행
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import pandas as pd


class SignalType(Enum):
    """전략이 반환하는 시그널 종류."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Signal:
    """generate_signal()의 반환값. 엔진에 전달되어 주문으로 변환됨."""
    signal_type: SignalType
    ticker: str
    price: float = 0.0       # 시그널 발생 시점 가격
    quantity: int = 0        # 주문 수량
    reason: str = ""         # 시그널 발생 사유 (로깅용)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PositionInfo:
    """현재 보유 현황. backtest/engine.py가 Portfolio에서 구성하여 전략에 전달."""
    ticker: str
    quantity: int = 0               # 보유 수량
    avg_price: float = 0.0          # 평균 매수가
    buy_count: int = 0              # 현재까지 매수 횟수
    max_buy_count: int = 0          # 최대 매수 가능 횟수 (= split_count)
    unrealized_profit: float = 0.0
    unrealized_profit_rate: float = 0.0


class TradingStrategy(ABC):
    """매매 전략 추상 클래스.

    새 전략을 만들려면 이 클래스를 상속받아 4개 메서드를 구현하면 된다:
    - generate_signal(): 핵심 시그널 생성 (should_buy/should_sell 내부 호출)
    - calculate_position_size(): 주문 수량 결정
    - should_buy(): 매수 조건 판단
    - should_sell(): 매도 조건 판단
    """

    def __init__(self, name: str, params: dict[str, Any] | None = None):
        self.name = name
        self.params = params or {}  # config.yaml에서 로드된 전략 파라미터

    @abstractmethod
    def generate_signal(
        self,
        market_data: pd.DataFrame,
        position_info: PositionInfo,
        available_cash: float,
    ) -> Signal:
        """매매 시그널 생성.

        Args:
            market_data: OHLCV DataFrame (최근 데이터 포함)
            position_info: 현재 포지션 정보
            available_cash: 사용 가능 현금

        Returns:
            Signal: 매수/매도/홀드 시그널
        """
        ...

    @abstractmethod
    def calculate_position_size(
        self,
        available_cash: float,
        signal: Signal,
    ) -> int:
        """매수/매도 수량 계산.

        Args:
            available_cash: 사용 가능 현금
            signal: 매매 시그널

        Returns:
            주문 수량
        """
        ...

    @abstractmethod
    def should_buy(
        self,
        market_data: pd.DataFrame,
        position_info: PositionInfo,
        available_cash: float,
    ) -> tuple[bool, str]:
        """매수 조건 판단.

        Returns:
            (매수 여부, 사유)
        """
        ...

    @abstractmethod
    def should_sell(
        self,
        market_data: pd.DataFrame,
        position_info: PositionInfo,
    ) -> tuple[bool, str]:
        """매도 조건 판단.

        Returns:
            (매도 여부, 사유)
        """
        ...
